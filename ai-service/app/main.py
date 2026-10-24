import json
import logging
import time
import uuid
from contextlib import asynccontextmanager
from uuid import UUID

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app import db
from app.boilerplate import strip_repeated_lines
from app.chunking import add_header, chunk_pages, document_header, heading_style, strip_header
from app.config import Settings, get_settings
from app.embeddings import build_embedder
from app.llm import LlmUnavailableError, build_llm
from app.logging_setup import configure_logging, trace_id_from, trace_id_var
from app.pdf import NoTextError, PdfError, extract_pages
from app.rag import answer_question, retrieve, stream_answer

configure_logging()
log = logging.getLogger("ai-service")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    app.state.embedder = build_embedder(settings)
    app.state.llm = build_llm(settings)
    db.init_schema(settings.database_url, app.state.embedder.dim, settings.reset_vectors_on_dim_change)
    app.state.pool = db.create_pool(settings.database_url)
    log.info("ai-service ready (embeddings=%s, llm=%s)", settings.embedding_backend, settings.llm_backend)
    yield
    app.state.pool.close()


def require_internal_key(
    x_internal_key: str | None = Header(default=None), settings: Settings = Depends(get_settings)
) -> None:
    if settings.internal_api_key and x_internal_key != settings.internal_api_key:
        raise HTTPException(status_code=401, detail="Ogiltig nyckel")


app = FastAPI(title="AI service", lifespan=lifespan)


@app.middleware("http")
async def trace_middleware(request, call_next):
    """Adopts the trace id the API sent (W3C traceparent) so all log lines of one question share it."""
    trace_id = trace_id_from(request.headers.get("traceparent")) or uuid.uuid4().hex
    trace_id_var.set(trace_id)
    started = time.perf_counter()
    response = await call_next(request)
    response.headers["X-Trace-Id"] = trace_id
    if request.url.path != "/health":  # polled every few seconds
        log.info("request", extra={"method": request.method, "path": request.url.path,
                                   "status": response.status_code, "duration_ms": round((time.perf_counter() - started) * 1000)})
    return response


class IngestResponse(BaseModel):
    document_id: UUID
    pages: int
    chunks: int


class QueryRequest(BaseModel):
    owner_id: str = Field(min_length=1)
    question: str = Field(min_length=1, max_length=2000)
    document_ids: list[UUID] | None = None
    top_k: int | None = Field(default=None, ge=1, le=20)


class SourceOut(BaseModel):
    document_id: UUID
    page: int
    chunk_index: int
    snippet: str
    score: float


class QueryResponse(BaseModel):
    answer: str
    grounded: bool
    sources: list[SourceOut]
    support: str = "fullt"  # fullt | delvis | inget
    broad: bool = False  # an overview question: the answer may be incomplete


@app.get("/health")
def health() -> dict:
    with app.state.pool.connection() as conn:
        conn.execute("SELECT 1")
    return {"status": "ok"}


@app.post("/ingest", response_model=IngestResponse, dependencies=[Depends(require_internal_key)])
def ingest(
    owner_id: str = Form(min_length=1),
    document_id: UUID = Form(),
    file: UploadFile = File(),
    settings: Settings = Depends(get_settings),
) -> IngestResponse:
    data = file.file.read(settings.max_upload_bytes + 1)
    if len(data) > settings.max_upload_bytes:
        raise HTTPException(status_code=413, detail="Filen är för stor")
    try:
        pages = extract_pages(data)
    except NoTextError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except PdfError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    page_count = len(pages)
    header = document_header(pages) if settings.doc_header else ""
    if settings.strip_page_boilerplate:
        pages = strip_repeated_lines(pages)
    chunks = add_header(chunk_pages(pages, settings.chunk_size, settings.chunk_overlap,
                         settings.section_labels and heading_style(pages)), header)
    embeddings = app.state.embedder.embed_passages([c.text for c in chunks])
    db.replace_document_chunks(app.state.pool, owner_id, document_id, chunks, embeddings)
    return IngestResponse(document_id=document_id, pages=page_count, chunks=len(chunks))


def source_out(h) -> SourceOut:
    return SourceOut(
        document_id=h.document_id,
        page=h.page,
        chunk_index=h.chunk_index,
        snippet=strip_header(h.content),
        score=round(h.score, 4),
    )


@app.post("/query", response_model=QueryResponse, dependencies=[Depends(require_internal_key)])
def query(req: QueryRequest, settings: Settings = Depends(get_settings)) -> QueryResponse:
    started = time.perf_counter()
    try:
        result = answer_question(
            pool=app.state.pool,
            embedder=app.state.embedder,
            llm=app.state.llm,
            settings=settings,
            owner_id=req.owner_id,
            question=req.question,
            document_ids=req.document_ids,
            top_k=req.top_k,
        )
    except LlmUnavailableError as exc:
        log.warning("LLM unavailable: %s", exc)
        raise HTTPException(status_code=503, detail="AI-modellen är inte tillgänglig just nu") from exc

    log.info("answer", extra={"mode": "plain", "question_chars": len(req.question), "sources": len(result.sources),
                              "grounded": result.grounded, "support": result.support, "broad": result.broad,
                              "total_ms": round((time.perf_counter() - started) * 1000)})
    return QueryResponse(
        answer=result.answer, grounded=result.grounded, sources=[source_out(h) for h in result.sources],
        support=result.support, broad=result.broad,
    )


def _line(event: dict) -> str:
    return json.dumps(event, ensure_ascii=False) + "\n"


@app.post("/query/stream", dependencies=[Depends(require_internal_key)])
def query_stream(req: QueryRequest, settings: Settings = Depends(get_settings)) -> StreamingResponse:
    """The answer as it is written, one JSON event per line (application/x-ndjson):

    {"type": "sources", "sources": [...]}   once, before the first token
    {"type": "token", "text": "..."}        while the model writes
    {"type": "support", "level": "delvis"}   (structured answers) how well the excerpts support the answer
    {"type": "done", "answer": "...", "grounded": true, "support": "fullt", "broad": false}   last; if grounded is false
    the sources must be ignored
    {"type": "error", "code": "ai_unavailable", "message": "..."}   if the model cannot be reached

    Retrieval happens before the response starts, so its errors are ordinary HTTP errors."""
    started = time.perf_counter()
    retrieval = retrieve(
        pool=app.state.pool, embedder=app.state.embedder, settings=settings, owner_id=req.owner_id,
        question=req.question, document_ids=req.document_ids, top_k=req.top_k,
    )
    retrieved_ms = round((time.perf_counter() - started) * 1000)

    def events():
        first_token_ms = None
        tokens = 0
        try:
            for kind, payload in stream_answer(app.state.llm, retrieval, settings.structured_answer):
                if kind == "sources":
                    yield _line({"type": "sources", "sources": [source_out(h).model_dump(mode="json") for h in payload]})
                elif kind == "support":
                    yield _line({"type": "support", "level": payload})
                elif kind == "token":
                    tokens += 1
                    if first_token_ms is None:
                        first_token_ms = round((time.perf_counter() - started) * 1000)
                    yield _line({"type": "token", "text": payload})
                else:
                    log.info("answer", extra={
                        "mode": "stream", "question_chars": len(req.question), "hits": len(retrieval.hits),
                        "refused_by_search": retrieval.refused, "grounded": payload.grounded, "support": payload.support,
                        "broad": payload.broad, "tokens": tokens, "retrieve_ms": retrieved_ms,
                        "first_token_ms": first_token_ms, "total_ms": round((time.perf_counter() - started) * 1000)})
                    yield _line({"type": "done", "answer": payload.answer, "grounded": payload.grounded,
                                 "support": payload.support, "broad": payload.broad})
        except LlmUnavailableError as exc:
            log.warning("LLM unavailable: %s", exc)
            yield _line({"type": "error", "code": "ai_unavailable", "message": "AI-modellen är inte tillgänglig just nu"})

    return StreamingResponse(events(), media_type="application/x-ndjson")


@app.delete("/documents/{document_id}", dependencies=[Depends(require_internal_key)])
def delete_document(document_id: UUID, owner_id: str) -> dict:
    deleted = db.delete_document(app.state.pool, owner_id, document_id)
    return {"deleted_chunks": deleted}
