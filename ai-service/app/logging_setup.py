"""Structured logs (one JSON object per line) with a trace id that follows a question across the services.

The .NET API starts a trace for every request and its HttpClient sends the W3C `traceparent` header to this
service; `trace_middleware` reads the trace id from it and every log line written while that request is handled
carries it, so `docker compose logs api ai-service | grep <trace id>` shows one question from end to end.
User text is never logged, only its length.
"""

import json
import logging
import re
from contextvars import ContextVar

trace_id_var: ContextVar[str | None] = ContextVar("trace_id", default=None)

# 00-<32 hex trace id>-<16 hex span id>-<2 hex flags>
TRACEPARENT = re.compile(r"^[0-9a-f]{2}-([0-9a-f]{32})-[0-9a-f]{16}-[0-9a-f]{2}$")

# Attributes every LogRecord has; anything else was passed with `extra=` and is written as a field of its own.
_STANDARD = set(logging.LogRecord("", 0, "", 0, "", (), None).__dict__) | {"message", "asctime", "taskName"}


def trace_id_from(header: str | None) -> str | None:
    match = TRACEPARENT.match((header or "").strip().lower())
    return match.group(1) if match else None


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S") + f".{int(record.msecs):03d}Z",
            "level": record.levelname.lower(),
            "logger": record.name,
            "msg": record.getMessage(),
            "trace_id": trace_id_var.get(),
        }
        entry.update({k: v for k, v in record.__dict__.items() if k not in _STANDARD})
        if record.exc_info:
            entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(entry, ensure_ascii=False, default=str)


def configure_logging(level: int = logging.INFO) -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level)
    # uvicorn's access log is one line per request in its own format; ours carry the useful fields.
    logging.getLogger("uvicorn.access").disabled = True
