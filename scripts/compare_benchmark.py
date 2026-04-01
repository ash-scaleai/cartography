#!/usr/bin/env python3
"""
Head-to-head benchmark: original (sequential) vs redesign (concurrent).

Spins up a fresh Neo4j for each run, syncs the same 6 AWS accounts,
and prints per-account and total timing comparisons.
"""
import asyncio
import json
import logging
import os
import subprocess
import sys
import time

import boto3
import neo4j

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ─── Configuration ───────────────────────────────────────────────────────────

NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "cartography-bench"
NEO4J_DATABASE = "neo4j"
AWS_REQUESTED_SYNCS = "iam,s3,ec2:instance,ec2:security_groups,ec2:vpc"

PROFILES = {
    "staging-admin": "562655106659",
    "sgp-staging-audit": "339712937434",
    "sgp-dev-audit": "202533533296",
    "sgp-sandbox-1-audit": "204726797455",
    "sgp-sandbox-2-audit": "274363548746",
    "disposable-testing-env-audit": "901588369155",
}

# ─── Neo4j lifecycle ─────────────────────────────────────────────────────────

def start_neo4j(name, port):
    """Start a fresh Neo4j container, wait for it to be ready."""
    print(f"\n  Starting Neo4j '{name}' on port {port}...")
    subprocess.run(
        ["docker", "rm", "-f", name],
        capture_output=True,
    )
    subprocess.run([
        "docker", "run", "-d",
        "--name", name,
        "-p", f"{port}:7687",
        "-e", f"NEO4J_AUTH={NEO4J_USER}/{NEO4J_PASSWORD}",
        "-e", "NEO4J_PLUGINS=[\"apoc\"]",
        "neo4j:5-community",
    ], check=True, capture_output=True)

    uri = f"bolt://localhost:{port}"
    # Wait for Neo4j to be ready
    for attempt in range(30):
        try:
            driver = neo4j.GraphDatabase.driver(uri, auth=(NEO4J_USER, NEO4J_PASSWORD))
            driver.verify_connectivity()
            print(f"  Neo4j '{name}' ready on {uri}")
            return driver, uri
        except Exception:
            time.sleep(2)
    raise RuntimeError(f"Neo4j '{name}' failed to start")


def stop_neo4j(name, driver):
    """Stop and remove Neo4j container."""
    try:
        driver.close()
    except Exception:
        pass
    subprocess.run(["docker", "rm", "-f", name], capture_output=True)
    print(f"  Neo4j '{name}' stopped and removed.")


# ─── Sync one account ────────────────────────────────────────────────────────

def sync_one_account(profile_name, account_id, neo4j_driver, label=""):
    """Sync a single AWS account. Returns (account_id, elapsed_seconds, success)."""
    import cartography.intel.aws as aws_module
    from cartography.intel.aws.resources import RESOURCE_FUNCTIONS

    # Ensure event loop for threads (S3 uses asyncio internally)
    try:
        asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    start = time.time()
    success = True
    print(f"    {label}[START] {account_id} ({profile_name})", flush=True)

    try:
        boto3_session = boto3.Session(profile_name=profile_name)
        update_tag = int(time.time())
        common_job_parameters = {"UPDATE_TAG": update_tag, "AWS_ID": account_id}

        with neo4j_driver.session(database=NEO4J_DATABASE) as neo4j_session:
            regions = aws_module.ec2.get_ec2_regions(boto3_session)
            requested = [r.strip() for r in AWS_REQUESTED_SYNCS.split(",")]

            sync_args = {
                "neo4j_session": neo4j_session,
                "boto3_session": boto3_session,
                "regions": regions,
                "current_aws_account_id": account_id,
                "update_tag": update_tag,
                "common_job_parameters": common_job_parameters,
            }

            for func_name in RESOURCE_FUNCTIONS:
                if func_name not in requested:
                    continue
                try:
                    RESOURCE_FUNCTIONS[func_name](**sync_args)
                except Exception as e:
                    print(f"    {label}[WARN] {account_id}/{func_name}: {e}", flush=True)

    except Exception as e:
        print(f"    {label}[FAIL] {account_id}: {e}", flush=True)
        success = False

    elapsed = time.time() - start
    status = "OK" if success else "FAIL"
    print(f"    {label}[{status}] {account_id} ({profile_name}) = {elapsed:.1f}s", flush=True)
    return account_id, elapsed, success


# ─── Sequential run (original cartography behavior) ─────────────────────────

def run_sequential(neo4j_driver):
    """Run all accounts one at a time, like original cartography."""
    print("\n  Running accounts SEQUENTIALLY (original behavior)...")
    results = {}
    total_start = time.time()

    for profile_name, account_id in PROFILES.items():
        acct_id, elapsed, success = sync_one_account(
            profile_name, account_id, neo4j_driver, label="SEQ ",
        )
        results[acct_id] = elapsed

    total = time.time() - total_start
    return results, total


# ─── Concurrent run (redesign behavior) ─────────────────────────────────────

async def run_concurrent_async(neo4j_driver):
    """Run all accounts concurrently, like the redesign."""
    print("\n  Running accounts CONCURRENTLY (redesign behavior)...")
    total_start = time.time()

    async def _sync(profile_name, account_id):
        return await asyncio.to_thread(
            sync_one_account, profile_name, account_id, neo4j_driver, "PAR ",
        )

    tasks = [
        _sync(profile_name, account_id)
        for profile_name, account_id in PROFILES.items()
    ]
    raw_results = await asyncio.gather(*tasks, return_exceptions=True)

    results = {}
    for r in raw_results:
        if isinstance(r, tuple):
            acct_id, elapsed, success = r
            results[acct_id] = elapsed
        else:
            print(f"    [ERROR] {r}")

    total = time.time() - total_start
    return results, total


def run_concurrent(neo4j_driver):
    return asyncio.run(run_concurrent_async(neo4j_driver))


# ─── Main ────────────────────────────────────────────────────────────────────

def print_comparison(seq_results, seq_total, par_results, par_total):
    print(f"\n{'#'*72}")
    print(f"  COMPARISON: ORIGINAL (sequential) vs REDESIGN (concurrent)")
    print(f"{'#'*72}")

    print(f"\n  {'Account':<20} {'Original':>12} {'Redesign':>12} {'Diff':>10}")
    print(f"  {'─'*20} {'─'*12} {'─'*12} {'─'*10}")

    for profile_name, account_id in PROFILES.items():
        seq_t = seq_results.get(account_id, 0)
        par_t = par_results.get(account_id, 0)
        diff = seq_t - par_t
        print(f"  {profile_name:<20} {seq_t:>10.1f}s {par_t:>10.1f}s {diff:>+9.1f}s")

    seq_sum = sum(seq_results.values())
    par_sum = sum(par_results.values())

    print(f"\n  {'TOTAL (wall clock)':<20} {seq_total:>10.1f}s {par_total:>10.1f}s {seq_total - par_total:>+9.1f}s")
    print(f"  {'Sum of accounts':<20} {seq_sum:>10.1f}s {par_sum:>10.1f}s")
    print(f"\n  Speedup: {seq_total / par_total:.2f}x faster")
    print(f"  Time saved: {seq_total - par_total:.0f}s ({(seq_total - par_total) / 60:.1f} min)")
    print(f"{'#'*72}\n")


def main():
    print(f"\n{'='*72}")
    print(f"  CARTOGRAPHY: ORIGINAL vs REDESIGN BENCHMARK")
    print(f"  Accounts: {len(PROFILES)}")
    print(f"  Modules: {AWS_REQUESTED_SYNCS}")
    print(f"{'='*72}")

    # ── Phase 1: Sequential (original) ──
    print(f"\n{'='*72}")
    print(f"  PHASE 1: ORIGINAL (sequential)")
    print(f"{'='*72}")
    driver_seq, uri_seq = start_neo4j("neo4j-seq", 7688)
    seq_results, seq_total = run_sequential(driver_seq)
    stop_neo4j("neo4j-seq", driver_seq)

    print(f"\n  Original total: {seq_total:.1f}s")

    # ── Phase 2: Concurrent (redesign) ──
    print(f"\n{'='*72}")
    print(f"  PHASE 2: REDESIGN (concurrent)")
    print(f"{'='*72}")
    driver_par, uri_par = start_neo4j("neo4j-par", 7689)
    par_results, par_total = run_concurrent(driver_par)
    stop_neo4j("neo4j-par", driver_par)

    print(f"\n  Redesign total: {par_total:.1f}s")

    # ── Comparison ──
    print_comparison(seq_results, seq_total, par_results, par_total)


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
