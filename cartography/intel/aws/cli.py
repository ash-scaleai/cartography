"""
AWS CLI option definitions for cartography.

This module defines all AWS-specific command-line options and the logic
to process them into Config-compatible keyword arguments. It serves both
the Typer-based CLI (Phase 0.3) and the plugin registry (Feature 4).
"""
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

PANEL = "AWS Options"
MODULE_NAME = "aws"

# Each entry: (param_name, type, cli_flag, help_text, default, extra_kwargs)
# extra_kwargs is a dict of additional typer.Option() keyword arguments.
OPTION_DEFINITIONS: list[tuple[str, type, str, str, Any, dict[str, Any]]] = [
    (
        "aws_sync_all_profiles",
        bool,
        "--aws-sync-all-profiles",
        (
            "Enable AWS sync for all discovered named profiles. "
            "Cartography will discover all configured AWS named profiles and run the AWS sync "
            'for each profile not named "default".'
        ),
        False,
        {},
    ),
    (
        "aws_regions",
        str | None,
        "--aws-regions",
        (
            "[EXPERIMENTAL] Comma-separated list of AWS regions to sync. "
            'Example: "us-east-1,us-east-2". '
            "CAUTION: Previously synced regions not in this list will have their assets deleted."
        ),
        None,
        {},
    ),
    (
        "aws_best_effort_mode",
        bool,
        "--aws-best-effort-mode",
        "Continue syncing other accounts if one fails, raising exceptions at the end.",
        False,
        {},
    ),
    (
        "aws_cloudtrail_management_events_lookback_hours",
        int | None,
        "--aws-cloudtrail-management-events-lookback-hours",
        "Number of hours back to retrieve CloudTrail management events. Not retrieved if not specified.",
        None,
        {},
    ),
    (
        "aws_requested_syncs",
        str | None,
        "--aws-requested-syncs",
        (
            "Comma-separated list of AWS resources to sync. "
            'Example: "ecr,s3,ec2:instance". See cartography.intel.aws.resources for full list.'
        ),
        None,
        {},
    ),
    (
        "aws_guardduty_severity_threshold",
        str | None,
        "--aws-guardduty-severity-threshold",
        "GuardDuty severity threshold. Valid values: LOW, MEDIUM, HIGH, CRITICAL.",
        None,
        {},
    ),
    (
        "experimental_aws_inspector_batch",
        int,
        "--experimental-aws-inspector-batch",
        "[EXPERIMENTAL] Batch size for AWS Inspector findings sync. Default: 1000.",
        1000,
        {},
    ),
    (
        "aws_tagging_api_cleanup_batch",
        int,
        "--aws-tagging-api-cleanup-batch",
        "Batch size for Resource Groups Tagging API cleanup (AWSTag nodes). Default: 1000.",
        1000,
        {},
    ),
    (
        "permission_relationships_file",
        str,
        "--permission-relationships-file",
        "Path to the AWS permission relationships mapping file.",
        "cartography/data/permission_relationships.yaml",
        {},
    ),
]


def add_arguments(params: list, visible_panels: set[str]) -> None:
    """
    Add AWS-specific CLI options to a Click command's params list.

    Used by the CLI plugin registry for dynamic provider discovery.

    Args:
        params: The Click command's params list to append to.
        visible_panels: Set of panel names that should be visible in --help.
    """
    try:
        import click
    except ImportError:
        return

    hidden = PANEL not in visible_panels

    for param_name, _, cli_flag, help_text, default, _ in OPTION_DEFINITIONS:
        is_flag = isinstance(default, bool)
        params.append(
            click.Option(
                [cli_flag],
                is_flag=is_flag,
                default=default,
                help=help_text,
                hidden=hidden,
            ),
        )


def process_cli_args(args: dict[str, Any]) -> dict[str, Any]:
    """
    Process raw CLI argument values into Config-ready keyword arguments.

    Performs validation and env-var reading for AWS-specific options.

    Args:
        args: Dictionary of raw CLI argument values (param_name -> value).

    Returns:
        Dictionary of keyword arguments to pass to Config constructor.
    """
    config_kwargs: dict[str, Any] = {}

    # Validate AWS requested syncs
    if args.get("aws_requested_syncs"):
        from cartography.intel.aws.util.common import (
            parse_and_validate_aws_requested_syncs,
        )
        parse_and_validate_aws_requested_syncs(args["aws_requested_syncs"])

    # Validate AWS regions
    if args.get("aws_regions"):
        from cartography.intel.aws.util.common import (
            parse_and_validate_aws_regions,
        )
        parse_and_validate_aws_regions(args["aws_regions"])

    # Pass through all AWS options directly
    config_kwargs["aws_sync_all_profiles"] = args.get("aws_sync_all_profiles", False)
    config_kwargs["aws_regions"] = args.get("aws_regions")
    config_kwargs["aws_best_effort_mode"] = args.get("aws_best_effort_mode", False)
    config_kwargs["aws_cloudtrail_management_events_lookback_hours"] = args.get(
        "aws_cloudtrail_management_events_lookback_hours",
    )
    config_kwargs["experimental_aws_inspector_batch"] = args.get(
        "experimental_aws_inspector_batch", 1000,
    )
    config_kwargs["aws_tagging_api_cleanup_batch"] = args.get(
        "aws_tagging_api_cleanup_batch", 1000,
    )
    config_kwargs["aws_requested_syncs"] = args.get("aws_requested_syncs")
    config_kwargs["aws_guardduty_severity_threshold"] = args.get(
        "aws_guardduty_severity_threshold",
    )
    config_kwargs["permission_relationships_file"] = args.get(
        "permission_relationships_file",
        "cartography/data/permission_relationships.yaml",
    )

    return config_kwargs
