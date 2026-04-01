"""
SentinelOne CLI option definitions for cartography.
"""
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

PANEL = "SentinelOne Options"
MODULE_NAME = "sentinelone"

OPTION_DEFINITIONS: list[tuple[str, type, str, str, Any, dict[str, Any]]] = [
    (
        "sentinelone_account_ids",
        str | None,
        "--sentinelone-account-ids",
        "Comma-separated list of SentinelOne account IDs to sync.",
        None,
        {},
    ),
    (
        "sentinelone_site_ids",
        str | None,
        "--sentinelone-site-ids",
        "Comma-separated list of SentinelOne site IDs to sync.",
        None,
        {},
    ),
    (
        "sentinelone_api_url",
        str | None,
        "--sentinelone-api-url",
        "SentinelOne API URL.",
        None,
        {},
    ),
    (
        "sentinelone_api_token_env_var",
        str,
        "--sentinelone-api-token-env-var",
        "Environment variable name containing SentinelOne API token.",
        "SENTINELONE_API_TOKEN",
        {},
    ),
]


def process_cli_args(args: dict[str, Any]) -> dict[str, Any]:
    """Process raw CLI argument values into Config-ready keyword arguments."""
    # Parse account IDs
    sentinelone_account_ids_list = None
    if args.get("sentinelone_account_ids"):
        sentinelone_account_ids_list = [
            id.strip() for id in args["sentinelone_account_ids"].split(",")
        ]
        logger.debug(
            "Parsed %d SentinelOne account IDs to sync",
            len(sentinelone_account_ids_list),
        )

    # Parse site IDs
    sentinelone_site_ids_list = None
    if args.get("sentinelone_site_ids"):
        sentinelone_site_ids_list = [
            id.strip() for id in args["sentinelone_site_ids"].split(",")
        ]
        logger.debug(
            "Parsed %d SentinelOne site IDs to sync",
            len(sentinelone_site_ids_list),
        )

    # Read API token
    sentinelone_api_token = None
    if args.get("sentinelone_api_url") and args.get("sentinelone_api_token_env_var"):
        logger.debug(
            "Reading SentinelOne API token from environment variable %s",
            args["sentinelone_api_token_env_var"],
        )
        sentinelone_api_token = os.environ.get(args["sentinelone_api_token_env_var"])

    return {
        "sentinelone_api_url": args.get("sentinelone_api_url"),
        "sentinelone_api_token": sentinelone_api_token,
        "sentinelone_account_ids": sentinelone_account_ids_list,
        "sentinelone_site_ids": sentinelone_site_ids_list,
    }
