"""
CrowdStrike CLI option definitions for cartography.
"""
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

PANEL = "CrowdStrike Options"
MODULE_NAME = "crowdstrike"

OPTION_DEFINITIONS: list[tuple[str, type, str, str, Any, dict[str, Any]]] = [
    (
        "crowdstrike_client_id_env_var",
        str | None,
        "--crowdstrike-client-id-env-var",
        "Environment variable name containing CrowdStrike client ID.",
        None,
        {},
    ),
    (
        "crowdstrike_client_secret_env_var",
        str | None,
        "--crowdstrike-client-secret-env-var",
        "Environment variable name containing CrowdStrike client secret.",
        None,
        {},
    ),
    (
        "crowdstrike_api_url",
        str | None,
        "--crowdstrike-api-url",
        "CrowdStrike API URL for self-hosted instances.",
        None,
        {},
    ),
]


def process_cli_args(args: dict[str, Any]) -> dict[str, Any]:
    """Process raw CLI argument values into Config-ready keyword arguments."""
    crowdstrike_client_id = None
    if args.get("crowdstrike_client_id_env_var"):
        logger.debug(
            "Reading client ID for CrowdStrike from environment variable %s",
            args["crowdstrike_client_id_env_var"],
        )
        crowdstrike_client_id = os.environ.get(args["crowdstrike_client_id_env_var"])

    crowdstrike_client_secret = None
    if args.get("crowdstrike_client_secret_env_var"):
        logger.debug(
            "Reading client secret for CrowdStrike from environment variable %s",
            args["crowdstrike_client_secret_env_var"],
        )
        crowdstrike_client_secret = os.environ.get(args["crowdstrike_client_secret_env_var"])

    return {
        "crowdstrike_client_id": crowdstrike_client_id,
        "crowdstrike_client_secret": crowdstrike_client_secret,
        "crowdstrike_api_url": args.get("crowdstrike_api_url"),
    }
