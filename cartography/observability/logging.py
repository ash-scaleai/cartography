from __future__ import annotations

import json
import logging
import uuid
from typing import Optional

from cartography.observability.config import ObservabilityConfig

# ---------------------------------------------------------------------------
# Correlation ID helpers
# ---------------------------------------------------------------------------

_correlation_id: Optional[str] = None


def generate_correlation_id() -> str:
    """Create a unique correlation ID for a sync run and store it globally.

    Returns:
        A UUID-4 string that will be attached to every subsequent log
        record via :class:`CorrelationIdFilter`.
    """
    global _correlation_id
    _correlation_id = str(uuid.uuid4())
    return _correlation_id


def get_correlation_id() -> Optional[str]:
    """Return the current correlation ID, or ``None`` if not yet generated."""
    return _correlation_id


# ---------------------------------------------------------------------------
# Logging filter
# ---------------------------------------------------------------------------


class CorrelationIdFilter(logging.Filter):
    """Logging filter that injects the per-sync-run correlation ID.

    After this filter is added to a handler (or the root logger), every
    :class:`logging.LogRecord` will carry a ``correlation_id`` attribute
    that formatters can reference via ``%(correlation_id)s``.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        record.correlation_id = _correlation_id or ""  # type: ignore[attr-defined]
        return True


# ---------------------------------------------------------------------------
# JSON formatter
# ---------------------------------------------------------------------------


class _JsonFormatter(logging.Formatter):
    """Emit each log record as a single JSON line."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry: dict = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if hasattr(record, "correlation_id") and record.correlation_id:  # type: ignore[attr-defined]
            log_entry["correlation_id"] = record.correlation_id  # type: ignore[attr-defined]
        if record.exc_info and record.exc_info[1] is not None:
            log_entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_entry)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def init_logging(config: Optional[ObservabilityConfig] = None) -> None:
    """Configure structured logging according to *config*.

    * Adds :class:`CorrelationIdFilter` to the root logger so that all
      records carry the ``correlation_id`` attribute.
    * When ``config.log_format`` is ``"json"``, replaces the formatter on
      all existing root-logger handlers with :class:`_JsonFormatter`.
    * When *config* is ``None`` or disabled, only the correlation-ID
      filter is attached (harmless no-op overhead).
    """
    root = logging.getLogger()

    # Always install the correlation-id filter
    filt = CorrelationIdFilter()
    root.addFilter(filt)

    if config is None or not config.enabled:
        return

    if config.log_format == "json":
        formatter = _JsonFormatter()
        if root.handlers:
            for handler in root.handlers:
                handler.setFormatter(formatter)
        else:
            # No handlers yet -- add a default StreamHandler with JSON formatting
            handler = logging.StreamHandler()
            handler.setFormatter(formatter)
            root.addHandler(handler)
