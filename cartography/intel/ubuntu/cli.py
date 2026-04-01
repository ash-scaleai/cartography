"""
Ubuntu Security CLI option definitions for cartography.
"""
import logging
from typing import Any

logger = logging.getLogger(__name__)

PANEL = "Ubuntu Security Options"
MODULE_NAME = "ubuntu"

OPTION_DEFINITIONS: list[tuple[str, type, str, str, Any, dict[str, Any]]] = [
    (
        "ubuntu_security_enabled",
        bool,
        "--ubuntu-security-enabled",
        "Enable Ubuntu Security CVE and Notice ingestion.",
        False,
        {},
    ),
    (
        "ubuntu_security_api_url",
        str | None,
        "--ubuntu-security-api-url",
        "Ubuntu Security API base URL. Defaults to https://ubuntu.com.",
        None,
        {},
    ),
]


def process_cli_args(args: dict[str, Any]) -> dict[str, Any]:
    """Process raw CLI argument values into Config-ready keyword arguments."""
    return {
        "ubuntu_security_enabled": args.get("ubuntu_security_enabled", False),
        "ubuntu_security_api_url": args.get("ubuntu_security_api_url"),
    }
