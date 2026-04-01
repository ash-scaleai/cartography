"""
Kandji CLI option definitions for cartography.
"""
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

PANEL = "Kandji Options"
MODULE_NAME = "kandji"

OPTION_DEFINITIONS: list[tuple[str, type, str, str, Any, dict[str, Any]]] = [
    (
        "kandji_base_uri",
        str | None,
        "--kandji-base-uri",
        "Kandji base URI, e.g. https://company.api.kandji.io.",
        None,
        {},
    ),
    (
        "kandji_tenant_id",
        str | None,
        "--kandji-tenant-id",
        "Kandji tenant ID.",
        None,
        {},
    ),
    (
        "kandji_token_env_var",
        str | None,
        "--kandji-token-env-var",
        "Environment variable name containing Kandji API token.",
        None,
        {},
    ),
]


def process_cli_args(args: dict[str, Any]) -> dict[str, Any]:
    """Process raw CLI argument values into Config-ready keyword arguments."""
    kandji_token = None
    if args.get("kandji_base_uri"):
        if args.get("kandji_token_env_var"):
            logger.debug(
                "Reading Kandji API token from environment variable %s",
                args["kandji_token_env_var"],
            )
            kandji_token = os.environ.get(args["kandji_token_env_var"])
        elif os.environ.get("KANDJI_TOKEN"):
            logger.debug(
                "Reading Kandji API token from environment variable KANDJI_TOKEN",
            )
            kandji_token = os.environ.get("KANDJI_TOKEN")
        else:
            logger.warning(
                "A Kandji base URI was provided but a token was not.",
            )

    return {
        "kandji_base_uri": args.get("kandji_base_uri"),
        "kandji_tenant_id": args.get("kandji_tenant_id"),
        "kandji_token": kandji_token,
    }
