"""
SubImage CLI option definitions for cartography.
"""
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

PANEL = "SubImage Options"
MODULE_NAME = "subimage"

OPTION_DEFINITIONS: list[tuple[str, type, str, str, Any, dict[str, Any]]] = [
    (
        "subimage_client_id_env_var",
        str | None,
        "--subimage-client-id-env-var",
        "Environment variable name containing SubImage client ID.",
        None,
        {},
    ),
    (
        "subimage_client_secret_env_var",
        str | None,
        "--subimage-client-secret-env-var",
        "Environment variable name containing SubImage client secret.",
        None,
        {},
    ),
    (
        "subimage_tenant_url",
        str | None,
        "--subimage-tenant-url",
        "SubImage tenant URL, e.g. https://tenant.subimage.io.",
        None,
        {},
    ),
    (
        "subimage_authkit_url",
        str,
        "--subimage-authkit-url",
        "SubImage AuthKit URL for OAuth2 token exchange.",
        "https://auth.subimage.io",
        {},
    ),
]


def process_cli_args(args: dict[str, Any]) -> dict[str, Any]:
    """Process raw CLI argument values into Config-ready keyword arguments."""
    subimage_client_id = None
    if args.get("subimage_client_id_env_var"):
        logger.debug(
            "Reading SubImage client ID from environment variable %s",
            args["subimage_client_id_env_var"],
        )
        subimage_client_id = os.environ.get(args["subimage_client_id_env_var"])

    subimage_client_secret = None
    if args.get("subimage_client_secret_env_var"):
        logger.debug(
            "Reading SubImage client secret from environment variable %s",
            args["subimage_client_secret_env_var"],
        )
        subimage_client_secret = os.environ.get(args["subimage_client_secret_env_var"])

    return {
        "subimage_client_id": subimage_client_id,
        "subimage_client_secret": subimage_client_secret,
        "subimage_tenant_url": args.get("subimage_tenant_url"),
        "subimage_authkit_url": args.get("subimage_authkit_url", "https://auth.subimage.io"),
    }
