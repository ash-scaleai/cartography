"""
Workday CLI option definitions for cartography.
"""
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

PANEL = "Workday Options"
MODULE_NAME = "workday"

OPTION_DEFINITIONS: list[tuple[str, type, str, str, Any, dict[str, Any]]] = [
    (
        "workday_api_url",
        str | None,
        "--workday-api-url",
        "Workday API URL.",
        None,
        {},
    ),
    (
        "workday_api_login",
        str | None,
        "--workday-api-login",
        "Workday API login username.",
        None,
        {},
    ),
    (
        "workday_api_password_env_var",
        str | None,
        "--workday-api-password-env-var",
        "Environment variable name containing Workday API password.",
        None,
        {},
    ),
]


def process_cli_args(args: dict[str, Any]) -> dict[str, Any]:
    """Process raw CLI argument values into Config-ready keyword arguments."""
    workday_api_password = None
    if (
        args.get("workday_api_url")
        and args.get("workday_api_login")
        and args.get("workday_api_password_env_var")
    ):
        logger.debug(
            "Reading Workday API password from environment variable %s",
            args["workday_api_password_env_var"],
        )
        workday_api_password = os.environ.get(args["workday_api_password_env_var"])

    return {
        "workday_api_url": args.get("workday_api_url"),
        "workday_api_login": args.get("workday_api_login"),
        "workday_api_password": workday_api_password,
    }
