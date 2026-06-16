"""Non-blocking async logging for callback-safe tick paths."""

from __future__ import annotations

import atexit
import logging
import logging.handlers
import queue
import sys

_log_listener: logging.handlers.QueueListener | None = None
_logger_initialized = False

LOGGER_NAME = "trading_engine"


class _NonBlockingQueueHandler(logging.handlers.QueueHandler):
    """Callback 路徑專用：queue 滿時丟棄 log，絕不阻塞 on_tick。"""

    def enqueue(self, record: logging.LogRecord) -> None:
        try:
            self.queue.put_nowait(record)
        except queue.Full:
            pass


def setup_async_logging(
    level: str = "INFO",
    log_file: str = "",
    *,
    configure_root: bool = True,
) -> logging.Logger:
    """QueueHandler（非阻塞入隊）+ 背景 QueueListener 負責磁碟/終端 I/O."""
    global _log_listener, _logger_initialized

    if _log_listener is not None:
        _log_listener.stop()
        _log_listener = None

    numeric_level = getattr(logging, level, logging.INFO)
    log_queue: queue.Queue = queue.Queue(-1)

    if configure_root:
        root = logging.getLogger()
        root.handlers.clear()
        root.setLevel(numeric_level)
        root.addHandler(_NonBlockingQueueHandler(log_queue))
    else:
        pkg_logger = logging.getLogger(LOGGER_NAME)
        pkg_logger.handlers.clear()
        pkg_logger.setLevel(numeric_level)
        pkg_logger.propagate = False
        pkg_logger.addHandler(_NonBlockingQueueHandler(log_queue))

    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )
    sink_handlers: list[logging.Handler] = []
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)
    sink_handlers.append(stream_handler)

    if log_file:
        file_handler = logging.handlers.TimedRotatingFileHandler(
            log_file,
            when="midnight",
            backupCount=14,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        sink_handlers.append(file_handler)

    _log_listener = logging.handlers.QueueListener(
        log_queue,
        *sink_handlers,
        respect_handler_level=True,
    )
    _log_listener.start()
    atexit.register(shutdown_async_logging)
    _logger_initialized = True
    return logging.getLogger(LOGGER_NAME)


def get_logger(name: str = LOGGER_NAME) -> logging.Logger:
    """Return package logger; initializes async logging once on first call."""
    global _logger_initialized
    if not _logger_initialized:
        setup_async_logging()
    return logging.getLogger(name)


def shutdown_async_logging() -> None:
    global _log_listener, _logger_initialized
    if _log_listener is not None:
        _log_listener.stop()
        _log_listener = None
    _logger_initialized = False
