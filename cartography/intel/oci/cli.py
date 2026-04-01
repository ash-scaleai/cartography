"""
OCI CLI option definitions for cartography.
"""
import logging
from typing import Any

logger = logging.getLogger(__name__)

PANEL = "OCI Options"
MODULE_NAME = "oci"

OPTION_DEFINITIONS: list[tuple[str, type, str, str, Any, dict[str, Any]]] = [
    (
        "oci_sync_all_profiles",
        bool,
        "--oci-sync-all-profiles",
        'Enable OCI sync for all discovered named profiles (excluding "DEFAULT").',
        False,
        {},
    ),
]


def process_cli_args(args: dict[str, Any]) -> dict[str, Any]:
    """Process raw CLI argument values into Config-ready keyword arguments."""
    return {
        "oci_sync_all_profiles": args.get("oci_sync_all_profiles", False),
    }
