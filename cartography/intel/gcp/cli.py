"""
GCP CLI option definitions for cartography.
"""
import logging
from typing import Any

logger = logging.getLogger(__name__)

PANEL = "GCP Options"
MODULE_NAME = "gcp"

OPTION_DEFINITIONS: list[tuple[str, type, str, str, Any, dict[str, Any]]] = [
    (
        "gcp_requested_syncs",
        str | None,
        "--gcp-requested-syncs",
        (
            "Comma-separated list of GCP resources to sync. "
            'Example: "compute,iam,storage". See cartography.intel.gcp.resources for full list.'
        ),
        None,
        {},
    ),
    (
        "gcp_permission_relationships_file",
        str,
        "--gcp-permission-relationships-file",
        "Path to the GCP permission relationships mapping file.",
        "cartography/data/gcp_permission_relationships.yaml",
        {},
    ),
]


def process_cli_args(args: dict[str, Any]) -> dict[str, Any]:
    """Process raw CLI argument values into Config-ready keyword arguments."""
    config_kwargs: dict[str, Any] = {}

    if args.get("gcp_requested_syncs"):
        from cartography.intel.gcp.util import (
            parse_and_validate_gcp_requested_syncs,
        )
        parse_and_validate_gcp_requested_syncs(args["gcp_requested_syncs"])

    config_kwargs["gcp_requested_syncs"] = args.get("gcp_requested_syncs")
    config_kwargs["gcp_permission_relationships_file"] = args.get(
        "gcp_permission_relationships_file",
        "cartography/data/gcp_permission_relationships.yaml",
    )

    return config_kwargs
