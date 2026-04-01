"""
GitLab CLI option definitions for cartography.
"""
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

PANEL = "GitLab Options"
MODULE_NAME = "gitlab"

OPTION_DEFINITIONS: list[tuple[str, type, str, str, Any, dict[str, Any]]] = [
    (
        "gitlab_url",
        str,
        "--gitlab-url",
        "GitLab instance URL. Defaults to https://gitlab.com.",
        "https://gitlab.com",
        {},
    ),
    (
        "gitlab_token_env_var",
        str | None,
        "--gitlab-token-env-var",
        "Environment variable name containing GitLab personal access token.",
        None,
        {},
    ),
    (
        "gitlab_organization_id",
        int | None,
        "--gitlab-organization-id",
        "GitLab organization (top-level group) ID to sync.",
        None,
        {},
    ),
    (
        "gitlab_commits_since_days",
        int,
        "--gitlab-commits-since-days",
        "Number of days of commit history to fetch. Default: 90.",
        90,
        {},
    ),
]


def process_cli_args(args: dict[str, Any]) -> dict[str, Any]:
    """Process raw CLI argument values into Config-ready keyword arguments."""
    config_kwargs: dict[str, Any] = {}

    gitlab_token = None
    if args.get("gitlab_url") and args.get("gitlab_token_env_var"):
        logger.debug(
            "Reading GitLab token from environment variable %s",
            args["gitlab_token_env_var"],
        )
        gitlab_token = os.environ.get(args["gitlab_token_env_var"])

    config_kwargs["gitlab_url"] = args.get("gitlab_url", "https://gitlab.com")
    config_kwargs["gitlab_token"] = gitlab_token
    config_kwargs["gitlab_organization_id"] = args.get("gitlab_organization_id")
    config_kwargs["gitlab_commits_since_days"] = args.get("gitlab_commits_since_days", 90)

    return config_kwargs
