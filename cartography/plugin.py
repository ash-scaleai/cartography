"""
Plugin discovery and registration for cartography intel modules.

This module provides a plugin-based architecture for cartography, allowing
intel modules (providers) to be discovered either as:

1. **Built-in modules**: The traditional monolithic package where all providers
   are bundled together under ``cartography.intel.*``.
2. **Entry point plugins**: External packages that register themselves via the
   ``cartography.plugins`` entry point group in their ``pyproject.toml``.

Plugin Interface
----------------
Each plugin entry point must resolve to a module (or object) that exposes a
callable with the signature::

    start_<provider>_ingestion(neo4j_session, config)

The entry point *name* is used as the module/provider name (e.g. ``aws``,
``github``). For example, a third-party package ``cartography-plugin-acme``
would declare in its ``pyproject.toml``::

    [project.entry-points."cartography.plugins"]
    acme = "cartography_plugin_acme:start_acme_ingestion"

If the entry point value is a *module* rather than a direct callable, the
discovery code will look for a ``start_<name>_ingestion`` function inside
that module.

Backward Compatibility
----------------------
When no external plugins are installed, the system falls back to discovering
built-in modules under ``cartography.intel`` using the same ``pkgutil``-based
scan that ``Sync.list_intel_modules()`` has always used. This means existing
deployments that install cartography as a single package continue to work
without any configuration changes.

Example plugin ``pyproject.toml`` snippets
------------------------------------------

**AWS (built-in, would be used if AWS were split into its own package)**::

    [project.entry-points."cartography.plugins"]
    aws = "cartography.intel.aws:start_aws_ingestion"

**GitHub**::

    [project.entry-points."cartography.plugins"]
    github = "cartography.intel.github:start_github_ingestion"

**GCP**::

    [project.entry-points."cartography.plugins"]
    gcp = "cartography.intel.gcp:start_gcp_ingestion"
"""

from __future__ import annotations

import importlib
import logging
import re
import sys
from collections import OrderedDict
from pkgutil import iter_modules
from typing import Callable

logger = logging.getLogger(__name__)

# The entry point group name that external plugin packages use to register.
PLUGIN_ENTRY_POINT_GROUP = "cartography.plugins"

# Modules that are always handled specially and should not be loaded as plugins.
_INTERNAL_MODULES = frozenset({"analysis", "create_indexes", "ontology"})


def _entry_points_for_group(group: str):
    """Return entry points for *group*, compatible with Python 3.10+."""
    if sys.version_info >= (3, 12):
        from importlib.metadata import entry_points
        return entry_points(group=group)

    # Python 3.10 / 3.11: importlib.metadata.entry_points may return a dict
    from importlib.metadata import entry_points as _ep
    result = _ep(group=group)
    # In 3.10+ entry_points(group=...) should work, but just in case:
    if isinstance(result, dict):
        return result.get(group, [])
    return result


def discover_plugins() -> OrderedDict[str, Callable[..., None]]:
    """Discover all available cartography intel modules.

    Resolution order:

    1. Always include ``create-indexes`` first (internal).
    2. Load any modules registered via the ``cartography.plugins`` entry point
       group.  These take precedence over built-in modules with the same name.
    3. Fall back to built-in modules discovered under ``cartography.intel``
       (only for names not already provided by an entry point plugin).
    4. Always include ``ontology`` and ``analysis`` last (internal).

    Returns:
        An :class:`~collections.OrderedDict` mapping module names to their
        callable sync functions.
    """
    modules: OrderedDict[str, Callable[..., None]] = OrderedDict()

    # --- 1. Internal: create-indexes always first ---
    try:
        import cartography.intel.create_indexes
        modules["create-indexes"] = cartography.intel.create_indexes.run
    except ImportError:
        logger.warning("Built-in 'create_indexes' module not found; skipping.")

    # --- 2. Entry-point plugins ---
    plugin_names: set[str] = set()
    for ep in _entry_points_for_group(PLUGIN_ENTRY_POINT_GROUP):
        name = ep.name
        if name in _INTERNAL_MODULES:
            logger.debug(
                "Skipping entry-point plugin '%s' — reserved internal module name.",
                name,
            )
            continue
        try:
            loaded = ep.load()
        except Exception:
            logger.exception("Failed to load plugin entry point '%s'.", name)
            continue

        func = _resolve_sync_function(name, loaded)
        if func is not None:
            modules[name] = func
            plugin_names.add(name)
            logger.debug("Loaded plugin '%s' from entry point.", name)
        else:
            logger.warning(
                "Plugin entry point '%s' did not resolve to a valid sync function.",
                name,
            )

    # --- 3. Built-in modules (fallback for names not covered by plugins) ---
    builtin_modules = _discover_builtin_modules()
    for name, func in builtin_modules.items():
        if name not in modules:
            modules[name] = func

    # --- 4. Internal: ontology + analysis always last ---
    try:
        import cartography.intel.ontology
        modules["ontology"] = cartography.intel.ontology.run
    except ImportError:
        logger.warning("Built-in 'ontology' module not found; skipping.")

    try:
        import cartography.intel.analysis
        modules["analysis"] = cartography.intel.analysis.run
    except ImportError:
        logger.warning("Built-in 'analysis' module not found; skipping.")

    return modules


def _resolve_sync_function(
    name: str, loaded: object,
) -> Callable[..., None] | None:
    """Given a loaded entry-point value, return the sync callable.

    The entry point may resolve to:
    * A callable directly (the ``start_<name>_ingestion`` function itself).
    * A module that contains a ``start_<name>_ingestion`` function **or** a
      ``run`` function.

    Returns:
        The callable, or ``None`` if nothing suitable was found.
    """
    # Direct callable
    if callable(loaded) and not _is_module(loaded):
        return loaded

    # Module — look for start_<name>_ingestion or run()
    expected_func_name = f"start_{name}_ingestion"
    func = getattr(loaded, expected_func_name, None)
    if func is not None and callable(func):
        return func

    # Also accept a plain ``run`` function (used by create_indexes, analysis, etc.)
    func = getattr(loaded, "run", None)
    if func is not None and callable(func):
        return func

    return None


def _is_module(obj: object) -> bool:
    """Return True if *obj* is a Python module."""
    import types
    return isinstance(obj, types.ModuleType)


def _discover_builtin_modules() -> OrderedDict[str, Callable[..., None]]:
    """Discover built-in modules under ``cartography.intel`` via pkgutil.

    This mirrors the original logic from :meth:`Sync.list_intel_modules` but
    returns only the provider modules (excludes internal modules like
    ``analysis`` and ``create_indexes``).
    """
    modules: OrderedDict[str, Callable[..., None]] = OrderedDict()
    callable_regex = re.compile(r"^start_(.+)_ingestion$")

    try:
        import cartography.intel
        intel_path = cartography.intel.__path__
    except (ImportError, AttributeError):
        logger.warning("cartography.intel package not found; no built-in modules available.")
        return modules

    for module_info in iter_modules(intel_path):
        if module_info.name in _INTERNAL_MODULES:
            continue
        try:
            intel_module = importlib.import_module(
                f"cartography.intel.{module_info.name}",
            )
        except ImportError as e:
            logger.error(
                "Failed to import built-in module '%s'. Error: %s",
                module_info.name,
                e,
            )
            continue

        for attr_name, attr_value in intel_module.__dict__.items():
            if not callable(attr_value):
                continue
            match = callable_regex.match(attr_name)
            if match:
                modules[module_info.name] = attr_value
                break

    return modules


def get_available_module_names() -> list[str]:
    """Return the names of all discoverable modules (plugins + built-ins).

    This is a convenience wrapper useful for CLI help text and validation.
    """
    return list(discover_plugins().keys())
