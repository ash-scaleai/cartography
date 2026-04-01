"""
Entra ID CLI option definitions for cartography.
"""
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

PANEL = "Entra ID Options"
MODULE_NAME = "entra"

OPTION_DEFINITIONS: list[tuple[str, type, str, str, Any, dict[str, Any]]] = [
    (
        "entra_tenant_id",
        str | None,
        "--entra-tenant-id",
        "Entra Tenant ID for Service Principal Authentication.",
        None,
        {},
    ),
    (
        "entra_client_id",
        str | None,
        "--entra-client-id",
        "Entra Client ID for Service Principal Authentication.",
        None,
        {},
    ),
    (
        "entra_client_secret_env_var",
        str | None,
        "--entra-client-secret-env-var",
        "Environment variable name containing Entra Client Secret.",
        None,
        {},
    ),
]


def process_cli_args(args: dict[str, Any]) -> dict[str, Any]:
    """Process raw CLI argument values into Config-ready keyword arguments."""
    config_kwargs: dict[str, Any] = {}

    entra_client_secret = None
    if (
        args.get("entra_tenant_id")
        and args.get("entra_client_id")
        and args.get("entra_client_secret_env_var")
    ):
        logger.debug(
            "Reading Client Secret for Entra from environment variable %s",
            args["entra_client_secret_env_var"],
        )
        entra_client_secret = os.environ.get(args["entra_client_secret_env_var"])

    config_kwargs["entra_tenant_id"] = args.get("entra_tenant_id")
    config_kwargs["entra_client_id"] = args.get("entra_client_id")
    config_kwargs["entra_client_secret"] = entra_client_secret

    return config_kwargs
