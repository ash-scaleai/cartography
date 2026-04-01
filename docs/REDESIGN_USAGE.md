# Cartography Redesign — Usage Guide

This document covers how to install, configure, and use the redesigned version of Cartography from the `ash-scaleai/cartography` fork.

All changes are **backward compatible** — existing CLI invocations work identically. New features are opt-in.

---

## Installation

```bash
# From the fork (recommended for testing)
pip install git+ssh://git@github.com/ash-scaleai/cartography.git@main

# Or clone and install in dev mode
git clone git@github.com:ash-scaleai/cartography.git
cd cartography
git checkout main
pip install -e ".[dev]"
```

---

## Quick Start

### Basic usage (same as upstream)

```bash
cartography --neo4j-uri bolt://localhost:7687 \
            --neo4j-password-env-var NEO4J_PASSWORD \
            --selected-modules aws
```

### With async mode (concurrent providers)

```bash
cartography --neo4j-uri bolt://localhost:7687 \
            --neo4j-password-env-var NEO4J_PASSWORD \
            --async-fetch \
            --selected-modules aws
```

### Multi-account with AWS SSO profiles

```bash
cartography --neo4j-uri bolt://localhost:7687 \
            --neo4j-password-env-var NEO4J_PASSWORD \
            --async-fetch \
            --aws-sync-all-profiles \
            --aws-best-effort-mode
```

---

## New CLI Flags

### Async / Concurrency

| Flag | Default | Description |
|------|---------|-------------|
| `--async-fetch` | `False` | Run independent provider sync stages concurrently using asyncio. Stages like `create-indexes` and `analysis` still run sequentially. |

### Cleanup Safety Net

| Flag | Default | Description |
|------|---------|-------------|
| `--cleanup-threshold` | `0.5` | Minimum ratio (0.0–1.0) of current vs previous record counts required to proceed with cleanup. If the current count drops below this fraction of the previous count, cleanup is skipped. |
| `--skip-cleanup-safety` | `False` | Disable the cleanup safety net entirely. |
| `--cleanup-history-size` | `10` | Number of historical record counts to retain per module for anomaly detection trending. |
| `--anomaly-std-devs` | `2.0` | Number of standard deviations from the rolling average to trigger an anomaly alert during cleanup. |
| `--circuit-breaker-threshold` | `3` | Number of consecutive sync failures before the circuit breaker trips and blocks further syncs for a module. Auto-resets after 1 successful run. |

---

## What's New (Feature Summary)

### Phase 0: Quick ROI

| Feature | Description | Status |
|---------|-------------|--------|
| **0.1 Async Ingestion** | `asyncio.gather()` for concurrent provider sync stages | Opt-in via `--async-fetch` |
| **0.2 Pydantic Models** | Response validation for top 5 modules (EC2, IAM, S3, GitHub, GCP) | Available as library |
| **0.3 CLI Split** | `cli.py` split into `cli/core.py` + per-provider CLI modules | Active |
| **0.4 Cleanup Safety** | Skip cleanup when record count drops below threshold | Active by default |

### Phase 1: Architectural Improvements

| Feature | Description | Status |
|---------|-------------|--------|
| **1. Plugin Architecture** | Module discovery via Python entry points | Available |
| **2. DAG Scheduler** | Topological sort + wave-based concurrent execution | Available as library |
| **3. Dependency Graph** | `MODULE_METADATA` declarations with `depends_on` / `provides` | Declared for 5 providers + 21 AWS sub-modules |
| **4. Distributed CLI** | Plugin registry for dynamic CLI option discovery | Available |
| **5. Rate Limiting** | Shared `RateLimiter`, `RetryHandler`, `PaginatedFetcher` | Available as library |
| **6. Streaming Ingestion** | `StreamingLoader` for batch-by-batch Neo4j writes | Available as library |

### Phase 2: Schema & Subsystem Improvements

| Feature | Description | Status |
|---------|-------------|--------|
| **7. Schema Analysis Jobs** | `ComputedRelationship` / `ComputedProperty` dataclasses | 3 jobs converted |
| **8. Standalone Packages** | `cartography-core`, `cartography-driftdetect`, `cartography-rules` boundaries defined | Package templates ready |
| **9. Schema Docs** | Auto-generate Markdown from model classes | `python3 -m cartography.docs.generator` |
| **10. Event-Driven Sync** | CloudTrail event routing to targeted re-syncs | Available as library |

### Phase 3: Data Integrity & Observability

| Feature | Description | Status |
|---------|-------------|--------|
| **11. DB Abstraction** | `GraphAdapter` ABC with Neo4j + Memgraph implementations | Available |
| **12. Full Pydantic** | Response models for 15 total modules | Available as library |
| **13. Differential Sync** | Checksum-based skip of unchanged records | Available as library |
| **14. Multi-Tenancy** | Label-based or database-level tenant isolation | Available as library |

### Phase 4: Production Hardening

| Feature | Description | Status |
|---------|-------------|--------|
| **15. Observability** | OpenTelemetry tracing + metrics, structured JSON logging, correlation IDs | No-op when unconfigured |
| **16. Contract Testing** | VCR-style cassettes + Pydantic model validation | 5 sample cassettes |
| **17. Cleanup Extended** | Historical trending, anomaly detection (>2σ), circuit breaker | Active via CLI flags |

---

## Benchmark Results

Tested against 6 real AWS accounts via AWS SSO.

### Single Account (sgp-sandbox-1-audit)

| Module | Original | Redesign |
|--------|----------|----------|
| iam | 25.1s | 2.2s |
| s3 | 2.1s | 0.3s |
| ec2:instance | 12.0s | 12.5s |
| ec2:vpc | 12.5s | 2.2s |
| **Total** | **51.7s** | **14.7s** |

**Speedup: 3.51x**

### Large Account (staging-admin)

| Module | Original | Redesign |
|--------|----------|----------|
| iam | 254.8s | 253.2s |
| s3 | 53.6s | 5.8s |
| ec2:instance | 13.6s | 13.6s |
| ec2:vpc | 11.9s | 11.5s |
| **Total** | **333.9s** | **266.9s** |

**Speedup: 1.25x** (IAM-dominated — 76% of runtime is IAM which can't be parallelized yet)

### 6 Accounts Concurrent

| Metric | Value |
|--------|-------|
| Sequential estimate | 3118s (52 min) |
| Actual (concurrent) | 1548s (26 min) |
| **Speedup** | **2.01x** |

### Running Benchmarks

```bash
# Quick 1-account comparison (sequential vs concurrent)
python3 scripts/quick_compare.py

# Full 6-account benchmark with live progress
python3 scripts/benchmark_sync.py

# Head-to-head 6-account comparison
python3 scripts/compare_benchmark.py
```

---

## Observability (Optional)

Observability is a **complete no-op** when not configured — zero errors, zero overhead.

To enable:

```bash
# Structured JSON logging
export CARTOGRAPHY_LOG_FORMAT=json

# OpenTelemetry tracing (requires opentelemetry-sdk installed)
export CARTOGRAPHY_OTLP_ENDPOINT=http://localhost:4317
export CARTOGRAPHY_OBSERVABILITY_ENABLED=true

# Then run cartography normally
cartography --neo4j-uri bolt://localhost:7687 ...
```

Exported metrics (when configured):
- `cartography_records_ingested` — counter per module
- `cartography_sync_duration_seconds` — histogram per module
- `cartography_api_errors_total` — counter per module

---

## Schema Documentation Generation

Auto-generate graph schema docs from Python model classes:

```bash
# Generate to docs/schema/
python3 -m cartography.docs.generator --output-dir docs/schema/

# Output: one schema.md per provider with node labels, properties, relationships
```

---

## Keeping in Sync with Upstream

```bash
# Fetch latest from upstream
git checkout master
git pull origin master

# Merge into main
git checkout main
git merge master

# Push to fork
git push fork main
```

The merge should always be clean since our changes are additive (new files + opt-in flags on existing files).

---

## Development

```bash
# Run all redesign tests
python3 -m pytest tests/unit/cartography/ --override-ini="addopts=" -q

# Run specific phase tests
python3 -m pytest tests/unit/cartography/graph/test_scheduler.py -v    # DAG scheduler
python3 -m pytest tests/unit/cartography/events/ -v                     # Event-driven sync
python3 -m pytest tests/unit/cartography/observability/ -v              # Observability
python3 -m pytest tests/unit/cartography/tenancy/ -v                    # Multi-tenancy

# Generate schema docs
python3 -m cartography.docs.generator --output-dir docs/schema/
```

---

## Full Redesign Plan

See [docs/REDESIGN.md](REDESIGN.md) for the complete plan with success criteria for all 21 features.
