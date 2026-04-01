from __future__ import annotations

import os
from dataclasses import dataclass
from dataclasses import field
from typing import Optional


@dataclass
class ObservabilityConfig:
    """Configuration for cartography observability features.

    Controls OpenTelemetry tracing, metrics export, and structured logging.
    All features degrade gracefully when dependencies are missing or
    configuration is absent.

    Attributes:
        enabled: Master switch for observability features. When False,
            all tracing, metrics, and structured logging are disabled.
        otlp_endpoint: Optional OTLP collector endpoint (e.g.
            ``http://localhost:4317``). When None, tracers and meters
            fall back to no-op implementations.
        service_name: The OpenTelemetry service name reported in traces
            and metrics. Defaults to ``"cartography"``.
        log_format: Log output format. ``"json"`` enables structured JSON
            logging; ``"text"`` keeps the default Python log format.
    """

    enabled: bool = True
    otlp_endpoint: Optional[str] = None
    service_name: str = "cartography"
    log_format: str = "text"

    @classmethod
    def from_env(cls) -> ObservabilityConfig:
        """Build an :class:`ObservabilityConfig` from environment variables.

        Recognised variables:

        * ``CARTOGRAPHY_OTLP_ENDPOINT`` -- OTLP collector endpoint.
        * ``CARTOGRAPHY_LOG_FORMAT`` -- ``"json"`` or ``"text"`` (default).
        * ``CARTOGRAPHY_OBSERVABILITY_ENABLED`` -- ``"0"`` or ``"false"``
          to disable all observability features.
        * ``CARTOGRAPHY_SERVICE_NAME`` -- Override the default service name.
        """
        enabled_raw = os.environ.get("CARTOGRAPHY_OBSERVABILITY_ENABLED", "1").lower()
        enabled = enabled_raw not in ("0", "false", "no")
        return cls(
            enabled=enabled,
            otlp_endpoint=os.environ.get("CARTOGRAPHY_OTLP_ENDPOINT"),
            service_name=os.environ.get("CARTOGRAPHY_SERVICE_NAME", "cartography"),
            log_format=os.environ.get("CARTOGRAPHY_LOG_FORMAT", "text"),
        )
