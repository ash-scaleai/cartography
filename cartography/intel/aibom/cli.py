"""
AIBOM CLI option definitions for cartography.
"""
import logging
from typing import Any

logger = logging.getLogger(__name__)

PANEL = "AIBOM Options"
MODULE_NAME = "aibom"

OPTION_DEFINITIONS: list[tuple[str, type, str, str, Any, dict[str, Any]]] = [
    (
        "aibom_s3_bucket",
        str | None,
        "--aibom-s3-bucket",
        "S3 bucket name containing AIBOM scan results.",
        None,
        {},
    ),
    (
        "aibom_s3_prefix",
        str | None,
        "--aibom-s3-prefix",
        "S3 prefix path for AIBOM scan results.",
        None,
        {},
    ),
    (
        "aibom_results_dir",
        str | None,
        "--aibom-results-dir",
        "Local directory containing AIBOM JSON results.",
        None,
        {},
    ),
]


def process_cli_args(args: dict[str, Any]) -> dict[str, Any]:
    """Process raw CLI argument values into Config-ready keyword arguments."""
    if args.get("aibom_s3_bucket"):
        logger.debug("AIBOM S3 bucket: %s", args["aibom_s3_bucket"])
    if args.get("aibom_s3_prefix"):
        logger.debug("AIBOM S3 prefix: %s", args["aibom_s3_prefix"])
    if args.get("aibom_results_dir"):
        logger.debug("AIBOM results dir: %s", args["aibom_results_dir"])

    return {
        "aibom_s3_bucket": args.get("aibom_s3_bucket"),
        "aibom_s3_prefix": args.get("aibom_s3_prefix"),
        "aibom_results_dir": args.get("aibom_results_dir"),
    }
