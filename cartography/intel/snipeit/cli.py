"""
SnipeIT CLI option definitions for cartography.
"""
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

PANEL = "SnipeIT Options"
MODULE_NAME = "snipeit"

OPTION_DEFINITIONS: list[tuple[str, type, str, str, Any, dict[str, Any]]] = [
    (
        "snipeit_base_uri",
        str | None,
        "--snipeit-base-uri",
        "SnipeIT base URI.",
        None,
        {},
    ),
    (
        "snipeit_token_env_var",
        str | None,
        "--snipeit-token-env-var",
        "Environment variable name containing SnipeIT API token.",
        None,
        {},
    ),
    (
        "snipeit_tenant_id",
        str | None,
        "--snipeit-tenant-id",
        "SnipeIT tenant ID.",
        None,
        {},
    ),
]


def process_cli_args(args: dict[str, Any]) -> dict[str, Any]:
    """Process raw CLI argument values into Config-ready keyword arguments."""
    snipeit_token = None
    if args.get("snipeit_base_uri"):
        if args.get("snipeit_token_env_var"):
            logger.debug(
                "Reading SnipeIT API token from environment variable %s",
                args["snipeit_token_env_var"],
            )
            snipeit_token = os.environ.get(args["snipeit_token_env_var"])
        elif os.environ.get("SNIPEIT_TOKEN"):
            logger.debug(
                "Reading SnipeIT API token from environment variable SNIPEIT_TOKEN",
            )
            snipeit_token = os.environ.get("SNIPEIT_TOKEN")
        else:
            logger.warning(
                "A SnipeIT base URI was provided but a token was not.",
            )

    return {
        "snipeit_base_uri": args.get("snipeit_base_uri"),
        "snipeit_token": snipeit_token,
        "snipeit_tenant_id": args.get("snipeit_tenant_id"),
    }
