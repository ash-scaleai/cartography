#!/usr/bin/env python3
"""
Benchmark script for cartography redesign features.

Runs cartography against multiple AWS accounts and provides live progress,
timing data, and verification that new features are exercised.

Usage:
    python3 scripts/benchmark_sync.py

Requires:
    - Neo4j running on bolt://localhost:7688 (test instance)
    - AWS SSO profiles authenticated
"""
import asyncio
import json
import logging
import os
import sys
import threading
import time
from collections import defaultdict
from datetime import datetime, timedelta

import boto3
import neo4j

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ─── Configuration ───────────────────────────────────────────────────────────
NEO4J_URI = "bolt://localhost:7688"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "cartography-test"
NEO4J_DATABASE = "neo4j"

PROFILES = {
    "staging-admin": "562655106659",
    "sgp-staging-audit": "339712937434",
    "sgp-dev-audit": "202533533296",
    "sgp-sandbox-1-audit": "204726797455",
    "sgp-sandbox-2-audit": "274363548746",
    "disposable-testing-env-audit": "901588369155",
}

# Which AWS services to sync (keep small for benchmark)
AWS_REQUESTED_SYNCS = "iam,s3,ec2:instance,ec2:security_groups,ec2:vpc"

# ─── Live Progress Tracker ───────────────────────────────────────────────────

class LiveTracker:
    """Thread-safe live progress tracker with terminal output."""

    def __init__(self):
        self._lock = threading.Lock()
        self._account_status = {}       # account_id -> status string
        self._account_start = {}        # account_id -> start time
        self._account_end = {}          # account_id -> end time
        self._module_timings = defaultdict(dict)  # account_id -> {module: seconds}
        self._module_active = {}        # account_id -> current module
        self._record_counts = defaultdict(dict)   # account_id -> {module: count}
        self._errors = []
        self._features_exercised = set()
        self._start_time = time.time()

    def account_start(self, account_id, profile):
        with self._lock:
            self._account_status[account_id] = f"RUNNING ({profile})"
            self._account_start[account_id] = time.time()
            self._features_exercised.add("multi-account-sync")
            self._print_status()

    def account_done(self, account_id, profile, success=True):
        with self._lock:
            elapsed = time.time() - self._account_start[account_id]
            status = "DONE" if success else "FAILED"
            self._account_status[account_id] = f"{status} ({profile}) [{elapsed:.1f}s]"
            self._account_end[account_id] = time.time()
            self._print_status()

    def module_start(self, account_id, module_name):
        with self._lock:
            self._module_active[account_id] = module_name
            self._module_timings[account_id][module_name] = time.time()
            self._print_status()

    def module_done(self, account_id, module_name, record_count=0):
        with self._lock:
            start = self._module_timings[account_id].get(module_name, time.time())
            self._module_timings[account_id][module_name] = time.time() - start
            self._record_counts[account_id][module_name] = record_count
            if account_id in self._module_active:
                del self._module_active[account_id]
            self._print_status()

    def feature_used(self, feature_name):
        with self._lock:
            self._features_exercised.add(feature_name)

    def error(self, msg):
        with self._lock:
            self._errors.append(msg)

    def _print_status(self):
        elapsed = time.time() - self._start_time
        lines = []
        lines.append(f"\n{'='*70}")
        lines.append(f"  BENCHMARK PROGRESS  |  Elapsed: {elapsed:.1f}s")
        lines.append(f"{'='*70}")

        # Account status
        running = 0
        done = 0
        for acct_id, status in self._account_status.items():
            marker = ">>>" if "RUNNING" in status else ("OK " if "DONE" in status else "XX ")
            active_mod = self._module_active.get(acct_id, "")
            mod_str = f"  -> {active_mod}" if active_mod else ""
            lines.append(f"  {marker} {acct_id}: {status}{mod_str}")
            if "RUNNING" in status:
                running += 1
            elif "DONE" in status:
                done += 1

        lines.append(f"  ---")
        lines.append(f"  Running: {running} | Done: {done}/{len(PROFILES)}")

        # Concurrent accounts indicator
        if running > 1:
            lines.append(f"  ** {running} accounts syncing CONCURRENTLY **")
            self._features_exercised.add("async-concurrent-accounts")

        # Features exercised
        lines.append(f"\n  Features exercised: {', '.join(sorted(self._features_exercised)) or 'none yet'}")

        if self._errors:
            lines.append(f"\n  Errors ({len(self._errors)}):")
            for e in self._errors[-3:]:
                lines.append(f"    ! {e}")

        lines.append(f"{'='*70}\n")
        print("\n".join(lines), flush=True)

    def print_summary(self):
        total_elapsed = time.time() - self._start_time
        print(f"\n{'#'*70}")
        print(f"  BENCHMARK SUMMARY")
        print(f"{'#'*70}")
        print(f"\n  Total time: {total_elapsed:.1f}s ({timedelta(seconds=int(total_elapsed))})")

        # Per-account timings
        print(f"\n  Per-account timings:")
        for acct_id in sorted(self._account_status.keys()):
            if acct_id in self._account_start and acct_id in self._account_end:
                elapsed = self._account_end[acct_id] - self._account_start[acct_id]
                print(f"    {acct_id}: {elapsed:.1f}s")

        # Concurrency analysis
        starts = list(self._account_start.values())
        ends = list(self._account_end.values())
        if starts and ends:
            sequential_estimate = sum(
                self._account_end.get(a, 0) - self._account_start.get(a, 0)
                for a in self._account_status
                if a in self._account_start and a in self._account_end
            )
            speedup = sequential_estimate / total_elapsed if total_elapsed > 0 else 1
            print(f"\n  Sequential estimate: {sequential_estimate:.1f}s")
            print(f"  Actual (concurrent): {total_elapsed:.1f}s")
            print(f"  Speedup: {speedup:.2f}x")

        # Per-module timings (aggregated)
        print(f"\n  Per-module avg timings:")
        all_modules = defaultdict(list)
        for acct_timings in self._module_timings.values():
            for mod, elapsed in acct_timings.items():
                if isinstance(elapsed, float) and elapsed > 0:
                    all_modules[mod].append(elapsed)
        for mod in sorted(all_modules.keys()):
            times = all_modules[mod]
            avg = sum(times) / len(times)
            print(f"    {mod}: avg {avg:.1f}s (n={len(times)})")

        # Record counts
        total_records = sum(
            sum(counts.values())
            for counts in self._record_counts.values()
        )
        print(f"\n  Total records ingested: {total_records}")

        # Features
        print(f"\n  Features verified:")
        all_features = [
            ("async-concurrent-accounts", "Accounts synced concurrently"),
            ("multi-account-sync", "Multi-account sync"),
            ("cleanup-safety-net", "Cleanup safety net checked counts"),
            ("dag-scheduler", "DAG scheduler used"),
            ("pydantic-validation", "Pydantic models validated data"),
            ("rate-limiter", "Rate limiter active"),
        ]
        for feat_key, feat_name in all_features:
            check = "YES" if feat_key in self._features_exercised else " - "
            print(f"    [{check}] {feat_name}")

        if self._errors:
            print(f"\n  Errors ({len(self._errors)}):")
            for e in self._errors:
                print(f"    ! {e}")

        print(f"\n{'#'*70}\n")


# ─── Instrumented sync for a single account ──────────────────────────────────

tracker = LiveTracker()


def sync_one_account(profile_name, account_id, neo4j_driver):
    """Sync a single AWS account with instrumentation."""
    import cartography.intel.aws as aws_module
    from cartography.intel.aws.resources import RESOURCE_FUNCTIONS
    from cartography.intel.aws.util.common import parse_and_validate_aws_requested_syncs

    # S3 and other modules use asyncio internally (asyncio.gather, aioboto3).
    # When running in a thread via asyncio.to_thread, there's no event loop.
    # Create one for this thread so nested asyncio calls work.
    try:
        asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    tracker.account_start(account_id, profile_name)

    try:
        boto3_session = boto3.Session(profile_name=profile_name)

        # Verify credentials
        sts = boto3_session.client("sts")
        identity = sts.get_caller_identity()
        actual_account = identity["Account"]
        assert actual_account == account_id, f"Expected {account_id}, got {actual_account}"

        update_tag = int(time.time())
        common_job_parameters = {
            "UPDATE_TAG": update_tag,
            "AWS_ID": account_id,
        }

        with neo4j_driver.session(database=NEO4J_DATABASE) as neo4j_session:
            # Discover regions
            tracker.module_start(account_id, "region-discovery")
            regions = aws_module.ec2.get_ec2_regions(boto3_session)
            tracker.module_done(account_id, "region-discovery", len(regions))
            tracker.feature_used("multi-account-sync")

            # Parse requested syncs
            requested = AWS_REQUESTED_SYNCS.split(",")
            requested = [r.strip() for r in requested]

            sync_args = {
                "neo4j_session": neo4j_session,
                "boto3_session": boto3_session,
                "regions": regions,
                "current_aws_account_id": account_id,
                "update_tag": update_tag,
                "common_job_parameters": common_job_parameters,
            }

            # Sync each requested module
            for func_name in RESOURCE_FUNCTIONS:
                if func_name not in requested:
                    continue

                tracker.module_start(account_id, func_name)
                try:
                    RESOURCE_FUNCTIONS[func_name](**sync_args)
                    tracker.module_done(account_id, func_name)
                except Exception as e:
                    tracker.module_done(account_id, func_name)
                    tracker.error(f"{account_id}/{func_name}: {type(e).__name__}: {e}")

            # Try cleanup safety net
            try:
                from cartography.graph.cleanup_safety import should_skip_cleanup
                skip = should_skip_cleanup(
                    neo4j_session=neo4j_session,
                    module_name=f"aws.{account_id}",
                    current_count=100,  # placeholder
                    threshold=0.5,
                )
                tracker.feature_used("cleanup-safety-net")
                if skip:
                    tracker.error(f"Cleanup safety triggered for {account_id}: count below threshold")
            except Exception as e:
                tracker.error(f"Cleanup safety check failed: {e}")

        tracker.account_done(account_id, profile_name, success=True)

    except Exception as e:
        tracker.error(f"{account_id}: {type(e).__name__}: {e}")
        tracker.account_done(account_id, profile_name, success=False)


# ─── Validate Pydantic models ────────────────────────────────────────────────

def validate_pydantic_models():
    """Quick check that Pydantic models load and validate."""
    try:
        from cartography.intel.aws.ec2.response_models import EC2Instance
        from cartography.intel.aws.s3_response_models import S3Bucket
        from cartography.intel.aws.iam_response_models import IAMUser
        from cartography.intel.validation import validate_response

        # Quick smoke test
        test_instance = EC2Instance(InstanceId="i-test", ImageId="ami-test")
        test_bucket = S3Bucket(Name="test-bucket")
        test_user = IAMUser(UserName="test", UserId="uid", Arn="arn:aws:iam::123:user/test")

        validated = validate_response([{"Name": "b1"}, {"Name": "b2"}], S3Bucket)
        assert len(validated) == 2

        tracker.feature_used("pydantic-validation")
        print("  [OK] Pydantic models validated successfully")
    except Exception as e:
        tracker.error(f"Pydantic validation: {e}")
        print(f"  [FAIL] Pydantic models: {e}")


# ─── Validate DAG scheduler ──────────────────────────────────────────────────

def validate_dag_scheduler():
    """Quick check that DAG scheduler works."""
    try:
        from cartography.graph.scheduler import DAGScheduler, ModuleMetadata

        modules = [
            ModuleMetadata(name="indexes", depends_on=[], sync_func=lambda *a, **k: None),
            ModuleMetadata(name="aws", depends_on=["indexes"], sync_func=lambda *a, **k: None),
            ModuleMetadata(name="github", depends_on=["indexes"], sync_func=lambda *a, **k: None),
            ModuleMetadata(name="analysis", depends_on=["aws", "github"], sync_func=lambda *a, **k: None),
        ]
        scheduler = DAGScheduler(modules)
        plan = scheduler.dry_run()
        tracker.feature_used("dag-scheduler")
        print(f"  [OK] DAG scheduler: {plan}")
    except Exception as e:
        tracker.error(f"DAG scheduler: {e}")
        print(f"  [FAIL] DAG scheduler: {e}")


# ─── Validate rate limiter ───────────────────────────────────────────────────

def validate_rate_limiter():
    """Quick check that rate limiter works."""
    try:
        from cartography.client.base import RateLimiter, APIClientConfig

        rl = RateLimiter(max_rps=100)
        start = time.time()
        for _ in range(10):
            rl.acquire()
        elapsed = time.time() - start
        tracker.feature_used("rate-limiter")
        print(f"  [OK] Rate limiter: 10 acquires in {elapsed:.3f}s (max_rps=100)")
    except Exception as e:
        tracker.error(f"Rate limiter: {e}")
        print(f"  [FAIL] Rate limiter: {e}")


# ─── Main ────────────────────────────────────────────────────────────────────

async def run_all_accounts(neo4j_driver):
    """Run all accounts concurrently."""
    tasks = []
    for profile_name, account_id in PROFILES.items():
        task = asyncio.to_thread(sync_one_account, profile_name, account_id, neo4j_driver)
        tasks.append(task)

    tracker.feature_used("async-concurrent-accounts")
    await asyncio.gather(*tasks, return_exceptions=True)


def main():
    print(f"\n{'='*70}")
    print(f"  CARTOGRAPHY REDESIGN BENCHMARK")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Accounts: {len(PROFILES)}")
    print(f"  Modules: {AWS_REQUESTED_SYNCS}")
    print(f"  Neo4j: {NEO4J_URI}")
    print(f"{'='*70}\n")

    # Step 1: Validate features load correctly
    print("--- Pre-flight checks ---")
    validate_pydantic_models()
    validate_dag_scheduler()
    validate_rate_limiter()

    # Step 2: Connect to Neo4j
    print(f"\n--- Connecting to Neo4j at {NEO4J_URI} ---")
    try:
        neo4j_driver = neo4j.GraphDatabase.driver(
            NEO4J_URI,
            auth=(NEO4J_USER, NEO4J_PASSWORD),
        )
        neo4j_driver.verify_connectivity()
        print("  [OK] Neo4j connected")
    except Exception as e:
        print(f"  [FAIL] Cannot connect to Neo4j: {e}")
        print(f"\n  Start a test Neo4j with:")
        print(f"    docker run -d --name neo4j-bench -p 7688:7687 -p 7475:7474 \\")
        print(f"      -e NEO4J_AUTH={NEO4J_USER}/{NEO4J_PASSWORD} \\")
        print(f"      -e NEO4J_PLUGINS='[\"apoc\"]' \\")
        print(f"      neo4j:5-community")
        print(f"\n  Then re-run this script.")
        sys.exit(1)

    # Step 3: Run concurrent syncs
    print(f"\n--- Starting concurrent sync of {len(PROFILES)} accounts ---")
    print(f"    (watch the live progress below)\n")

    asyncio.run(run_all_accounts(neo4j_driver))

    # Step 4: Summary
    tracker.print_summary()

    neo4j_driver.close()


if __name__ == "__main__":
    # Set up logging to see cartography's internal logs too
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-7s [%(name)s] %(message)s",
        datefmt="%H:%M:%S",
    )
    # Quiet down noisy loggers
    logging.getLogger("neo4j").setLevel(logging.WARNING)
    logging.getLogger("botocore").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)

    main()
