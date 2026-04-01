"""
Spacelift CLI option definitions for cartography.
"""
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

PANEL = "Spacelift Options"
MODULE_NAME = "spacelift"

OPTION_DEFINITIONS: list[tuple[str, type, str, str, Any, dict[str, Any]]] = [
    (
        "spacelift_api_endpoint",
        str | None,
        "--spacelift-api-endpoint",
        "Spacelift GraphQL API endpoint.",
        None,
        {},
    ),
    (
        "spacelift_api_token_env_var",
        str,
        "--spacelift-api-token-env-var",
        "Environment variable name containing Spacelift API token.",
        "SPACELIFT_API_TOKEN",
        {},
    ),
    (
        "spacelift_api_key_id_env_var",
        str,
        "--spacelift-api-key-id-env-var",
        "Environment variable name containing Spacelift API key ID.",
        "SPACELIFT_API_KEY_ID",
        {},
    ),
    (
        "spacelift_api_key_secret_env_var",
        str,
        "--spacelift-api-key-secret-env-var",
        "Environment variable name containing Spacelift API key secret.",
        "SPACELIFT_API_KEY_SECRET",
        {},
    ),
    (
        "spacelift_ec2_ownership_aws_profile",
        str | None,
        "--spacelift-ec2-ownership-aws-profile",
        "AWS profile for fetching EC2 ownership data from S3.",
        None,
        {},
    ),
    (
        "spacelift_ec2_ownership_s3_bucket",
        str | None,
        "--spacelift-ec2-ownership-s3-bucket",
        "S3 bucket for EC2 ownership CloudTrail data.",
        None,
        {},
    ),
    (
        "spacelift_ec2_ownership_s3_prefix",
        str | None,
        "--spacelift-ec2-ownership-s3-prefix",
        "S3 prefix for EC2 ownership CloudTrail data.",
        None,
        {},
    ),
]


def process_cli_args(args: dict[str, Any]) -> dict[str, Any]:
    """Process raw CLI argument values into Config-ready keyword arguments."""
    spacelift_api_endpoint_resolved = args.get("spacelift_api_endpoint")
    if not spacelift_api_endpoint_resolved:
        spacelift_api_endpoint_resolved = os.environ.get("SPACELIFT_API_ENDPOINT")

    spacelift_api_token = None
    spacelift_api_key_id = None
    spacelift_api_key_secret = None

    if spacelift_api_endpoint_resolved:
        if args.get("spacelift_api_token_env_var"):
            logger.debug(
                "Reading Spacelift API token from environment variable %s",
                args["spacelift_api_token_env_var"],
            )
            spacelift_api_token = os.environ.get(args["spacelift_api_token_env_var"])

        if args.get("spacelift_api_key_id_env_var"):
            logger.debug(
                "Reading Spacelift API key ID from environment variable %s",
                args["spacelift_api_key_id_env_var"],
            )
            spacelift_api_key_id = os.environ.get(args["spacelift_api_key_id_env_var"])

        if args.get("spacelift_api_key_secret_env_var"):
            logger.debug(
                "Reading Spacelift API key secret from environment variable %s",
                args["spacelift_api_key_secret_env_var"],
            )
            spacelift_api_key_secret = os.environ.get(args["spacelift_api_key_secret_env_var"])

    return {
        "spacelift_api_endpoint": spacelift_api_endpoint_resolved,
        "spacelift_api_token": spacelift_api_token,
        "spacelift_api_key_id": spacelift_api_key_id,
        "spacelift_api_key_secret": spacelift_api_key_secret,
        "spacelift_ec2_ownership_aws_profile": args.get("spacelift_ec2_ownership_aws_profile"),
        "spacelift_ec2_ownership_s3_bucket": args.get("spacelift_ec2_ownership_s3_bucket"),
        "spacelift_ec2_ownership_s3_prefix": args.get("spacelift_ec2_ownership_s3_prefix"),
    }
