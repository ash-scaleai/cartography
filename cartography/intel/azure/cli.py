"""
Azure CLI option definitions for cartography.

This module defines all Azure-specific command-line options and the logic
to process them into Config-compatible keyword arguments.
"""
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

PANEL = "Azure Options"
MODULE_NAME = "azure"

OPTION_DEFINITIONS: list[tuple[str, type, str, str, Any, dict[str, Any]]] = [
    (
        "azure_sync_all_subscriptions",
        bool,
        "--azure-sync-all-subscriptions",
        "Enable Azure sync for all discovered subscriptions.",
        False,
        {},
    ),
    (
        "azure_sp_auth",
        bool,
        "--azure-sp-auth",
        "Use Service Principal authentication for Azure sync.",
        False,
        {},
    ),
    (
        "azure_tenant_id",
        str | None,
        "--azure-tenant-id",
        "Azure Tenant ID for Service Principal Authentication.",
        None,
        {},
    ),
    (
        "azure_client_id",
        str | None,
        "--azure-client-id",
        "Azure Client ID for Service Principal Authentication.",
        None,
        {},
    ),
    (
        "azure_client_secret_env_var",
        str | None,
        "--azure-client-secret-env-var",
        "Environment variable name containing Azure Client Secret.",
        None,
        {},
    ),
    (
        "azure_subscription_id",
        str | None,
        "--azure-subscription-id",
        "The Azure Subscription ID to sync.",
        None,
        {},
    ),
    (
        "azure_permission_relationships_file",
        str,
        "--azure-permission-relationships-file",
        "Path to the Azure permission relationships mapping file.",
        "cartography/data/azure_permission_relationships.yaml",
        {},
    ),
]


def process_cli_args(args: dict[str, Any]) -> dict[str, Any]:
    """
    Process raw CLI argument values into Config-ready keyword arguments.

    Args:
        args: Dictionary of raw CLI argument values.

    Returns:
        Dictionary of keyword arguments to pass to Config constructor.
    """
    config_kwargs: dict[str, Any] = {}

    # Read Azure client secret from environment
    azure_client_secret = None
    if args.get("azure_sp_auth") and args.get("azure_client_secret_env_var"):
        logger.debug(
            "Reading Client Secret for Azure from environment variable %s",
            args["azure_client_secret_env_var"],
        )
        azure_client_secret = os.environ.get(args["azure_client_secret_env_var"])

    config_kwargs["azure_sync_all_subscriptions"] = args.get("azure_sync_all_subscriptions", False)
    config_kwargs["azure_sp_auth"] = args.get("azure_sp_auth", False)
    config_kwargs["azure_tenant_id"] = args.get("azure_tenant_id")
    config_kwargs["azure_client_id"] = args.get("azure_client_id")
    config_kwargs["azure_client_secret"] = azure_client_secret
    config_kwargs["azure_subscription_id"] = args.get("azure_subscription_id")
    config_kwargs["azure_permission_relationships_file"] = args.get(
        "azure_permission_relationships_file",
        "cartography/data/azure_permission_relationships.yaml",
    )

    return config_kwargs
