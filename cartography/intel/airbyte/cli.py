"""
Airbyte CLI option definitions for cartography.
"""
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

PANEL = "Airbyte Options"
MODULE_NAME = "airbyte"

OPTION_DEFINITIONS: list[tuple[str, type, str, str, Any, dict[str, Any]]] = [
    (
        "airbyte_client_id",
        str | None,
        "--airbyte-client-id",
        "Airbyte client ID for authentication.",
        None,
        {},
    ),
    (
        "airbyte_client_secret_env_var",
        str | None,
        "--airbyte-client-secret-env-var",
        "Environment variable name containing Airbyte client secret.",
        None,
        {},
    ),
    (
        "airbyte_api_url",
        str,
        "--airbyte-api-url",
        "Airbyte API base URL.",
        "https://api.airbyte.com/v1",
        {},
    ),
]


def process_cli_args(args: dict[str, Any]) -> dict[str, Any]:
    """Process raw CLI argument values into Config-ready keyword arguments."""
    airbyte_client_secret = None
    if args.get("airbyte_client_id") and args.get("airbyte_client_secret_env_var"):
        logger.debug(
            "Reading Airbyte client secret from environment variable %s",
            args["airbyte_client_secret_env_var"],
        )
        airbyte_client_secret = os.environ.get(args["airbyte_client_secret_env_var"])

    return {
        "airbyte_client_id": args.get("airbyte_client_id"),
        "airbyte_client_secret": airbyte_client_secret,
        "airbyte_api_url": args.get("airbyte_api_url", "https://api.airbyte.com/v1"),
    }
