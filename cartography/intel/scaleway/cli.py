"""
Scaleway CLI option definitions for cartography.
"""
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

PANEL = "Scaleway Options"
MODULE_NAME = "scaleway"

OPTION_DEFINITIONS: list[tuple[str, type, str, str, Any, dict[str, Any]]] = [
    (
        "scaleway_org",
        str | None,
        "--scaleway-org",
        "Scaleway organization ID to sync.",
        None,
        {},
    ),
    (
        "scaleway_access_key",
        str | None,
        "--scaleway-access-key",
        "Scaleway access key for authentication.",
        None,
        {},
    ),
    (
        "scaleway_secret_key_env_var",
        str | None,
        "--scaleway-secret-key-env-var",
        "Environment variable name containing Scaleway secret key.",
        None,
        {},
    ),
]


def process_cli_args(args: dict[str, Any]) -> dict[str, Any]:
    """Process raw CLI argument values into Config-ready keyword arguments."""
    scaleway_secret_key = None
    if args.get("scaleway_secret_key_env_var"):
        logger.debug(
            "Reading Scaleway secret key from environment variable %s",
            args["scaleway_secret_key_env_var"],
        )
        scaleway_secret_key = os.environ.get(args["scaleway_secret_key_env_var"])

    return {
        "scaleway_org": args.get("scaleway_org"),
        "scaleway_access_key": args.get("scaleway_access_key"),
        "scaleway_secret_key": scaleway_secret_key,
    }
