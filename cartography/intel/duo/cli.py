"""
Duo CLI option definitions for cartography.
"""
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

PANEL = "Duo Options"
MODULE_NAME = "duo"

OPTION_DEFINITIONS: list[tuple[str, type, str, str, Any, dict[str, Any]]] = [
    (
        "duo_api_key_env_var",
        str | None,
        "--duo-api-key-env-var",
        "Environment variable name containing Duo API key.",
        None,
        {},
    ),
    (
        "duo_api_secret_env_var",
        str | None,
        "--duo-api-secret-env-var",
        "Environment variable name containing Duo API secret.",
        None,
        {},
    ),
    (
        "duo_api_hostname",
        str | None,
        "--duo-api-hostname",
        "Duo API hostname.",
        None,
        {},
    ),
]


def process_cli_args(args: dict[str, Any]) -> dict[str, Any]:
    """Process raw CLI argument values into Config-ready keyword arguments."""
    duo_api_key = None
    duo_api_secret = None
    if (
        args.get("duo_api_key_env_var")
        and args.get("duo_api_secret_env_var")
        and args.get("duo_api_hostname")
    ):
        logger.debug(
            "Reading Duo credentials from environment variables %s, %s",
            args["duo_api_key_env_var"],
            args["duo_api_secret_env_var"],
        )
        duo_api_key = os.environ.get(args["duo_api_key_env_var"])
        duo_api_secret = os.environ.get(args["duo_api_secret_env_var"])

    return {
        "duo_api_key": duo_api_key,
        "duo_api_secret": duo_api_secret,
        "duo_api_hostname": args.get("duo_api_hostname"),
    }
