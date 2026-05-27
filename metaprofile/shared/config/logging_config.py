"""structlog 初始化。在 FastAPI 应用启动时调用 configure_logging()。"""
from __future__ import annotations

import logging
import sys

import structlog


def configure_logging(log_level: str = "INFO", env: str = "dev") -> None:
    level = getattr(logging, log_level.upper(), logging.INFO)

    shared_processors: list = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
    ]

    if env == "dev":
        structlog.configure(
            processors=[*shared_processors, structlog.dev.ConsoleRenderer()],
            wrapper_class=structlog.make_filtering_bound_logger(level),
            context_class=dict,
            logger_factory=structlog.PrintLoggerFactory(),
        )
    else:
        structlog.configure(
            processors=[
                *shared_processors,
                structlog.processors.dict_tracebacks,
                structlog.processors.JSONRenderer(),
            ],
            wrapper_class=structlog.make_filtering_bound_logger(level),
            context_class=dict,
            logger_factory=structlog.PrintLoggerFactory(sys.stdout),
        )

    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=level)
