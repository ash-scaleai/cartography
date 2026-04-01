"""
CLI Plugin Registry for Cartography.

This module provides dynamic discovery of CLI plugins, both built-in
(found by scanning cartography/intel/*/cli.py) and external (registered
via the ``cartography.cli_plugins`` entry point group).

Each CLI plugin module must export:
    - ``PANEL``: str - The help panel name for grouping options in --help.
    - ``add_arguments(parser, visible_panels)``: Adds CLI options to the
      Click command's params list.
    - ``process_cli_args(args: dict) -> dict``: Extracts config key-value
      pairs from parsed CLI arguments.

Example plugin module (cartography/intel/aws/cli.py)::

    import click
    import typer

    PANEL = "AWS Options"

    def add_arguments(params: list, visible_panels: set[str]) -> None:
        hidden = PANEL not in visible_panels
        params.append(click.Option(
            ["--aws-sync-all-profiles"],
            is_flag=True, default=False,
            help="Enable AWS sync for all discovered named profiles.",
        ))

    def process_cli_args(args: dict) -> dict:
        return {
            "aws_sync_all_profiles": args.get("aws_sync_all_profiles", False),
        }
"""
from __future__ import annotations

import importlib
import logging
import os
import sys
from dataclasses import dataclass
from dataclasses import field
from pathlib import Path
from types import ModuleType

if sys.version_info >= (3, 12):
    from importlib.metadata import entry_points
else:
    from importlib.metadata import entry_points

logger = logging.getLogger(__name__)

# The entry point group name for external CLI plugins
ENTRY_POINT_GROUP = "cartography.cli_plugins"


@dataclass
class CLIPlugin:
    """Represents a discovered CLI plugin."""

    name: str
    module: ModuleType
    panel: str
    add_arguments: callable  # type: ignore[type-arg]
    process_cli_args: callable  # type: ignore[type-arg]


@dataclass
class CLIPluginRegistry:
    """
    Registry of all discovered CLI plugins.

    This is the central coordination point for CLI plugin discovery and
    management. It collects plugins from two sources:

    1. Built-in providers: Discovered by scanning ``cartography/intel/*/cli.py``
    2. External plugins: Discovered via the ``cartography.cli_plugins`` entry
       point group

    Usage::

        registry = discover_cli_plugins()
        for plugin in registry.plugins:
            plugin.add_arguments(command.params, visible_panels)
    """

    plugins: list[CLIPlugin] = field(default_factory=list)
    _plugin_names: set[str] = field(default_factory=set)

    def register(self, plugin: CLIPlugin) -> None:
        """Register a plugin, avoiding duplicates by name."""
        if plugin.name in self._plugin_names:
            logger.debug(
                "Skipping duplicate CLI plugin '%s'",
                plugin.name,
            )
            return
        self.plugins.append(plugin)
        self._plugin_names.add(plugin.name)

    def get_all_panels(self) -> set[str]:
        """Return set of all panel names from registered plugins."""
        return {p.panel for p in self.plugins}

    def get_module_panel_mapping(self) -> dict[str, str]:
        """Return mapping of plugin name to panel name."""
        return {p.name: p.panel for p in self.plugins}


def _find_builtin_cli_modules() -> list[tuple[str, str]]:
    """
    Scan cartography/intel/*/cli.py for built-in provider CLI modules.

    Returns:
        List of (provider_name, module_path) tuples.
        e.g. [("aws", "cartography.intel.aws.cli")]
    """
    results = []

    # Find the cartography/intel directory
    try:
        import cartography.intel

        intel_dir = Path(os.path.dirname(cartography.intel.__file__))
    except (ImportError, AttributeError):
        logger.warning("Could not locate cartography.intel package")
        return results

    if not intel_dir.is_dir():
        return results

    for child in sorted(intel_dir.iterdir()):
        if not child.is_dir():
            continue
        if child.name.startswith("_"):
            continue
        cli_file = child / "cli.py"
        if cli_file.is_file():
            module_path = f"cartography.intel.{child.name}.cli"
            results.append((child.name, module_path))

    return results


def _load_plugin_module(
    name: str,
    module_path: str,
    source: str,
) -> CLIPlugin | None:
    """
    Load a CLI plugin module and validate it has the required exports.

    Args:
        name: Human-readable name for the plugin (e.g., "aws").
        module_path: Dotted Python module path to import.
        source: Description of where the plugin was found (for logging).

    Returns:
        A CLIPlugin instance, or None if the module is invalid.
    """
    try:
        module = importlib.import_module(module_path)
    except Exception:
        logger.warning(
            "Failed to import CLI plugin '%s' from %s (%s). Skipping.",
            name,
            module_path,
            source,
            exc_info=True,
        )
        return None

    # Validate required exports
    panel = getattr(module, "PANEL", None)
    add_arguments_fn = getattr(module, "add_arguments", None)
    process_cli_args_fn = getattr(module, "process_cli_args", None)

    if panel is None:
        logger.warning(
            "CLI plugin '%s' (%s) does not export PANEL. Skipping.",
            name,
            module_path,
        )
        return None

    if not callable(add_arguments_fn):
        logger.warning(
            "CLI plugin '%s' (%s) does not export a callable add_arguments. Skipping.",
            name,
            module_path,
        )
        return None

    if not callable(process_cli_args_fn):
        logger.warning(
            "CLI plugin '%s' (%s) does not export a callable process_cli_args. Skipping.",
            name,
            module_path,
        )
        return None

    return CLIPlugin(
        name=name,
        module=module,
        panel=panel,
        add_arguments=add_arguments_fn,
        process_cli_args=process_cli_args_fn,
    )


def _discover_entrypoint_plugins() -> list[tuple[str, str]]:
    """
    Discover external CLI plugins via the cartography.cli_plugins entry point group.

    Returns:
        List of (plugin_name, module_path) tuples.
    """
    results = []
    try:
        eps = entry_points()
        # Python 3.12+ returns a SelectableGroups; older returns dict
        if hasattr(eps, "select"):
            group_eps = eps.select(group=ENTRY_POINT_GROUP)
        elif isinstance(eps, dict):
            group_eps = eps.get(ENTRY_POINT_GROUP, [])
        else:
            group_eps = [ep for ep in eps if ep.group == ENTRY_POINT_GROUP]

        for ep in group_eps:
            results.append((ep.name, ep.value))
    except Exception:
        logger.warning(
            "Failed to discover entry point plugins for group '%s'",
            ENTRY_POINT_GROUP,
            exc_info=True,
        )

    return results


def discover_cli_plugins() -> CLIPluginRegistry:
    """
    Discover all CLI plugins from built-in providers and entry points.

    Built-in providers are found by scanning ``cartography/intel/*/cli.py``.
    External plugins are found via the ``cartography.cli_plugins`` entry point
    group.

    Returns:
        A CLIPluginRegistry containing all discovered plugins.
    """
    registry = CLIPluginRegistry()

    # 1. Discover built-in provider CLI modules
    for name, module_path in _find_builtin_cli_modules():
        plugin = _load_plugin_module(name, module_path, source="built-in")
        if plugin is not None:
            registry.register(plugin)
            logger.debug("Registered built-in CLI plugin: %s", name)

    # 2. Discover external plugins via entry points
    for name, module_path in _discover_entrypoint_plugins():
        plugin = _load_plugin_module(name, module_path, source="entry-point")
        if plugin is not None:
            registry.register(plugin)
            logger.debug("Registered entry-point CLI plugin: %s", name)

    logger.debug(
        "Discovered %d CLI plugins: %s",
        len(registry.plugins),
        [p.name for p in registry.plugins],
    )

    return registry
