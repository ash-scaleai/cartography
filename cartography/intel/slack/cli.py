"""
Slack CLI option definitions for cartography.
"""
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

PANEL = "Slack Options"
MODULE_NAME = "slack"

OPTION_DEFINITIONS: list[tuple[str, type, str, str, Any, dict[str, Any]]] = [
    (
        "slack_token_env_var",
        str | None,
        "--slack-token-env-var",
        "Environment variable name containing Slack token.",
        None,
        {},
    ),
    (
        "slack_teams",
        str | None,
        "--slack-teams",
        "Comma-separated list of Slack Team IDs to sync.",
        None,
        {},
    ),
    (
        "slack_channels_memberships",
        bool,
        "--slack-channels-memberships",
        "Pull memberships for Slack channels (can be time consuming).",
        False,
        {},
    ),
]


def process_cli_args(args: dict[str, Any]) -> dict[str, Any]:
    """Process raw CLI argument values into Config-ready keyword arguments."""
    slack_token = None
    if args.get("slack_token_env_var"):
        logger.debug(
            "Reading Slack token from environment variable %s",
            args["slack_token_env_var"],
        )
        slack_token = os.environ.get(args["slack_token_env_var"])

    return {
        "slack_token": slack_token,
        "slack_teams": args.get("slack_teams"),
        "slack_channels_memberships": args.get("slack_channels_memberships", False),
    }
