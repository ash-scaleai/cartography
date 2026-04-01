"""
Explicit dependency graph for cartography sync modules.

Each intel module declares a MODULE_METADATA constant describing its name,
what it depends on, and what Neo4j node labels it provides. This lets
cartography validate the sync order at startup instead of relying on
implicit OrderedDict positioning.
"""
from __future__ import annotations

import importlib
import logging
from collections import defaultdict
from dataclasses import dataclass
from dataclasses import field
from pkgutil import iter_modules
from typing import Iterable

import cartography.intel

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ModuleMetadata:
    """Metadata for a single cartography sync module.

    Attributes:
        name: Dotted module identifier, e.g. ``"aws.ec2.instances"``.
        depends_on: Module names that must run before this one.
        provides: Neo4j node labels created by this module (documentation/validation).
    """
    name: str
    depends_on: list[str] = field(default_factory=list)
    provides: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("ModuleMetadata.name must not be empty")


def validate_dependency_graph(modules: list[ModuleMetadata]) -> None:
    """Check that all dependency references resolve and that there are no cycles.

    Raises ``ValueError`` with a clear message on the first problem found.
    """
    registered = {m.name for m in modules}

    # --- 1. Check for duplicate names ---
    seen: set[str] = set()
    for m in modules:
        if m.name in seen:
            raise ValueError(
                f"Duplicate module name '{m.name}' found in the dependency graph",
            )
        seen.add(m.name)

    # --- 2. Check that every depends_on target is registered ---
    for m in modules:
        for dep in m.depends_on:
            if dep not in registered:
                raise ValueError(
                    f"Module '{m.name}' depends on '{dep}' which is not registered",
                )

    # --- 3. Cycle detection (Kahn's algorithm) ---
    _detect_cycles(modules)


def _detect_cycles(modules: list[ModuleMetadata]) -> None:
    """Raise ``ValueError`` if the dependency graph contains a cycle."""
    # Build adjacency list and in-degree map
    in_degree: dict[str, int] = {m.name: 0 for m in modules}
    dependents: dict[str, list[str]] = defaultdict(list)

    for m in modules:
        for dep in m.depends_on:
            dependents[dep].append(m.name)
            in_degree[m.name] += 1

    # Seed the queue with nodes that have no incoming edges
    queue = [name for name, deg in in_degree.items() if deg == 0]
    visited_count = 0

    while queue:
        node = queue.pop(0)
        visited_count += 1
        for dependent in dependents[node]:
            in_degree[dependent] -= 1
            if in_degree[dependent] == 0:
                queue.append(dependent)

    if visited_count != len(modules):
        # Find the nodes still in the cycle for a useful error message
        cycle_members = sorted(
            name for name, deg in in_degree.items() if deg > 0
        )
        raise ValueError(
            f"Dependency cycle detected among modules: {cycle_members}",
        )


def discover_module_metadata() -> list[ModuleMetadata]:
    """Walk ``cartography.intel.*`` and collect every ``MODULE_METADATA`` constant.

    Returns a flat list of all :class:`ModuleMetadata` instances found.
    """
    all_metadata: list[ModuleMetadata] = []

    for module_info in iter_modules(cartography.intel.__path__):
        fqn = f"cartography.intel.{module_info.name}"
        try:
            mod = importlib.import_module(fqn)
        except Exception:
            logger.debug("Could not import %s for metadata discovery", fqn, exc_info=True)
            continue

        _collect_from_module(mod, all_metadata)

    return all_metadata


def _collect_from_module(mod: object, dest: list[ModuleMetadata]) -> None:
    """Append MODULE_METADATA entries from *mod* to *dest*.

    MODULE_METADATA may be a single :class:`ModuleMetadata` or an iterable of them.
    """
    raw = getattr(mod, "MODULE_METADATA", None)
    if raw is None:
        return

    if isinstance(raw, ModuleMetadata):
        dest.append(raw)
    elif isinstance(raw, Iterable):
        for item in raw:
            if isinstance(item, ModuleMetadata):
                dest.append(item)
            else:
                logger.warning(
                    "Ignoring non-ModuleMetadata item in MODULE_METADATA of %s",
                    getattr(mod, "__name__", repr(mod)),
                )
    else:
        logger.warning(
            "MODULE_METADATA in %s is not a ModuleMetadata or iterable thereof",
            getattr(mod, "__name__", repr(mod)),
        )
