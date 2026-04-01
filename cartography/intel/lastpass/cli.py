"""
LastPass CLI option definitions for cartography.
"""
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

PANEL = "LastPass Options"
MODULE_NAME = "lastpass"

OPTION_DEFINITIONS: list[tuple[str, type, str, str, Any, dict[str, Any]]] = [
    (
        "lastpass_cid_env_var",
        str | None,
        "--lastpass-cid-env-var",
        "Environment variable name containing LastPass CID.",
        None,
        {},
    ),
    (
        "lastpass_provhash_env_var",
        str | None,
        "--lastpass-provhash-env-var",
        "Environment variable name containing LastPass provhash.",
        None,
        {},
    ),
]


def process_cli_args(args: dict[str, Any]) -> dict[str, Any]:
    """Process raw CLI argument values into Config-ready keyword arguments."""
    lastpass_cid = None
    if args.get("lastpass_cid_env_var"):
        logger.debug(
            "Reading CID for LastPass from environment variable %s",
            args["lastpass_cid_env_var"],
        )
        lastpass_cid = os.environ.get(args["lastpass_cid_env_var"])

    lastpass_provhash = None
    if args.get("lastpass_provhash_env_var"):
        logger.debug(
            "Reading provhash for LastPass from environment variable %s",
            args["lastpass_provhash_env_var"],
        )
        lastpass_provhash = os.environ.get(args["lastpass_provhash_env_var"])

    return {
        "lastpass_cid": lastpass_cid,
        "lastpass_provhash": lastpass_provhash,
    }
