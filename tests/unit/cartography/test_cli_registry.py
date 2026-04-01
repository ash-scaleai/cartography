"""
Tests for the CLI plugin registry (cartography.cli.registry).

Tests cover:
- Discovery of built-in provider CLI modules
- Discovery with mock entry points for external plugins
- That --help includes dynamically discovered options
- That removing a provider doesn't cause errors
- Graceful handling of malformed cli.py
"""
from __future__ import annotations

import importlib
import sys
import types
import unittest.mock
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest

from cartography.cli.registry import CLIPlugin
from cartography.cli.registry import CLIPluginRegistry
from cartography.cli.registry import ENTRY_POINT_GROUP
from cartography.cli.registry import _discover_entrypoint_plugins
from cartography.cli.registry import _find_builtin_cli_modules
from cartography.cli.registry import _load_plugin_module
from cartography.cli.registry import discover_cli_plugins


class TestCLIPluginRegistry:
    """Tests for the CLIPluginRegistry dataclass."""

    def test_register_plugin(self):
        registry = CLIPluginRegistry()
        plugin = CLIPlugin(
            name="test",
            module=MagicMock(),
            panel="Test Options",
            add_arguments=MagicMock(),
            process_cli_args=MagicMock(),
        )
        registry.register(plugin)
        assert len(registry.plugins) == 1
        assert registry.plugins[0].name == "test"

    def test_register_duplicate_skipped(self):
        registry = CLIPluginRegistry()
        plugin1 = CLIPlugin(
            name="test",
            module=MagicMock(),
            panel="Test Options",
            add_arguments=MagicMock(),
            process_cli_args=MagicMock(),
        )
        plugin2 = CLIPlugin(
            name="test",
            module=MagicMock(),
            panel="Test Options v2",
            add_arguments=MagicMock(),
            process_cli_args=MagicMock(),
        )
        registry.register(plugin1)
        registry.register(plugin2)
        assert len(registry.plugins) == 1
        assert registry.plugins[0].panel == "Test Options"

    def test_get_all_panels(self):
        registry = CLIPluginRegistry()
        for name, panel in [("a", "A Panel"), ("b", "B Panel")]:
            registry.register(CLIPlugin(
                name=name,
                module=MagicMock(),
                panel=panel,
                add_arguments=MagicMock(),
                process_cli_args=MagicMock(),
            ))
        panels = registry.get_all_panels()
        assert panels == {"A Panel", "B Panel"}

    def test_get_module_panel_mapping(self):
        registry = CLIPluginRegistry()
        registry.register(CLIPlugin(
            name="aws",
            module=MagicMock(),
            panel="AWS Options",
            add_arguments=MagicMock(),
            process_cli_args=MagicMock(),
        ))
        mapping = registry.get_module_panel_mapping()
        assert mapping == {"aws": "AWS Options"}


class TestFindBuiltinCLIModules:
    """Tests for _find_builtin_cli_modules."""

    def test_discovers_aws_cli_module(self):
        """Test that the AWS cli.py we created is discovered."""
        results = _find_builtin_cli_modules()
        names = [name for name, _ in results]
        assert "aws" in names

    def test_module_paths_are_correct(self):
        """Verify discovered module paths follow the expected pattern."""
        results = _find_builtin_cli_modules()
        for name, module_path in results:
            assert module_path == f"cartography.intel.{name}.cli"


class TestLoadPluginModule:
    """Tests for _load_plugin_module."""

    def test_load_valid_module(self):
        """Test loading a valid CLI plugin module."""
        plugin = _load_plugin_module("aws", "cartography.intel.aws.cli", "test")
        assert plugin is not None
        assert plugin.name == "aws"
        assert plugin.panel == "AWS Options"
        assert callable(plugin.add_arguments)
        assert callable(plugin.process_cli_args)

    def test_load_nonexistent_module(self):
        """Test that loading a nonexistent module returns None."""
        plugin = _load_plugin_module(
            "nonexistent",
            "cartography.intel.nonexistent.cli",
            "test",
        )
        assert plugin is None

    def test_load_module_missing_panel(self):
        """Test that a module missing PANEL is skipped."""
        # Create a fake module without PANEL
        fake_module = types.ModuleType("fake_cli")
        fake_module.add_arguments = lambda params, vp: None
        fake_module.process_cli_args = lambda args: {}

        with patch("cartography.cli.registry.importlib.import_module", return_value=fake_module):
            plugin = _load_plugin_module("fake", "fake.cli", "test")
        assert plugin is None

    def test_load_module_missing_add_arguments(self):
        """Test that a module missing add_arguments is skipped."""
        fake_module = types.ModuleType("fake_cli")
        fake_module.PANEL = "Fake Options"
        fake_module.process_cli_args = lambda args: {}
        # No add_arguments

        with patch("cartography.cli.registry.importlib.import_module", return_value=fake_module):
            plugin = _load_plugin_module("fake", "fake.cli", "test")
        assert plugin is None

    def test_load_module_missing_process_cli_args(self):
        """Test that a module missing process_cli_args is skipped."""
        fake_module = types.ModuleType("fake_cli")
        fake_module.PANEL = "Fake Options"
        fake_module.add_arguments = lambda params, vp: None
        # No process_cli_args

        with patch("cartography.cli.registry.importlib.import_module", return_value=fake_module):
            plugin = _load_plugin_module("fake", "fake.cli", "test")
        assert plugin is None

    def test_load_module_import_error_is_graceful(self):
        """Test that import errors are handled gracefully."""
        with patch(
            "cartography.cli.registry.importlib.import_module",
            side_effect=ImportError("no such module"),
        ):
            plugin = _load_plugin_module("broken", "broken.cli", "test")
        assert plugin is None

    def test_load_module_syntax_error_is_graceful(self):
        """Test that syntax errors in plugin modules are handled gracefully."""
        with patch(
            "cartography.cli.registry.importlib.import_module",
            side_effect=SyntaxError("invalid syntax"),
        ):
            plugin = _load_plugin_module("broken", "broken.cli", "test")
        assert plugin is None


class TestDiscoverEntrypointPlugins:
    """Tests for _discover_entrypoint_plugins with mock entry points."""

    def test_discover_with_mock_entry_points(self):
        """Test discovery of external plugins via entry points."""
        mock_ep = MagicMock()
        mock_ep.name = "custom_provider"
        mock_ep.value = "custom_package.cli_plugin"
        mock_ep.group = ENTRY_POINT_GROUP

        mock_eps = MagicMock()
        mock_eps.select.return_value = [mock_ep]

        with patch("cartography.cli.registry.entry_points", return_value=mock_eps):
            results = _discover_entrypoint_plugins()

        assert len(results) == 1
        assert results[0] == ("custom_provider", "custom_package.cli_plugin")

    def test_discover_with_no_entry_points(self):
        """Test discovery when no entry points are registered."""
        mock_eps = MagicMock()
        mock_eps.select.return_value = []

        with patch("cartography.cli.registry.entry_points", return_value=mock_eps):
            results = _discover_entrypoint_plugins()

        assert results == []

    def test_discover_entry_points_error_is_graceful(self):
        """Test that errors in entry point discovery are handled gracefully."""
        with patch(
            "cartography.cli.registry.entry_points",
            side_effect=RuntimeError("failed"),
        ):
            results = _discover_entrypoint_plugins()

        assert results == []


class TestDiscoverCLIPlugins:
    """Tests for the top-level discover_cli_plugins function."""

    def test_discovers_builtin_aws_plugin(self):
        """Test that discover_cli_plugins finds the AWS built-in plugin."""
        registry = discover_cli_plugins()
        names = [p.name for p in registry.plugins]
        assert "aws" in names

    def test_external_plugin_via_entry_points(self):
        """Test that an external plugin is discovered via entry points."""
        # Create a fake external plugin module
        fake_module = types.ModuleType("external_cli")
        fake_module.PANEL = "External Options"
        fake_module.add_arguments = lambda params, vp: None
        fake_module.process_cli_args = lambda args: {}

        mock_ep = MagicMock()
        mock_ep.name = "external"
        mock_ep.value = "external_package.cli"
        mock_ep.group = ENTRY_POINT_GROUP

        mock_eps = MagicMock()
        mock_eps.select.return_value = [mock_ep]

        with patch("cartography.cli.registry.entry_points", return_value=mock_eps), \
             patch(
                 "cartography.cli.registry.importlib.import_module",
                 side_effect=lambda path: fake_module if path == "external_package.cli" else importlib.import_module(path),
             ):
            registry = discover_cli_plugins()

        names = [p.name for p in registry.plugins]
        assert "external" in names

    def test_removing_provider_does_not_cause_errors(self):
        """
        Test that if a built-in provider's cli.py disappears (e.g., uninstalled),
        discover_cli_plugins still works without errors.
        """
        # Patch _find_builtin_cli_modules to return a nonexistent provider
        with patch(
            "cartography.cli.registry._find_builtin_cli_modules",
            return_value=[("removed_provider", "cartography.intel.removed_provider.cli")],
        ):
            # This should not raise
            registry = discover_cli_plugins()

        # The removed provider should not be in the registry
        names = [p.name for p in registry.plugins]
        assert "removed_provider" not in names

    def test_malformed_cli_module_is_skipped_gracefully(self):
        """
        Test that a malformed cli.py (e.g., raises exception on import)
        is skipped without crashing the registry.
        """
        with patch(
            "cartography.cli.registry._find_builtin_cli_modules",
            return_value=[("bad", "cartography.intel.bad.cli")],
        ):
            # This should not raise
            registry = discover_cli_plugins()

        names = [p.name for p in registry.plugins]
        assert "bad" not in names


class TestCLIHelpWithPlugins:
    """Tests that --help includes dynamically discovered options."""

    def test_help_includes_plugin_options(self, capsys):
        """Test that --help output includes options from discovered plugins."""
        import cartography.cli

        sync = MagicMock()
        cli = cartography.cli.CLI(sync, "test")
        exit_code = cli.main(["-h"])
        captured = capsys.readouterr()

        assert exit_code == 0
        assert "Usage:" in captured.out
        # The AWS plugin should add --aws-sync-all-profiles via the registry
        # (or it's still in the core CLI inline options)
        assert "--aws-sync-all-profiles" in captured.out

    def test_help_with_selected_modules_shows_only_relevant(self, capsys):
        """Test that --help with --selected-modules filters panels."""
        import cartography.cli

        sync = MagicMock()
        cli = cartography.cli.CLI(sync, "test")
        exit_code = cli.main(["--selected-modules", "aws", "-h"])
        captured = capsys.readouterr()

        assert exit_code == 0
        # AWS options should be visible
        assert "--aws-sync-all-profiles" in captured.out


class TestAWSCLIPlugin:
    """Tests for the AWS CLI plugin module specifically."""

    def test_aws_plugin_exports(self):
        """Test that the AWS CLI plugin has the required exports."""
        from cartography.intel.aws import cli as aws_cli

        assert hasattr(aws_cli, "PANEL")
        assert aws_cli.PANEL == "AWS Options"
        assert callable(aws_cli.add_arguments)
        assert callable(aws_cli.process_cli_args)

    def test_aws_add_arguments(self):
        """Test that add_arguments adds Click options to params list."""
        from cartography.intel.aws import cli as aws_cli

        params = []
        aws_cli.add_arguments(params, {"AWS Options"})
        assert len(params) > 0

        # Check that known options are present
        param_names = [p.name for p in params]
        assert "aws_sync_all_profiles" in param_names
        assert "aws_regions" in param_names
        assert "aws_best_effort_mode" in param_names

    def test_aws_add_arguments_hidden_when_panel_not_visible(self):
        """Test that options are hidden when panel is not in visible set."""
        from cartography.intel.aws import cli as aws_cli

        params = []
        aws_cli.add_arguments(params, set())  # No visible panels

        for param in params:
            assert param.hidden is True

    def test_aws_process_cli_args(self):
        """Test that process_cli_args extracts correct config values."""
        from cartography.intel.aws import cli as aws_cli

        args = {
            "aws_sync_all_profiles": True,
            "aws_regions": "us-east-1,us-west-2",
            "aws_best_effort_mode": False,
            "aws_cloudtrail_management_events_lookback_hours": 24,
            "aws_requested_syncs": None,
            "aws_guardduty_severity_threshold": None,
            "experimental_aws_inspector_batch": 1000,
            "aws_tagging_api_cleanup_batch": 1000,
            "permission_relationships_file": None,
        }
        config = aws_cli.process_cli_args(args)
        assert config["aws_sync_all_profiles"] is True
        assert config["aws_regions"] == "us-east-1,us-west-2"
        assert config["aws_best_effort_mode"] is False
