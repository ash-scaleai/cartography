"""
JumpCloud CLI option definitions for cartography.
"""
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

PANEL = "JumpCloud Options"
MODULE_NAME = "jumpcloud"

OPTION_DEFINITIONS: list[tuple[str, type, str, str, Any, dict[str, Any]]] = [
    (
        "jumpcloud_api_key_env_var",
        str | None,
        "--jumpcloud-api-key-env-var",
        "Environment variable name containing JumpCloud API key.",
        None,
        {},
    ),
    (
        "jumpcloud_org_id",
        str | None,
        "--jumpcloud-org-id",
        "JumpCloud organization ID used as the tenant identifier.",
        None,
        {},
    ),
]


def process_cli_args(args: dict[str, Any]) -> dict[str, Any]:
    """Process raw CLI argument values into Config-ready keyword arguments."""
    jumpcloud_api_key = None
    if args.get("jumpcloud_api_key_env_var"):
        logger.debug(
            "Reading API key for JumpCloud from environment variable %s",
            args["jumpcloud_api_key_env_var"],
        )
        jumpcloud_api_key = os.environ.get(args["jumpcloud_api_key_env_var"])

    return {
        "jumpcloud_api_key": jumpcloud_api_key,
        "jumpcloud_org_id": args.get("jumpcloud_org_id"),
    }
