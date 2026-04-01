"""
Trivy CLI option definitions for cartography.
"""
import logging
from typing import Any

logger = logging.getLogger(__name__)

PANEL = "Trivy Options"
MODULE_NAME = "trivy"

OPTION_DEFINITIONS: list[tuple[str, type, str, str, Any, dict[str, Any]]] = [
    (
        "trivy_s3_bucket",
        str | None,
        "--trivy-s3-bucket",
        "S3 bucket name containing Trivy scan results.",
        None,
        {},
    ),
    (
        "trivy_s3_prefix",
        str | None,
        "--trivy-s3-prefix",
        "S3 prefix path for Trivy scan results.",
        None,
        {},
    ),
    (
        "trivy_results_dir",
        str | None,
        "--trivy-results-dir",
        "Local directory containing Trivy JSON results.",
        None,
        {},
    ),
]


def process_cli_args(args: dict[str, Any]) -> dict[str, Any]:
    """Process raw CLI argument values into Config-ready keyword arguments."""
    if args.get("trivy_s3_bucket"):
        logger.debug("Trivy S3 bucket: %s", args["trivy_s3_bucket"])
    if args.get("trivy_s3_prefix"):
        logger.debug("Trivy S3 prefix: %s", args["trivy_s3_prefix"])
    if args.get("trivy_results_dir"):
        logger.debug("Trivy results dir: %s", args["trivy_results_dir"])

    return {
        "trivy_s3_bucket": args.get("trivy_s3_bucket"),
        "trivy_s3_prefix": args.get("trivy_s3_prefix"),
        "trivy_results_dir": args.get("trivy_results_dir"),
    }
