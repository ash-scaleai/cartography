"""
Google Workspace CLI option definitions for cartography.
"""
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

PANEL = "Google Workspace Options"
MODULE_NAME = "googleworkspace"

OPTION_DEFINITIONS: list[tuple[str, type, str, str, Any, dict[str, Any]]] = [
    (
        "googleworkspace_auth_method",
        str,
        "--googleworkspace-auth-method",
        'Google Workspace authentication method: "delegated", "oauth", or "default".',
        "delegated",
        {},
    ),
    (
        "googleworkspace_tokens_env_var",
        str,
        "--googleworkspace-tokens-env-var",
        "Environment variable name containing Google Workspace credentials.",
        "GOOGLEWORKSPACE_GOOGLE_APPLICATION_CREDENTIALS",
        {},
    ),
]


def process_cli_args(args: dict[str, Any]) -> dict[str, Any]:
    """Process raw CLI argument values into Config-ready keyword arguments."""
    googleworkspace_config = None
    if args.get("googleworkspace_tokens_env_var"):
        logger.debug(
            "Reading config for Google Workspace from environment variable %s",
            args["googleworkspace_tokens_env_var"],
        )
        googleworkspace_config = os.environ.get(args["googleworkspace_tokens_env_var"])

    return {
        "googleworkspace_auth_method": args.get("googleworkspace_auth_method", "delegated"),
        "googleworkspace_config": googleworkspace_config,
    }
