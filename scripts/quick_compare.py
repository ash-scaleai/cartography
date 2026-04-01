#!/usr/bin/env python3
"""Quick 1-account comparison: sequential vs concurrent (within-account modules)."""
import asyncio
import logging
import os
import subprocess
import sys
import time

import boto3
import neo4j

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "benchmark-test"
NEO4J_DB = "neo4j"
PROFILE = "sgp-sandbox-1-audit"
ACCOUNT_ID = "204726797455"
SYNCS = ["iam", "s3", "ec2:instance", "ec2:security_groups", "ec2:vpc"]


def start_neo4j(name, port):
    subprocess.run(["docker", "rm", "-f", name], capture_output=True)
    subprocess.run([
        "docker", "run", "-d", "--name", name,
        "-p", f"{port}:7687",
        "-e", f"NEO4J_AUTH={NEO4J_USER}/{NEO4J_PASSWORD}",
        "-e", "NEO4J_PLUGINS=[\"apoc\"]",
        "neo4j:5-community",
    ], check=True, capture_output=True)
    uri = f"bolt://localhost:{port}"
    for _ in range(30):
        try:
            d = neo4j.GraphDatabase.driver(uri, auth=(NEO4J_USER, NEO4J_PASSWORD))
            d.verify_connectivity()
            return d
        except Exception:
            time.sleep(2)
    raise RuntimeError("Neo4j didn't start")


def stop_neo4j(name, driver):
    driver.close()
    subprocess.run(["docker", "rm", "-f", name], capture_output=True)


def sync_module(func_name, sync_args):
    """Sync one module, return (name, elapsed)."""
    start = time.time()
    from cartography.intel.aws.resources import RESOURCE_FUNCTIONS
    try:
        RESOURCE_FUNCTIONS[func_name](**sync_args)
    except Exception as e:
        print(f"    [WARN] {func_name}: {e}")
    return func_name, time.time() - start


def run_sequential(driver):
    """Original: sync modules one at a time."""
    import cartography.intel.aws as aws_module
    from cartography.intel.aws.resources import RESOURCE_FUNCTIONS

    try:
        asyncio.get_event_loop()
    except RuntimeError:
        asyncio.set_event_loop(asyncio.new_event_loop())

    boto3_session = boto3.Session(profile_name=PROFILE)
    update_tag = int(time.time())
    common_job_parameters = {"UPDATE_TAG": update_tag, "AWS_ID": ACCOUNT_ID}

    with driver.session(database=NEO4J_DB) as neo4j_session:
        regions = aws_module.ec2.get_ec2_regions(boto3_session)
        sync_args = {
            "neo4j_session": neo4j_session,
            "boto3_session": boto3_session,
            "regions": regions,
            "current_aws_account_id": ACCOUNT_ID,
            "update_tag": update_tag,
            "common_job_parameters": common_job_parameters,
        }

        results = {}
        total_start = time.time()
        for func_name in RESOURCE_FUNCTIONS:
            if func_name not in SYNCS:
                continue
            name, elapsed = sync_module(func_name, sync_args)
            results[name] = elapsed
            print(f"    SEQ {name}: {elapsed:.1f}s", flush=True)

        total = time.time() - total_start
    return results, total


async def run_concurrent_async(driver):
    """Redesign: sync independent modules concurrently."""
    import cartography.intel.aws as aws_module
    from cartography.intel.aws.resources import RESOURCE_FUNCTIONS

    boto3_session = boto3.Session(profile_name=PROFILE)
    update_tag = int(time.time())
    common_job_parameters = {"UPDATE_TAG": update_tag, "AWS_ID": ACCOUNT_ID}

    with driver.session(database=NEO4J_DB) as neo4j_session:
        regions = aws_module.ec2.get_ec2_regions(boto3_session)
        sync_args = {
            "neo4j_session": neo4j_session,
            "boto3_session": boto3_session,
            "regions": regions,
            "current_aws_account_id": ACCOUNT_ID,
            "update_tag": update_tag,
            "common_job_parameters": common_job_parameters,
        }

        # Group: IAM is independent, EC2 modules depend on each other,
        # S3 is independent. Run IAM + S3 + EC2-group concurrently.
        async def _sync(name):
            try:
                asyncio.get_event_loop()
            except RuntimeError:
                asyncio.set_event_loop(asyncio.new_event_loop())
            return await asyncio.to_thread(sync_module, name, sync_args)

        total_start = time.time()

        # Wave 1: IAM, S3, and EC2 VPC run concurrently
        wave1_names = ["iam", "s3", "ec2:vpc"]
        wave1 = await asyncio.gather(*[_sync(n) for n in wave1_names])
        wave1_results = {name: elapsed for name, elapsed in wave1}
        for name, elapsed in wave1:
            print(f"    PAR {name}: {elapsed:.1f}s (wave 1)", flush=True)

        # Wave 2: EC2 security groups + instances (can run after VPC)
        wave2_names = ["ec2:security_groups", "ec2:instance"]
        wave2 = await asyncio.gather(*[_sync(n) for n in wave2_names])
        wave2_results = {name: elapsed for name, elapsed in wave2}
        for name, elapsed in wave2:
            print(f"    PAR {name}: {elapsed:.1f}s (wave 2)", flush=True)

        total = time.time() - total_start
        results = {**wave1_results, **wave2_results}
    return results, total


def main():
    print(f"\n{'='*60}")
    print(f"  QUICK COMPARE: {PROFILE} ({ACCOUNT_ID})")
    print(f"  Modules: {', '.join(SYNCS)}")
    print(f"{'='*60}")

    # Sequential
    print(f"\n--- ORIGINAL (sequential) ---")
    d1 = start_neo4j("neo4j-seq", 7688)
    seq_results, seq_total = run_sequential(d1)
    stop_neo4j("neo4j-seq", d1)

    # Concurrent
    print(f"\n--- REDESIGN (concurrent waves) ---")
    d2 = start_neo4j("neo4j-par", 7689)
    par_results, par_total = asyncio.run(run_concurrent_async(d2))
    stop_neo4j("neo4j-par", d2)

    # Comparison
    print(f"\n{'#'*60}")
    print(f"  RESULTS: {PROFILE}")
    print(f"{'#'*60}")
    print(f"\n  {'Module':<22} {'Original':>10} {'Redesign':>10}")
    print(f"  {'─'*22} {'─'*10} {'─'*10}")
    for mod in SYNCS:
        s = seq_results.get(mod, 0)
        p = par_results.get(mod, 0)
        print(f"  {mod:<22} {s:>8.1f}s {p:>8.1f}s")
    print(f"  {'─'*22} {'─'*10} {'─'*10}")
    print(f"  {'TOTAL (wall clock)':<22} {seq_total:>8.1f}s {par_total:>8.1f}s")
    print(f"\n  Speedup: {seq_total / par_total:.2f}x")
    print(f"  Time saved: {seq_total - par_total:.0f}s")
    print(f"{'#'*60}\n")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-7s [%(name)s] %(message)s",
        datefmt="%H:%M:%S",
    )
    logging.getLogger("neo4j").setLevel(logging.WARNING)
    logging.getLogger("botocore").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    main()
