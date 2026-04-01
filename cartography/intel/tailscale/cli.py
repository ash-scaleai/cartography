"""
Tailscale CLI option definitions for cartography.
"""
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

PANEL = "Tailscale Options"
MODULE_NAME = "tailscale"

OPTION_DEFINITIONS: list[tuple[str, type, str, str, Any, dict[str, Any]]] = [
    (
        "tailscale_token_env_var",
        str | None,
        "--tailscale-token-env-var",
        "Environment variable name containing Tailscale API token.",
        None,
        {},
    ),
    (
        "tailscale_org",
        str | None,
        "--tailscale-org",
        "Tailscale organization name to sync.",
        None,
        {},
    ),
    (
        "tailscale_base_url",
        str,
        "--tailscale-base-url",
        "Tailscale API base URL.",
        "https://api.tailscale.com/api/v2",
        {},
    ),
]


def process_cli_args(args: dict[str, Any]) -> dict[str, Any]:
    """Process raw CLI argument values into Config-ready keyword arguments."""
    tailscale_token = None
    if args.get("tailscale_token_env_var"):
        logger.debug(
            "Reading Tailscale API token from environment variable %s",
            args["tailscale_token_env_var"],
        )
        tailscale_token = os.environ.get(args["tailscale_token_env_var"])

    return {
        "tailscale_token": tailscale_token,
        "tailscale_org": args.get("tailscale_org"),
        "tailscale_base_url": args.get("tailscale_base_url", "https://api.tailscale.com/api/v2"),
    }
