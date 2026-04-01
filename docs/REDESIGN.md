# Cartography Redesign Plan

## Overview

This document captures the full architectural redesign plan for Cartography. It covers quick-win improvements (Phase 0) through production hardening (Phase 4), totaling 4 quick-ROI items and 17 deeper features.

Each feature includes success criteria that must be met before the feature is considered complete.

---

## Universal Requirements (Apply to Every Feature)

Every feature, regardless of phase, must meet these baseline criteria:

1. **Tests**: Unit tests for core logic + integration test for the happy path. No feature merges without test coverage.
2. **Debuggability**: Every feature must be inspectable at runtime. This means:
   - Structured log messages at key decision points (not just errors)
   - A `--dry-run` or `--verbose` mode where applicable, showing what would happen without side effects
   - Clear error messages with context (which module, which resource, what failed, what to check)
3. **Graceful degradation**: Optional features (observability, plugins, event-driven sync) must be no-ops when not configured. Missing config = silent skip, never a crash.
4. **Backward compatibility**: Existing CLI invocations and sync behavior must not break unless explicitly deprecated with a migration path.

---

## Phase 0: Quick ROI (Do First)

These deliver immediate value without architectural upheaval.

### 0.1 — Add asyncio for concurrent API calls

- **Status**: Not started
- **Why**: Sync runs are I/O-bound. Providers like AWS, GitHub, Okta could fetch in parallel. Within AWS, independent services (EC2, S3, IAM) could overlap.
- **What**: Introduce `asyncio` event loop at the sync orchestrator level. Convert `get()` functions to async where provider SDKs support it (aioboto3 already in deps). Keep `load()` synchronous (Neo4j writes are fast, serialization is fine).
- **Key files**: `cartography/sync.py`, `cartography/intel/aws/__init__.py`
- **Success criteria**: End-to-end sync time for a multi-provider run (e.g., AWS + GitHub + Okta) drops by ≥30% compared to sequential baseline. No change in data correctness (same node/relationship counts).

### 0.2 — Add Pydantic models at API boundaries

- **Status**: Not started
- **Why**: Data flows as `list[dict[str, Any]]` with no validation. Provider API changes silently corrupt the graph.
- **What**: Add Pydantic response models for the transform layer input. Validate after `get()`, before `transform()`. Start with the top 5 modules by usage (AWS EC2, IAM, S3, GitHub, GCP Compute). Gradually roll out.
- **Key files**: New `cartography/intel/<provider>/models.py` files per module
- **Success criteria**: Top 5 modules have Pydantic models. Malformed API responses raise `ValidationError` with clear field-level messages instead of silently ingesting bad data. Existing tests still pass (no false positives).

### 0.3 — Split cli.py into per-provider CLI groups

- **Status**: Not started
- **Why**: `cli.py` is 105KB, every provider's options in one file.
- **What**: Each provider module registers its own Typer sub-group. Core CLI only handles Neo4j, module selection, orchestration. Provider CLI options live next to the provider code.
- **Key files**: `cartography/cli.py` → split into `cartography/cli/core.py` + `cartography/intel/<provider>/cli.py`
- **Success criteria**: `cli.py` reduced to <10KB (core only). `cartography --help` still shows all options. All existing CLI invocations work identically (backward compatible). Each provider's CLI code lives in its own directory.

### 0.4 — Add cleanup safety net

- **Status**: Not started
- **Why**: If a module crashes mid-sync, cleanup deletes valid data that wasn't re-ingested.
- **What**: Before cleanup, compare fetched record count against previous run's count (stored as a graph property or simple file). If count drops below configurable threshold (default 50%), skip cleanup and warn.
- **Key files**: `cartography/graph/job.py`, `cartography/graph/cleanupbuilder.py`
- **Success criteria**: When a module fetches <50% of previous count, cleanup is skipped and a WARNING log is emitted. Configurable threshold via CLI flag. Integration test simulates partial fetch and verifies no data loss.

---

## Phase 1: Architectural Improvements (Features 1–6)

### Feature 1 — Plugin-based module architecture

- **Status**: Not started
- **Why**: Eliminates the 30+ runtime dependency problem. Each provider becomes an independently installable package.
- **What**: Make each provider an installable plugin (`cartography-aws`, `cartography-github`, etc.). Core package: `cartography-core` with schema system, graph client, sync orchestrator. Plugins register via Python entry points (`cartography.modules`).
- **Success criteria**: `pip install cartography-core` installs no provider SDKs. `pip install cartography-aws` adds only boto3/aioboto3. `cartography --selected-modules aws` works with only those two installed. Plugin discovery tested with at least 3 providers.

### Feature 2 — Parallel ingestion with DAG scheduler

- **Status**: Not started
- **Why**: Current `OrderedDict` in `sync.py` forces sequential execution even for independent modules.
- **What**: Replace `OrderedDict` with a DAG-based scheduler. Each module declares `depends_on: list[str]`. Scheduler topologically sorts and runs independent modules concurrently. Uses asyncio (from Phase 0.1) as the execution engine.
- **Key file**: `cartography/sync.py`
- **Success criteria**: Independent modules (e.g., AWS + GitHub) run concurrently. Dependent modules (e.g., EC2 after VPC) run in correct order. Cycle detection raises error at startup. `--dry-run` flag prints execution plan without running.

### Feature 3 — Explicit dependency graph

- **Status**: Not started
- **Why**: Adding a new module currently requires guessing insertion position in the sync order.
- **What**: Each module's `__init__.py` exports a `MODULE_METADATA` dict with `name`, `depends_on`, `provides` (node labels). Scheduler validates the graph at startup (cycle detection, missing deps).
- **Success criteria**: Every module has `MODULE_METADATA`. Missing dependency raises `ValueError` at startup with clear message. Unit test validates all declared dependencies resolve.

### Feature 4 — Distributed CLI config

- **Status**: Not started
- **Why**: Extension of Phase 0.3 — once plugins exist, each plugin should ship its own CLI group.
- **What**: Core CLI discovers plugins and assembles the full CLI dynamically.
- **Key file**: `cartography/cli/core.py`
- **Success criteria**: Adding a new provider requires zero changes to core CLI code. `cartography --help` dynamically lists installed providers. Uninstalling a provider plugin cleanly removes its CLI options.

### Feature 5 — Shared rate-limiting / API client framework

- **Status**: Not started
- **Why**: Retry, backoff, rate-limit, and pagination logic is duplicated across modules.
- **What**: Abstract into `cartography/client/base.py`. Modules configure via declarative params: `max_rps=10, retry_on=[429, 503], backoff="exponential"`. Neo4j retry layer stays separate (different failure modes).
- **Key files**: New `cartography/client/base.py`, refactor individual modules
- **Success criteria**: At least 5 modules migrated to shared client. Rate-limit test: mock 429 responses, verify backoff and eventual success. No duplicate retry logic in migrated modules.

### Feature 6 — Streaming ingestion

- **Status**: Not started
- **Why**: Current approach collects all records in memory then bulk-loads, causing high peak memory for large accounts.
- **What**: Stream pages to Neo4j as they arrive. The existing batch UNWIND approach at the Neo4j layer is fine — feed it smaller, incremental batches.
- **Key file**: `cartography/client/core/tx.py`
- **Success criteria**: Peak memory for a large module (e.g., EC2 instances across 50 regions) drops by ≥40%. Data correctness unchanged (same node counts). Benchmark before/after with memory profiler.

---

## Phase 2: Schema & Subsystem Improvements (Features 7–10)

### Feature 7 — Unify analysis jobs into the schema system

- **Status**: Not started
- **Why**: Analysis jobs are currently raw Cypher in JSON files under `cartography/data/jobs/`, disconnected from the schema system.
- **What**: Let schemas declare computed relationships or derived properties. Framework materializes these post-ingestion. Keeps everything in one place, testable with same patterns.
- **Key files**: `cartography/models/core/`, `cartography/data/jobs/`
- **Success criteria**: At least 3 existing JSON analysis jobs converted to schema-declared computed relationships. Generated Cypher matches original JSON job output. JSON jobs marked deprecated with migration guide.

### Feature 8 — Separate driftdetect and rules into standalone packages

- **Status**: Not started
- **Why**: These subsystems have independent release cycles and user bases.
- **What**: `cartography-driftdetect` and `cartography-rules` as independent packages. Depend on `cartography-core` for graph access. Own release cycles, own CLIs.
- **Key dirs**: `cartography/driftdetect/`, `cartography/rules/`
- **Success criteria**: `pip install cartography-driftdetect` works independently. `cartography-detectdrift` CLI functions without the main `cartography` package installed (only needs `cartography-core`). Existing tests pass in both packages.

### Feature 9 — Schema-driven documentation

- **Status**: Not started
- **Why**: Hand-written schema docs drift from code over time.
- **What**: Auto-generate graph schema docs from Python model classes. Build step produces `docs/modules/*/schema.md`.
- **Key files**: `cartography/models/`, `docs/`
- **Success criteria**: `make docs` generates schema pages for all modules with node labels, properties, and relationships. CI step fails if generated docs are stale (diff check). Zero hand-written schema docs remain.

### Feature 10 — Event-driven incremental sync

- **Status**: Not started
- **Why**: Full syncs are expensive. Cloud events can trigger targeted re-syncs for changed resources only.
- **What**: Support a mode where cloud events (CloudTrail, GCP Audit Logs, Azure Activity Log) trigger targeted re-syncs. Route events to the appropriate module. The update_tag cleanup strategy already supports this — missing piece is event ingestion and routing.
- **New subsystem**: `cartography/events/`
- **Success criteria**: Demo with CloudTrail: an EC2 instance launch event triggers re-sync of only the EC2 module for that region. Latency from event to graph update <60s. Full sync still works as fallback.

---

## Phase 3: Data Integrity & Observability (Features 11–14)

### Feature 11 — Graph database abstraction layer

- **Status**: Not started
- **Why**: Hard dependency on Neo4j limits deployment options.
- **What**: Thin adapter interface over Neo4j driver. Enables swapping in Memgraph, Neptune, FalkorDB. Declarative schemas already insulate modules from raw Cypher — abstract the driver and query builder.
- **Key files**: `cartography/graph/querybuilder.py`, `cartography/client/core/tx.py`
- **Success criteria**: Adapter interface defined with at least 2 implementations (Neo4j + one alternative, e.g., Memgraph). Full test suite passes against both backends. Zero intel module code changes required to switch backends.

### Feature 12 — Typed API response models (full coverage)

- **Status**: Not started
- **Why**: Extension of Phase 0.2 — full coverage across all 40+ modules.
- **What**: Pydantic models for every provider API response. Validation at boundary, IDE support, catches schema drift early.
- **Success criteria**: 100% of modules have Pydantic response models. `mypy --strict` passes on all model files. CI runs validation against recorded API responses (from Feature 16 cassettes).

### Feature 13 — Differential sync

- **Status**: Not started
- **Why**: Re-ingesting unchanged data is wasteful for large environments.
- **What**: Track checksums/ETags per resource. Skip unchanged items during re-ingestion. The update_tag strategy is compatible — just don't re-MERGE what hasn't changed.
- **Success criteria**: Second consecutive sync of unchanged data completes in <10% of first sync's time. API call count drops proportionally (skip fetches where ETag matches). Data correctness verified: graph state identical after full vs differential sync.

### Feature 14 — First-class multi-tenancy

- **Status**: Not started
- **Why**: MSPs and large organizations need tenant isolation within a single Cartography instance.
- **What**: Tenant isolation via separate graph namespaces or label-based partitioning. Single instance serves multiple orgs. Tenant-scoped cleanup, queries, and access control.
- **Success criteria**: Two tenants synced into same Neo4j instance with zero data leakage. Cleanup for tenant A does not affect tenant B's data. Query isolation demonstrated: tenant A's queries cannot see tenant B's nodes.

---

## Phase 4: Production Hardening (Features 15–17)

### Feature 15 — Observability

- **Status**: Not started
- **Why**: Current instrumentation is limited to `@timeit` decorators. No structured logging, tracing, or metrics export.
- **What**: Structured logging with correlation IDs per sync run. OpenTelemetry traces for full pipeline (API call → transform → Neo4j write). Exported metrics: records ingested, API latency, errors per module, sync duration. Replace `@timeit` with proper instrumentation.
- **Graceful degradation**: If no OTLP endpoint, Jaeger, or Prometheus is configured, observability is a no-op — zero errors, zero performance impact. Uses OpenTelemetry's no-op tracer/meter pattern by default.
- **Success criteria**: Cartography starts and completes a full sync with no observability config (no env vars, no endpoints) — no errors, no warnings. When configured, every sync run emits a trace visible in Jaeger/Zipkin with spans for each module. Prometheus/OTLP metrics endpoint exposes: `cartography_records_ingested`, `cartography_sync_duration_seconds`, `cartography_api_errors_total`. Correlation ID appears in every log line during a sync run.

### Feature 16 — Contract testing for provider APIs

- **Status**: Not started
- **Why**: Provider-side breaking changes can corrupt graph data silently.
- **What**: VCR-style recorded API response cassettes. Lightweight contract tests that fail CI when response shapes drift.
- **Success criteria**: At least 10 modules have recorded cassettes. CI job runs contract tests on every PR. When a cassette is updated with a breaking shape change, the corresponding Pydantic model test fails. Cassette refresh script documented.

### Feature 17 — Cleanup safety net (extended)

- **Status**: Not started
- **Why**: Extension of Phase 0.4 with historical trending and anomaly detection.
- **What**: Track record counts over time per module. Anomaly detection: alert if any module's count deviates significantly from rolling average. Circuit breaker: halt sync for a module if repeated failures detected.
- **Success criteria**: Record count history stored per module (last 10 runs). Alert fires when count drops >2 standard deviations from rolling average. Circuit breaker trips after 3 consecutive failures, auto-resets after 1 successful run. All behaviors covered by integration tests.

---

## Feature Implementation Workflow

When starting work on a feature:

1. Read the relevant section in this document for context and success criteria
2. Branch off `master` (not the `redesign-plan` branch)
3. Name branch: `redesign/<feature-number>-<short-name>` (e.g., `redesign/0.1-async-ingestion`)
4. After merging the feature PR, update this document to mark the feature's status as done

---

## Branch Maintenance Strategy

The `redesign-plan` branch should stay mergeable from `master` with minimal conflicts:

- **Only add new files** — `docs/REDESIGN.md` and `docs/REDESIGN_CLAUDE.md` are net-new files that won't conflict with upstream changes
- **Never modify existing source files** on this branch — all code changes happen on separate feature branches
- **Periodic merge**: `git merge master` into this branch whenever needed — should always be clean since we only add documentation files
- This branch serves as a **planning artifact**, not an implementation branch
