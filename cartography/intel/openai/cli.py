"""
OpenAI CLI option definitions for cartography.
"""
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

PANEL = "OpenAI Options"
MODULE_NAME = "openai"

OPTION_DEFINITIONS: list[tuple[str, type, str, str, Any, dict[str, Any]]] = [
    (
        "openai_apikey_env_var",
        str | None,
        "--openai-apikey-env-var",
        "Environment variable name containing OpenAI API key.",
        None,
        {},
    ),
    (
        "openai_org_id",
        str | None,
        "--openai-org-id",
        "OpenAI organization ID to sync.",
        None,
        {},
    ),
]


def process_cli_args(args: dict[str, Any]) -> dict[str, Any]:
    """Process raw CLI argument values into Config-ready keyword arguments."""
    openai_apikey = None
    if args.get("openai_apikey_env_var"):
        logger.debug(
            "Reading OpenAI API key from environment variable %s",
            args["openai_apikey_env_var"],
        )
        openai_apikey = os.environ.get(args["openai_apikey_env_var"])

    return {
        "openai_apikey": openai_apikey,
        "openai_org_id": args.get("openai_org_id"),
    }
