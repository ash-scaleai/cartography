"""
Syft CLI option definitions for cartography.
"""
import logging
from typing import Any

logger = logging.getLogger(__name__)

PANEL = "Syft Options"
MODULE_NAME = "syft"

OPTION_DEFINITIONS: list[tuple[str, type, str, str, Any, dict[str, Any]]] = [
    (
        "syft_s3_bucket",
        str | None,
        "--syft-s3-bucket",
        "S3 bucket name containing Syft scan results.",
        None,
        {},
    ),
    (
        "syft_s3_prefix",
        str | None,
        "--syft-s3-prefix",
        "S3 prefix path for Syft scan results.",
        None,
        {},
    ),
    (
        "syft_results_dir",
        str | None,
        "--syft-results-dir",
        "Local directory containing Syft JSON results.",
        None,
        {},
    ),
]


def process_cli_args(args: dict[str, Any]) -> dict[str, Any]:
    """Process raw CLI argument values into Config-ready keyword arguments."""
    if args.get("syft_s3_bucket"):
        logger.debug("Syft S3 bucket: %s", args["syft_s3_bucket"])
    if args.get("syft_s3_prefix"):
        logger.debug("Syft S3 prefix: %s", args["syft_s3_prefix"])
    if args.get("syft_results_dir"):
        logger.debug("Syft results dir: %s", args["syft_results_dir"])

    return {
        "syft_s3_bucket": args.get("syft_s3_bucket"),
        "syft_s3_prefix": args.get("syft_s3_prefix"),
        "syft_results_dir": args.get("syft_results_dir"),
    }
