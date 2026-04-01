"""
Cloudflare CLI option definitions for cartography.
"""
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

PANEL = "Cloudflare Options"
MODULE_NAME = "cloudflare"

OPTION_DEFINITIONS: list[tuple[str, type, str, str, Any, dict[str, Any]]] = [
    (
        "cloudflare_token_env_var",
        str | None,
        "--cloudflare-token-env-var",
        "Environment variable name containing Cloudflare API key.",
        None,
        {},
    ),
]


def process_cli_args(args: dict[str, Any]) -> dict[str, Any]:
    """Process raw CLI argument values into Config-ready keyword arguments."""
    cloudflare_token = None
    if args.get("cloudflare_token_env_var"):
        logger.debug(
            "Reading Cloudflare API key from environment variable %s",
            args["cloudflare_token_env_var"],
        )
        cloudflare_token = os.environ.get(args["cloudflare_token_env_var"])

    return {"cloudflare_token": cloudflare_token}
