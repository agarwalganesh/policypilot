"""PolicyPilot — Structured Logging Configuration"""
import logging
import sys
import uuid
from typing import Optional

import structlog


def configure_logging(log_level: str = "INFO") -> None:
    """Configure structlog for structured JSON logging."""
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, log_level.upper(), logging.INFO),
    )

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.BoundLogger:
    return structlog.get_logger(name)


def bind_request_context(
    request_id: Optional[str] = None,
    user_id: Optional[str] = None,
) -> str:
    """Bind per-request context variables to structlog."""
    rid = request_id or str(uuid.uuid4())
    structlog.contextvars.clear_contextvars()
    ctx = {"request_id": rid}
    if user_id:
        ctx["user_id"] = user_id
    structlog.contextvars.bind_contextvars(**ctx)
    return rid
