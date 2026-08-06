"""
Thin Langfuse wrapper. Every Vapi tool-call and end-of-call webhook is
traced so a reviewer can open Langfuse and see the full conversation ->
tool-call -> DB-write chain for any call. Failures here must never break
the request path (observability is best-effort).
"""
from contextlib import contextmanager

import structlog
from langfuse import Langfuse

from app.config import settings

log = structlog.get_logger()

langfuse_client: Langfuse | None = None
if settings.LANGFUSE_PUBLIC_KEY and settings.LANGFUSE_SECRET_KEY:
    langfuse_client = Langfuse(
        public_key=settings.LANGFUSE_PUBLIC_KEY,
        secret_key=settings.LANGFUSE_SECRET_KEY,
        host=settings.LANGFUSE_HOST,
    )


@contextmanager
def trace_span(name: str, call_id: str | None = None, **metadata):
    """Wraps a block of work in a Langfuse trace/span. No-ops if unconfigured."""
    if langfuse_client is None:
        yield None
        return
    trace = langfuse_client.trace(name=name, session_id=call_id, metadata=metadata)
    span = trace.span(name=name, input=metadata)
    try:
        yield span
        span.end(output={"status": "ok"})
    except Exception as exc:  # noqa: BLE001
        span.end(output={"status": "error", "error": str(exc)}, level="ERROR")
        log.error("langfuse_span_error", name=name, error=str(exc))
        raise
