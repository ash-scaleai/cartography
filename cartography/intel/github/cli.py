"""
GitHub CLI option definitions for cartography.
"""
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

PANEL = "GitHub Options"
MODULE_NAME = "github"

OPTION_DEFINITIONS: list[tuple[str, type, str, str, Any, dict[str, Any]]] = [
    (
        "github_config_env_var",
        str | None,
        "--github-config-env-var",
        "Environment variable name containing Base64 encoded GitHub config.",
        None,
        {},
    ),
    (
        "github_commit_lookback_days",
        int,
        "--github-commit-lookback-days",
        "Number of days to look back for GitHub commit tracking. Default: 30.",
        30,
        {},
    ),
]


def process_cli_args(args: dict[str, Any]) -> dict[str, Any]:
    """Process raw CLI argument values into Config-ready keyword arguments."""
    config_kwargs: dict[str, Any] = {}

    github_config = None
    if args.get("github_config_env_var"):
        logger.debug(
            "Reading config for GitHub from environment variable %s",
            args["github_config_env_var"],
        )
        github_config = os.environ.get(args["github_config_env_var"])

    config_kwargs["github_config"] = github_config
    config_kwargs["github_commit_lookback_days"] = args.get("github_commit_lookback_days", 30)

    return config_kwargs
