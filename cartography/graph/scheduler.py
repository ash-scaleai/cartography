"""
DAG-based scheduler for parallel module execution.

This module provides a DAGScheduler that accepts modules with dependency
metadata, topologically sorts them into waves, and runs independent modules
concurrently using asyncio.
"""
from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from collections import deque
from dataclasses import dataclass
from dataclasses import field
from typing import Any
from typing import Callable

logger = logging.getLogger(__name__)


@dataclass
class ModuleMetadata:
    """Metadata describing a sync module and its dependencies.

    Attributes:
        name: Unique identifier for this module.
        depends_on: List of module names that must complete before this one runs.
        sync_func: The callable that performs the actual sync work.
    """
    name: str
    depends_on: list[str] = field(default_factory=list)
    sync_func: Callable[..., Any] = field(default=lambda *a, **kw: None)


class DAGScheduler:
    """Schedule and execute sync modules respecting a dependency DAG.

    Modules are grouped into *waves*. All modules in a wave have their
    dependencies satisfied by earlier waves, so they can run concurrently.
    Wave N+1 starts only after every module in wave N has finished.

    Usage::

        scheduler = DAGScheduler([
            ModuleMetadata("create-indexes", [], create_indexes_func),
            ModuleMetadata("aws", ["create-indexes"], aws_func),
            ModuleMetadata("github", ["create-indexes"], github_func),
            ModuleMetadata("analysis", ["aws", "github"], analysis_func),
        ])

        # Preview the plan without executing
        scheduler.dry_run()

        # Execute (from sync code that is not itself async)
        scheduler.execute(neo4j_session, config)
    """

    def __init__(self, modules: list[ModuleMetadata]) -> None:
        self._modules: dict[str, ModuleMetadata] = {}
        for mod in modules:
            if mod.name in self._modules:
                raise ValueError(f"Duplicate module name: '{mod.name}'")
            self._modules[mod.name] = mod

        # Validate that all declared dependencies actually exist
        for mod in self._modules.values():
            for dep in mod.depends_on:
                if dep not in self._modules:
                    raise ValueError(
                        f"Module '{mod.name}' depends on '{dep}', "
                        f"which is not a registered module.",
                    )

        self._waves: list[list[str]] = self._topological_sort()

    # ------------------------------------------------------------------
    # Topological sort using Kahn's algorithm
    # ------------------------------------------------------------------

    def _topological_sort(self) -> list[list[str]]:
        """Compute execution waves via Kahn's algorithm.

        Returns a list of waves, where each wave is a list of module names
        whose dependencies are all in previous waves.

        Raises ``ValueError`` if the dependency graph contains a cycle.
        """
        # Build adjacency list and in-degree map
        in_degree: dict[str, int] = {name: 0 for name in self._modules}
        dependents: dict[str, list[str]] = defaultdict(list)

        for mod in self._modules.values():
            for dep in mod.depends_on:
                dependents[dep].append(mod.name)
                in_degree[mod.name] += 1

        # Seed the queue with nodes that have no incoming edges
        queue: deque[str] = deque(
            sorted(name for name, deg in in_degree.items() if deg == 0),
        )

        waves: list[list[str]] = []
        processed = 0

        while queue:
            # Everything currently in the queue forms the next wave
            wave: list[str] = sorted(queue)  # sorted for determinism
            queue.clear()
            waves.append(wave)
            processed += len(wave)

            for name in wave:
                for dependent in sorted(dependents[name]):
                    in_degree[dependent] -= 1
                    if in_degree[dependent] == 0:
                        queue.append(dependent)

        if processed != len(self._modules):
            # Find the cycle participants for a helpful error message
            cycle_members = [
                name for name, deg in in_degree.items() if deg > 0
            ]
            raise ValueError(
                f"Cycle detected among modules: {cycle_members}. "
                "Cannot determine a valid execution order.",
            )

        return waves

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def waves(self) -> list[list[str]]:
        """Return the computed execution waves (read-only copy)."""
        return [list(w) for w in self._waves]

    def dry_run(self) -> str:
        """Return a human-readable execution plan without running anything.

        Example output::

            Wave 1: [create-indexes]
            Wave 2: [aws, github, okta]
            Wave 3: [analysis]
        """
        lines: list[str] = []
        for i, wave in enumerate(self._waves, start=1):
            lines.append(f"Wave {i}: [{', '.join(wave)}]")
        plan = " -> ".join(lines)
        logger.info("DAG execution plan: %s", plan)
        return plan

    def execute(self, *args: Any, **kwargs: Any) -> dict[str, str]:
        """Run all modules respecting dependency order.

        Positional and keyword arguments are forwarded to each module's
        ``sync_func``.  Independent modules within a wave run concurrently
        via ``asyncio.to_thread``.

        Returns a dict mapping module name to outcome: ``"success"``,
        ``"failed"``, or ``"skipped"``.
        """
        return asyncio.run(self._execute_async(*args, **kwargs))

    async def _execute_async(
        self, *args: Any, **kwargs: Any,
    ) -> dict[str, str]:
        results: dict[str, str] = {}
        failed_modules: set[str] = set()

        for wave_index, wave in enumerate(self._waves, start=1):
            # Determine which modules in this wave can actually run
            runnable: list[str] = []
            for name in wave:
                mod = self._modules[name]
                blocked_by = [
                    dep for dep in mod.depends_on if dep in failed_modules
                ]
                if blocked_by:
                    logger.warning(
                        "Skipping module '%s' because dependencies failed: %s",
                        name,
                        blocked_by,
                    )
                    results[name] = "skipped"
                    failed_modules.add(name)
                else:
                    runnable.append(name)

            if not runnable:
                continue

            logger.info(
                "Executing wave %d: [%s]",
                wave_index,
                ", ".join(runnable),
            )

            tasks = [
                asyncio.create_task(
                    self._run_module(name, *args, **kwargs),
                    name=name,
                )
                for name in runnable
            ]

            # Wait for all tasks in this wave. We use return_exceptions so
            # that one failure doesn't cancel siblings.
            outcomes = await asyncio.gather(*tasks, return_exceptions=True)

            for name, outcome in zip(runnable, outcomes):
                if isinstance(outcome, BaseException):
                    logger.error(
                        "Module '%s' failed: %s",
                        name,
                        outcome,
                    )
                    results[name] = "failed"
                    failed_modules.add(name)
                else:
                    results[name] = "success"

        return results

    async def _run_module(
        self, name: str, *args: Any, **kwargs: Any,
    ) -> None:
        """Run a single module's sync_func in a thread."""
        mod = self._modules[name]
        logger.info("Starting module '%s'", name)
        await asyncio.to_thread(mod.sync_func, *args, **kwargs)
        logger.info("Finished module '%s'", name)
