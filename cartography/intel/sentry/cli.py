"""
Sentry CLI option definitions for cartography.
"""
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

PANEL = "Sentry Options"
MODULE_NAME = "sentry"

OPTION_DEFINITIONS: list[tuple[str, type, str, str, Any, dict[str, Any]]] = [
    (
        "sentry_token_env_var",
        str | None,
        "--sentry-token-env-var",
        "Environment variable name containing Sentry internal integration token.",
        None,
        {},
    ),
    (
        "sentry_org",
        str | None,
        "--sentry-org",
        "Sentry organization slug. Required when using an internal integration token.",
        None,
        {},
    ),
    (
        "sentry_host",
        str,
        "--sentry-host",
        "Sentry host URL (default: https://sentry.io). Use for self-hosted instances.",
        "https://sentry.io",
        {},
    ),
]


def process_cli_args(args: dict[str, Any]) -> dict[str, Any]:
    """Process raw CLI argument values into Config-ready keyword arguments."""
    sentry_token = None
    if args.get("sentry_token_env_var"):
        logger.debug(
            "Reading Sentry token from environment variable %s",
            args["sentry_token_env_var"],
        )
        sentry_token = os.environ.get(args["sentry_token_env_var"])

    return {
        "sentry_token": sentry_token,
        "sentry_org": args.get("sentry_org"),
        "sentry_host": args.get("sentry_host", "https://sentry.io"),
    }
