"""
Semgrep CLI option definitions for cartography.
"""
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

PANEL = "Semgrep Options"
MODULE_NAME = "semgrep"

OPTION_DEFINITIONS: list[tuple[str, type, str, str, Any, dict[str, Any]]] = [
    (
        "semgrep_app_token_env_var",
        str | None,
        "--semgrep-app-token-env-var",
        "Environment variable name containing Semgrep app token.",
        None,
        {},
    ),
    (
        "semgrep_dependency_ecosystems",
        str | None,
        "--semgrep-dependency-ecosystems",
        'Comma-separated list of ecosystems for Semgrep dependencies. Example: "gomod,npm".',
        None,
        {},
    ),
]


def process_cli_args(args: dict[str, Any]) -> dict[str, Any]:
    """Process raw CLI argument values into Config-ready keyword arguments."""
    semgrep_app_token = None
    if args.get("semgrep_app_token_env_var"):
        logger.debug(
            "Reading Semgrep app token from environment variable %s",
            args["semgrep_app_token_env_var"],
        )
        semgrep_app_token = os.environ.get(args["semgrep_app_token_env_var"])

    if args.get("semgrep_dependency_ecosystems"):
        from cartography.intel.semgrep.dependencies import (
            parse_and_validate_semgrep_ecosystems,
        )
        parse_and_validate_semgrep_ecosystems(args["semgrep_dependency_ecosystems"])

    return {
        "semgrep_app_token": semgrep_app_token,
        "semgrep_dependency_ecosystems": args.get("semgrep_dependency_ecosystems"),
    }
