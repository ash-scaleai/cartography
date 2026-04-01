"""
BigFix CLI option definitions for cartography.
"""
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

PANEL = "BigFix Options"
MODULE_NAME = "bigfix"

OPTION_DEFINITIONS: list[tuple[str, type, str, str, Any, dict[str, Any]]] = [
    (
        "bigfix_username",
        str | None,
        "--bigfix-username",
        "BigFix username for authentication.",
        None,
        {},
    ),
    (
        "bigfix_password_env_var",
        str | None,
        "--bigfix-password-env-var",
        "Environment variable name containing BigFix password.",
        None,
        {},
    ),
    (
        "bigfix_root_url",
        str | None,
        "--bigfix-root-url",
        "BigFix API URL.",
        None,
        {},
    ),
]


def process_cli_args(args: dict[str, Any]) -> dict[str, Any]:
    """Process raw CLI argument values into Config-ready keyword arguments."""
    bigfix_password = None
    if (
        args.get("bigfix_username")
        and args.get("bigfix_password_env_var")
        and args.get("bigfix_root_url")
    ):
        logger.debug(
            "Reading BigFix password from environment variable %s",
            args["bigfix_password_env_var"],
        )
        bigfix_password = os.environ.get(args["bigfix_password_env_var"])

    return {
        "bigfix_username": args.get("bigfix_username"),
        "bigfix_password": bigfix_password,
        "bigfix_root_url": args.get("bigfix_root_url"),
    }
