"""
CVE CLI option definitions for cartography.
"""
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

PANEL = "CVE Options"
MODULE_NAME = "cve"

OPTION_DEFINITIONS: list[tuple[str, type, str, str, Any, dict[str, Any]]] = [
    (
        "nist_cve_url",
        str,
        "--nist-cve-url",
        "Base URL for NIST CVE data.",
        "https://services.nvd.nist.gov/rest/json/cves/2.0/",
        {},
    ),
    (
        "cve_enabled",
        bool,
        "--cve-enabled",
        "Enable CVE data sync from NIST.",
        False,
        {},
    ),
    (
        "cve_api_key_env_var",
        str | None,
        "--cve-api-key-env-var",
        "Environment variable name containing NIST NVD API v2.0 key.",
        None,
        {},
    ),
]


def process_cli_args(args: dict[str, Any]) -> dict[str, Any]:
    """Process raw CLI argument values into Config-ready keyword arguments."""
    cve_api_key = None
    if args.get("cve_api_key_env_var"):
        logger.debug(
            "Reading CVE API key from environment variable %s",
            args["cve_api_key_env_var"],
        )
        cve_api_key = os.environ.get(args["cve_api_key_env_var"])

    return {
        "nist_cve_url": args.get("nist_cve_url", "https://services.nvd.nist.gov/rest/json/cves/2.0/"),
        "cve_enabled": args.get("cve_enabled", False),
        "cve_api_key": cve_api_key,
    }
