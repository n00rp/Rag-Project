import logging
from contextlib import asynccontextmanager
from dataclasses import replace
from uuid import UUID

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, UploadFile
from pydantic import BaseModel, Field

from app import db
from app.boilerplate import strip_repeated_lines
from app.chunking import chunk_pages, document_header
from app.config import Settings, get_settings
from app.embeddings import build_embedder
from app.llm import LlmUnavailableError, build_llm
from app.pdf import NoTextError, PdfError, extract_pages
from app.rag import answer_question

log = logging.getLogger("ai-service")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    app.state.embedder = build_embedder(settings)
    app.state.llm = build_llm(settings)
    db.init_schema(settings.database_url, app.state.embedder.dim)
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
    chunks = chunk_pages(pages, settings.chunk_size, settings.chunk_overlap)
    if header:
        chunks = [replace(c, text=f"{header}. {c.text}") for c in chunks]
    embeddings = app.state.embedder.embed_passages([c.text for c in chunks])
    db.replace_document_chunks(app.state.pool, owner_id, document_id, chunks, embeddings)
    return IngestResponse(document_id=document_id, pages=page_count, chunks=len(chunks))


@app.post("/query", response_model=QueryResponse, dependencies=[Depends(require_internal_key)])
def query(req: QueryRequest, settings: Settings = Depends(get_settings)) -> QueryResponse:
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

    return QueryResponse(
        answer=result.answer,
        grounded=result.grounded,
        sources=[
            SourceOut(
                document_id=h.document_id,
                page=h.page,
                chunk_index=h.chunk_index,
                snippet=h.content,
                score=round(h.score, 4),
            )
            for h in result.sources
        ],
    )


@app.delete("/documents/{document_id}", dependencies=[Depends(require_internal_key)])
def delete_document(document_id: UUID, owner_id: str) -> dict:
    deleted = db.delete_document(app.state.pool, owner_id, document_id)
    return {"deleted_chunks": deleted}
