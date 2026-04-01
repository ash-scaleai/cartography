#!/usr/bin/env python3
"""
Refresh contract-test cassettes by recording live API responses.

This script is a **stub / documentation template**. It shows how to use the
CassetteRecorder to capture fresh provider API responses and write them to
the fixtures directory. Actual execution requires valid provider credentials.

Usage
-----
1.  Configure provider credentials in your environment (e.g., AWS_PROFILE,
    GITHUB_TOKEN, GOOGLE_APPLICATION_CREDENTIALS).

2.  Uncomment and adapt the sections below for the modules you want to
    refresh.

3.  Run::

        python scripts/refresh_cassettes.py

4.  Review the generated JSON files in ``cartography/testing/fixtures/``,
    ensure no secrets leaked into the response data, then commit.

Design notes
------------
*   Cassette refresh is **manual** — it is never run automatically in CI.
*   Each cassette captures the raw API response shape so that contract tests
    can detect field removals and type changes.
*   Sanitize responses before committing: strip account IDs, tokens, and
    any PII.
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

# Ensure the repo root is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cartography.testing.cassette import CassetteRecorder  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "cartography" / "testing" / "fixtures"


def refresh_ec2_instances() -> None:
    """Example: record EC2 DescribeInstances responses."""
    # import boto3
    # session = boto3.session.Session()
    # client = session.client("ec2", region_name="us-east-1")
    # paginator = client.get_paginator("describe_instances")
    # all_instances = []
    # for page in paginator.paginate():
    #     for reservation in page["Reservations"]:
    #         all_instances.extend(reservation["Instances"])
    #
    # recorder = CassetteRecorder(module_name="aws.ec2.instances")
    # recorder.record("describe_instances", all_instances)
    # recorder.save_all(FIXTURES_DIR)
    logger.info("ec2_instances: skipped (stub — uncomment to run with real credentials)")


def refresh_iam_users() -> None:
    """Example: record IAM ListUsers responses."""
    # import boto3
    # session = boto3.session.Session()
    # client = session.client("iam")
    # paginator = client.get_paginator("list_users")
    # users = []
    # for page in paginator.paginate():
    #     users.extend(page["Users"])
    #
    # recorder = CassetteRecorder(module_name="aws.iam.users")
    # recorder.record("list_users", users)
    # recorder.save_all(FIXTURES_DIR)
    logger.info("iam_users: skipped (stub — uncomment to run with real credentials)")


def refresh_s3_buckets() -> None:
    """Example: record S3 ListBuckets responses."""
    # import boto3
    # session = boto3.session.Session()
    # client = session.client("s3")
    # response = client.list_buckets()
    #
    # recorder = CassetteRecorder(module_name="aws.s3.buckets")
    # recorder.record("list_buckets", response["Buckets"])
    # recorder.save_all(FIXTURES_DIR)
    logger.info("s3_buckets: skipped (stub — uncomment to run with real credentials)")


def refresh_github_repos() -> None:
    """Example: record GitHub repos responses."""
    # import requests
    # token = os.environ["GITHUB_TOKEN"]
    # org = "my-org"
    # headers = {"Authorization": f"Bearer {token}"}
    # resp = requests.get(
    #     f"https://api.github.com/orgs/{org}/repos", headers=headers
    # )
    # repos = resp.json()
    #
    # recorder = CassetteRecorder(module_name="github.repos")
    # recorder.record("get_repos", repos)
    # recorder.save_all(FIXTURES_DIR)
    logger.info("github_repos: skipped (stub — uncomment to run with real credentials)")


def refresh_gcp_instances() -> None:
    """Example: record GCP Compute instances responses."""
    # from google.cloud import compute_v1
    # client = compute_v1.InstancesClient()
    # project = "my-project"
    # zone = "us-central1-a"
    # instances = list(client.list(project=project, zone=zone))
    #
    # recorder = CassetteRecorder(module_name="gcp.compute.instances")
    # recorder.record("instances_list", [inst._to_dict() for inst in instances])
    # recorder.save_all(FIXTURES_DIR)
    logger.info("gcp_instances: skipped (stub — uncomment to run with real credentials)")


if __name__ == "__main__":
    logger.info("Refreshing cassettes in %s", FIXTURES_DIR)
    refresh_ec2_instances()
    refresh_iam_users()
    refresh_s3_buckets()
    refresh_github_repos()
    refresh_gcp_instances()
    logger.info("Done. Review generated files before committing.")
