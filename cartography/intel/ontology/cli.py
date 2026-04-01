"""
Ontology CLI option definitions for cartography.
"""
import logging
from typing import Any

logger = logging.getLogger(__name__)

PANEL = "Ontology Options"
MODULE_NAME = "ontology"

OPTION_DEFINITIONS: list[tuple[str, type, str, str, Any, dict[str, Any]]] = [
    (
        "ontology_users_source",
        str | None,
        "--ontology-users-source",
        "Comma-separated list of sources of truth for user data in the ontology.",
        None,
        {},
    ),
    (
        "ontology_devices_source",
        str | None,
        "--ontology-devices-source",
        "Comma-separated list of sources of truth for device data in the ontology.",
        None,
        {},
    ),
]


def process_cli_args(args: dict[str, Any]) -> dict[str, Any]:
    """Process raw CLI argument values into Config-ready keyword arguments."""
    return {
        "ontology_users_source": args.get("ontology_users_source"),
        "ontology_devices_source": args.get("ontology_devices_source"),
    }
