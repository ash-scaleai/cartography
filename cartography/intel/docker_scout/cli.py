"""
Docker Scout CLI option definitions for cartography.
"""
import logging
from typing import Any

logger = logging.getLogger(__name__)

PANEL = "Docker Scout Options"
MODULE_NAME = "docker_scout"

OPTION_DEFINITIONS: list[tuple[str, type, str, str, Any, dict[str, Any]]] = [
    (
        "docker_scout_results_dir",
        str | None,
        "--docker-scout-results-dir",
        "Local directory containing Docker Scout recommendation text reports.",
        None,
        {},
    ),
    (
        "docker_scout_s3_bucket",
        str | None,
        "--docker-scout-s3-bucket",
        "S3 bucket name containing Docker Scout recommendation text reports.",
        None,
        {},
    ),
    (
        "docker_scout_s3_prefix",
        str | None,
        "--docker-scout-s3-prefix",
        "S3 prefix path for Docker Scout recommendation text reports.",
        None,
        {},
    ),
]


def process_cli_args(args: dict[str, Any]) -> dict[str, Any]:
    """Process raw CLI argument values into Config-ready keyword arguments."""
    if args.get("docker_scout_results_dir"):
        logger.debug("Docker Scout results dir: %s", args["docker_scout_results_dir"])
    if args.get("docker_scout_s3_bucket"):
        logger.debug("Docker Scout S3 bucket: %s", args["docker_scout_s3_bucket"])
    if args.get("docker_scout_s3_prefix"):
        logger.debug("Docker Scout S3 prefix: %s", args["docker_scout_s3_prefix"])

    return {
        "docker_scout_results_dir": args.get("docker_scout_results_dir"),
        "docker_scout_s3_bucket": args.get("docker_scout_s3_bucket"),
        "docker_scout_s3_prefix": args.get("docker_scout_s3_prefix"),
    }
