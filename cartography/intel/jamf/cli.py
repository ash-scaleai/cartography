"""
Jamf CLI option definitions for cartography.
"""
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

PANEL = "Jamf Options"
MODULE_NAME = "jamf"

OPTION_DEFINITIONS: list[tuple[str, type, str, str, Any, dict[str, Any]]] = [
    (
        "jamf_base_uri",
        str | None,
        "--jamf-base-uri",
        "Jamf base URI, e.g. https://hostname.com/JSSResource.",
        None,
        {},
    ),
    (
        "jamf_user",
        str | None,
        "--jamf-user",
        "Username to authenticate to Jamf.",
        None,
        {},
    ),
    (
        "jamf_password_env_var",
        str | None,
        "--jamf-password-env-var",
        "Environment variable name containing Jamf password.",
        None,
        {},
    ),
]


def process_cli_args(args: dict[str, Any]) -> dict[str, Any]:
    """Process raw CLI argument values into Config-ready keyword arguments."""
    jamf_password = None
    if args.get("jamf_base_uri"):
        if args.get("jamf_user") and args.get("jamf_password_env_var"):
            logger.debug(
                "Reading password for Jamf from environment variable %s",
                args["jamf_password_env_var"],
            )
            jamf_password = os.environ.get(args["jamf_password_env_var"])
        if not args.get("jamf_user"):
            logger.warning("A Jamf base URI was provided but a user was not.")
        if args.get("jamf_user") and not jamf_password:
            logger.warning("A Jamf password could not be found.")

    return {
        "jamf_base_uri": args.get("jamf_base_uri"),
        "jamf_user": args.get("jamf_user"),
        "jamf_password": jamf_password,
    }
