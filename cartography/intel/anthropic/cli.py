"""
Anthropic CLI option definitions for cartography.
"""
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

PANEL = "Anthropic Options"
MODULE_NAME = "anthropic"

OPTION_DEFINITIONS: list[tuple[str, type, str, str, Any, dict[str, Any]]] = [
    (
        "anthropic_apikey_env_var",
        str | None,
        "--anthropic-apikey-env-var",
        "Environment variable name containing Anthropic API key.",
        None,
        {},
    ),
]


def process_cli_args(args: dict[str, Any]) -> dict[str, Any]:
    """Process raw CLI argument values into Config-ready keyword arguments."""
    anthropic_apikey = None
    if args.get("anthropic_apikey_env_var"):
        logger.debug(
            "Reading Anthropic API key from environment variable %s",
            args["anthropic_apikey_env_var"],
        )
        anthropic_apikey = os.environ.get(args["anthropic_apikey_env_var"])

    return {"anthropic_apikey": anthropic_apikey}
