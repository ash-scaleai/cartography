"""
PagerDuty CLI option definitions for cartography.
"""
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

PANEL = "PagerDuty Options"
MODULE_NAME = "pagerduty"

OPTION_DEFINITIONS: list[tuple[str, type, str, str, Any, dict[str, Any]]] = [
    (
        "pagerduty_api_key_env_var",
        str | None,
        "--pagerduty-api-key-env-var",
        "Environment variable name containing PagerDuty API key.",
        None,
        {},
    ),
    (
        "pagerduty_request_timeout",
        int | None,
        "--pagerduty-request-timeout",
        "Timeout in seconds for PagerDuty API requests.",
        None,
        {},
    ),
]


def process_cli_args(args: dict[str, Any]) -> dict[str, Any]:
    """Process raw CLI argument values into Config-ready keyword arguments."""
    pagerduty_api_key = None
    if args.get("pagerduty_api_key_env_var"):
        logger.debug(
            "Reading API key for PagerDuty from environment variable %s",
            args["pagerduty_api_key_env_var"],
        )
        pagerduty_api_key = os.environ.get(args["pagerduty_api_key_env_var"])

    return {
        "pagerduty_api_key": pagerduty_api_key,
        "pagerduty_request_timeout": args.get("pagerduty_request_timeout"),
    }
