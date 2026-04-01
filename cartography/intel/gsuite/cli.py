"""
GSuite CLI option definitions for cartography.
"""
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

PANEL = "GSuite Options"
MODULE_NAME = "gsuite"

OPTION_DEFINITIONS: list[tuple[str, type, str, str, Any, dict[str, Any]]] = [
    (
        "gsuite_auth_method",
        str,
        "--gsuite-auth-method",
        'GSuite authentication method: "delegated", "oauth", or "default".',
        "delegated",
        {},
    ),
    (
        "gsuite_tokens_env_var",
        str,
        "--gsuite-tokens-env-var",
        "Environment variable name containing GSuite credentials.",
        "GSUITE_GOOGLE_APPLICATION_CREDENTIALS",
        {},
    ),
]


def process_cli_args(args: dict[str, Any]) -> dict[str, Any]:
    """Process raw CLI argument values into Config-ready keyword arguments."""
    gsuite_config = None
    if args.get("gsuite_tokens_env_var"):
        logger.debug(
            "Reading config for GSuite from environment variable %s",
            args["gsuite_tokens_env_var"],
        )
        gsuite_config = os.environ.get(args["gsuite_tokens_env_var"])

    return {
        "gsuite_auth_method": args.get("gsuite_auth_method", "delegated"),
        "gsuite_config": gsuite_config,
    }
