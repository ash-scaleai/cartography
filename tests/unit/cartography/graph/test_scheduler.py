"""Tests for cartography.graph.scheduler — DAG-based parallel module execution."""
from __future__ import annotations

import asyncio
import time
from unittest.mock import MagicMock

import pytest

from cartography.graph.scheduler import DAGScheduler
from cartography.graph.scheduler import ModuleMetadata


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _noop(*args, **kwargs):
    """A no-op sync function used as a placeholder."""


def _make_modules(specs: list[tuple[str, list[str]]]) -> list[ModuleMetadata]:
    """Build ModuleMetadata list from (name, depends_on) tuples."""
    return [
        ModuleMetadata(name=name, depends_on=deps, sync_func=_noop)
        for name, deps in specs
    ]


# ---------------------------------------------------------------------------
# Topological sort correctness
# ---------------------------------------------------------------------------

class TestTopologicalSort:
    def test_linear_chain(self):
        """A -> B -> C should produce three waves."""
        modules = _make_modules([
            ("A", []),
            ("B", ["A"]),
            ("C", ["B"]),
        ])
        scheduler = DAGScheduler(modules)
        assert scheduler.waves == [["A"], ["B"], ["C"]]

    def test_diamond_dependency(self):
        """Diamond: A -> B, A -> C, B+C -> D."""
        modules = _make_modules([
            ("A", []),
            ("B", ["A"]),
            ("C", ["A"]),
            ("D", ["B", "C"]),
        ])
        scheduler = DAGScheduler(modules)
        assert scheduler.waves == [["A"], ["B", "C"], ["D"]]

    def test_independent_modules(self):
        """Modules with no dependencies all land in wave 1."""
        modules = _make_modules([
            ("X", []),
            ("Y", []),
            ("Z", []),
        ])
        scheduler = DAGScheduler(modules)
        assert scheduler.waves == [["X", "Y", "Z"]]

    def test_complex_dag(self):
        modules = _make_modules([
            ("create-indexes", []),
            ("aws", ["create-indexes"]),
            ("github", ["create-indexes"]),
            ("okta", ["create-indexes"]),
            ("analysis", ["aws", "github", "okta"]),
        ])
        scheduler = DAGScheduler(modules)
        assert scheduler.waves == [
            ["create-indexes"],
            ["aws", "github", "okta"],
            ["analysis"],
        ]

    def test_single_module(self):
        modules = _make_modules([("solo", [])])
        scheduler = DAGScheduler(modules)
        assert scheduler.waves == [["solo"]]

    def test_waves_are_deterministically_sorted(self):
        """Modules within a wave are sorted alphabetically for determinism."""
        modules = _make_modules([
            ("Z-mod", []),
            ("A-mod", []),
            ("M-mod", []),
        ])
        scheduler = DAGScheduler(modules)
        assert scheduler.waves == [["A-mod", "M-mod", "Z-mod"]]


# ---------------------------------------------------------------------------
# Cycle detection
# ---------------------------------------------------------------------------

class TestCycleDetection:
    def test_simple_cycle_raises(self):
        modules = _make_modules([
            ("A", ["B"]),
            ("B", ["A"]),
        ])
        with pytest.raises(ValueError, match="Cycle detected"):
            DAGScheduler(modules)

    def test_three_node_cycle_raises(self):
        modules = _make_modules([
            ("A", ["C"]),
            ("B", ["A"]),
            ("C", ["B"]),
        ])
        with pytest.raises(ValueError, match="Cycle detected"):
            DAGScheduler(modules)

    def test_self_cycle_raises(self):
        modules = _make_modules([("A", ["A"])])
        with pytest.raises(ValueError, match="Cycle detected"):
            DAGScheduler(modules)

    def test_cycle_with_non_cycle_nodes(self):
        """Only the cycle participants should appear in the error."""
        modules = _make_modules([
            ("ok", []),
            ("A", ["B"]),
            ("B", ["A"]),
        ])
        with pytest.raises(ValueError, match="Cycle detected"):
            DAGScheduler(modules)


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

class TestValidation:
    def test_duplicate_module_name_raises(self):
        modules = [
            ModuleMetadata(name="dup", sync_func=_noop),
            ModuleMetadata(name="dup", sync_func=_noop),
        ]
        with pytest.raises(ValueError, match="Duplicate module name"):
            DAGScheduler(modules)

    def test_missing_dependency_raises(self):
        modules = [ModuleMetadata(name="A", depends_on=["ghost"], sync_func=_noop)]
        with pytest.raises(ValueError, match="depends on 'ghost'"):
            DAGScheduler(modules)


# ---------------------------------------------------------------------------
# Concurrent execution
# ---------------------------------------------------------------------------

class TestConcurrentExecution:
    def test_independent_modules_overlap_in_time(self):
        """Two independent modules should run concurrently, finishing faster
        than if they ran sequentially."""
        sleep_seconds = 0.3

        def slow_func(*args, **kwargs):
            time.sleep(sleep_seconds)

        modules = [
            ModuleMetadata(name="A", depends_on=[], sync_func=slow_func),
            ModuleMetadata(name="B", depends_on=[], sync_func=slow_func),
        ]
        scheduler = DAGScheduler(modules)

        start = time.monotonic()
        results = scheduler.execute()
        elapsed = time.monotonic() - start

        assert results == {"A": "success", "B": "success"}
        # If they ran sequentially it would take ~0.6s; concurrently ~0.3s.
        # Use 0.5s as the threshold to allow some overhead.
        assert elapsed < sleep_seconds * 2 - 0.1, (
            f"Expected concurrent execution but took {elapsed:.2f}s"
        )


# ---------------------------------------------------------------------------
# Dependency ordering
# ---------------------------------------------------------------------------

class TestDependencyOrdering:
    def test_dependent_module_waits_for_dependency(self):
        """Module B depends on A. B must not start until A finishes."""
        execution_log: list[tuple[str, str]] = []

        def make_func(name):
            def func(*args, **kwargs):
                execution_log.append((name, "start"))
                time.sleep(0.15)
                execution_log.append((name, "end"))
            return func

        modules = [
            ModuleMetadata(name="A", depends_on=[], sync_func=make_func("A")),
            ModuleMetadata(name="B", depends_on=["A"], sync_func=make_func("B")),
        ]
        scheduler = DAGScheduler(modules)
        results = scheduler.execute()

        assert results == {"A": "success", "B": "success"}
        # A must end before B starts
        a_end_idx = execution_log.index(("A", "end"))
        b_start_idx = execution_log.index(("B", "start"))
        assert a_end_idx < b_start_idx, (
            f"Expected A to finish before B starts. Log: {execution_log}"
        )


# ---------------------------------------------------------------------------
# Dry-run output
# ---------------------------------------------------------------------------

class TestDryRun:
    def test_dry_run_format(self):
        modules = _make_modules([
            ("create-indexes", []),
            ("aws", ["create-indexes"]),
            ("github", ["create-indexes"]),
            ("analysis", ["aws", "github"]),
        ])
        scheduler = DAGScheduler(modules)
        plan = scheduler.dry_run()

        assert "Wave 1: [create-indexes]" in plan
        assert "Wave 2: [aws, github]" in plan
        assert "Wave 3: [analysis]" in plan
        # Waves are separated by " -> "
        assert plan.count(" -> ") == 2

    def test_dry_run_single_wave(self):
        modules = _make_modules([("X", []), ("Y", [])])
        scheduler = DAGScheduler(modules)
        plan = scheduler.dry_run()
        assert plan == "Wave 1: [X, Y]"


# ---------------------------------------------------------------------------
# Error propagation
# ---------------------------------------------------------------------------

class TestErrorPropagation:
    def test_failed_module_skips_dependents(self):
        """If A fails, B (which depends on A) should be skipped."""
        def failing_func(*args, **kwargs):
            raise RuntimeError("boom")

        modules = [
            ModuleMetadata(name="A", depends_on=[], sync_func=failing_func),
            ModuleMetadata(name="B", depends_on=["A"], sync_func=_noop),
        ]
        scheduler = DAGScheduler(modules)
        results = scheduler.execute()

        assert results["A"] == "failed"
        assert results["B"] == "skipped"

    def test_failure_does_not_affect_independent_modules(self):
        """If A fails, C (independent of A) should still succeed."""
        call_log = []

        def failing_func(*args, **kwargs):
            raise RuntimeError("boom")

        def good_func(*args, **kwargs):
            call_log.append("C")

        modules = [
            ModuleMetadata(name="A", depends_on=[], sync_func=failing_func),
            ModuleMetadata(name="C", depends_on=[], sync_func=good_func),
            ModuleMetadata(name="B", depends_on=["A"], sync_func=_noop),
        ]
        scheduler = DAGScheduler(modules)
        results = scheduler.execute()

        assert results["A"] == "failed"
        assert results["B"] == "skipped"
        assert results["C"] == "success"
        assert "C" in call_log

    def test_transitive_skip(self):
        """A fails -> B skipped -> C (depends on B) also skipped."""
        def failing_func(*args, **kwargs):
            raise RuntimeError("boom")

        modules = [
            ModuleMetadata(name="A", depends_on=[], sync_func=failing_func),
            ModuleMetadata(name="B", depends_on=["A"], sync_func=_noop),
            ModuleMetadata(name="C", depends_on=["B"], sync_func=_noop),
        ]
        scheduler = DAGScheduler(modules)
        results = scheduler.execute()

        assert results["A"] == "failed"
        assert results["B"] == "skipped"
        assert results["C"] == "skipped"

    def test_args_forwarded_to_sync_func(self):
        """Verify that execute() forwards args/kwargs to each sync_func."""
        received = {}

        def capture_func(*args, **kwargs):
            received["args"] = args
            received["kwargs"] = kwargs

        modules = [
            ModuleMetadata(name="A", depends_on=[], sync_func=capture_func),
        ]
        scheduler = DAGScheduler(modules)
        scheduler.execute("session", config="my_config")

        assert received["args"] == ("session",)
        assert received["kwargs"] == {"config": "my_config"}
