"""
Keycloak CLI option definitions for cartography.
"""
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

PANEL = "Keycloak Options"
MODULE_NAME = "keycloak"

OPTION_DEFINITIONS: list[tuple[str, type, str, str, Any, dict[str, Any]]] = [
    (
        "keycloak_client_id",
        str | None,
        "--keycloak-client-id",
        "Keycloak client ID to sync.",
        None,
        {},
    ),
    (
        "keycloak_client_secret_env_var",
        str,
        "--keycloak-client-secret-env-var",
        "Environment variable name containing Keycloak client secret.",
        "KEYCLOAK_CLIENT_SECRET",
        {},
    ),
    (
        "keycloak_url",
        str | None,
        "--keycloak-url",
        "Keycloak base URL.",
        None,
        {},
    ),
    (
        "keycloak_realm",
        str,
        "--keycloak-realm",
        "Keycloak realm for authentication (all realms will be synced).",
        "master",
        {},
    ),
]


def process_cli_args(args: dict[str, Any]) -> dict[str, Any]:
    """Process raw CLI argument values into Config-ready keyword arguments."""
    keycloak_client_secret = None
    if args.get("keycloak_client_secret_env_var"):
        logger.debug(
            "Reading Keycloak client secret from environment variable %s",
            args["keycloak_client_secret_env_var"],
        )
        keycloak_client_secret = os.environ.get(args["keycloak_client_secret_env_var"])

    return {
        "keycloak_client_id": args.get("keycloak_client_id"),
        "keycloak_client_secret": keycloak_client_secret,
        "keycloak_url": args.get("keycloak_url"),
        "keycloak_realm": args.get("keycloak_realm", "master"),
    }
