"""
DigitalOcean CLI option definitions for cartography.
"""
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

PANEL = "DigitalOcean Options"
MODULE_NAME = "digitalocean"

OPTION_DEFINITIONS: list[tuple[str, type, str, str, Any, dict[str, Any]]] = [
    (
        "digitalocean_token_env_var",
        str | None,
        "--digitalocean-token-env-var",
        "Environment variable name containing DigitalOcean access token.",
        None,
        {},
    ),
]


def process_cli_args(args: dict[str, Any]) -> dict[str, Any]:
    """Process raw CLI argument values into Config-ready keyword arguments."""
    digitalocean_token = None
    if args.get("digitalocean_token_env_var"):
        logger.debug(
            "Reading token for DigitalOcean from environment variable %s",
            args["digitalocean_token_env_var"],
        )
        digitalocean_token = os.environ.get(args["digitalocean_token_env_var"])

    return {"digitalocean_token": digitalocean_token}
