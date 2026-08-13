from __future__ import annotations

import json
import logging
import time
from contextvars import ContextVar
from uuid import uuid4

from fastapi import Request


request_id_context: ContextVar[str] = ContextVar("request_id", default="-")
logger = logging.getLogger("duxue")


def configure_logging() -> None:
    if logger.handlers:
        return
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


def log_event(event: str, **fields) -> None:
    payload = {
        "event": event,
        "request_id": request_id_context.get(),
        **fields,
    }
    logger.info(json.dumps(payload, ensure_ascii=False, default=str))


async def request_context_middleware(request: Request, call_next):
    request_id = request.headers.get("x-request-id", "").strip()[:128] or uuid4().hex
    token = request_id_context.set(request_id)
    started = time.perf_counter()
    try:
        response = await call_next(request)
        response.headers["x-request-id"] = request_id
        log_event(
            "http_request",
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            duration_ms=round((time.perf_counter() - started) * 1000, 2),
        )
        return response
    finally:
        request_id_context.reset(token)
