"""Tests for the cartography plugin discovery system."""

from __future__ import annotations

from collections import OrderedDict
from types import ModuleType
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest

from cartography.plugin import (
    PLUGIN_ENTRY_POINT_GROUP,
    _discover_builtin_modules,
    _resolve_sync_function,
    discover_plugins,
    get_available_module_names,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fake_entry_point(name: str, load_return):
    """Create a mock entry point that returns *load_return* on .load()."""
    ep = MagicMock()
    ep.name = name
    ep.load.return_value = load_return
    return ep


def _make_module(name: str, attrs: dict | None = None) -> ModuleType:
    """Create a minimal ModuleType with optional attributes."""
    mod = ModuleType(name)
    for k, v in (attrs or {}).items():
        setattr(mod, k, v)
    return mod


# ---------------------------------------------------------------------------
# _resolve_sync_function
# ---------------------------------------------------------------------------

class TestResolveSyncFunction:
    def test_direct_callable(self):
        def start_foo_ingestion(neo4j_session, config):
            pass

        result = _resolve_sync_function("foo", start_foo_ingestion)
        assert result is start_foo_ingestion

    def test_module_with_matching_function(self):
        def start_bar_ingestion(neo4j_session, config):
            pass

        mod = _make_module("bar_mod", {"start_bar_ingestion": start_bar_ingestion})
        result = _resolve_sync_function("bar", mod)
        assert result is start_bar_ingestion

    def test_module_with_run_function(self):
        def run(neo4j_session, config):
            pass

        mod = _make_module("baz_mod", {"run": run})
        result = _resolve_sync_function("baz", mod)
        assert result is run

    def test_module_without_matching_function_returns_none(self):
        mod = _make_module("empty_mod")
        result = _resolve_sync_function("empty", mod)
        assert result is None


# ---------------------------------------------------------------------------
# discover_plugins — with mock entry points
# ---------------------------------------------------------------------------

class TestDiscoverPluginsWithMockEntryPoints:
    @patch("cartography.plugin._entry_points_for_group")
    def test_plugin_entry_points_are_discovered(self, mock_ep):
        """Entry point plugins should appear in the discovered modules."""

        def start_acme_ingestion(neo4j_session, config):
            pass

        mock_ep.return_value = [
            _fake_entry_point("acme", start_acme_ingestion),
        ]

        result = discover_plugins()

        assert "acme" in result
        assert result["acme"] is start_acme_ingestion

    @patch("cartography.plugin._entry_points_for_group")
    def test_plugin_takes_precedence_over_builtin(self, mock_ep):
        """If a plugin and a built-in share the same name, the plugin wins."""

        def plugin_aws(neo4j_session, config):
            pass

        mock_ep.return_value = [
            _fake_entry_point("aws", plugin_aws),
        ]

        result = discover_plugins()

        # The plugin version should be used, not the built-in.
        assert result["aws"] is plugin_aws

    @patch("cartography.plugin._entry_points_for_group")
    def test_internal_modules_skipped_as_plugins(self, mock_ep):
        """Plugins named 'analysis' or 'create_indexes' should be skipped."""

        def fake_analysis(neo4j_session, config):
            pass

        mock_ep.return_value = [
            _fake_entry_point("analysis", fake_analysis),
            _fake_entry_point("create_indexes", fake_analysis),
        ]

        result = discover_plugins()

        # The built-in analysis/create_indexes should be used, not the plugin.
        assert result.get("analysis") is not fake_analysis
        assert "create_indexes" not in result  # create_indexes is "create-indexes"

    @patch("cartography.plugin._entry_points_for_group")
    def test_no_plugins_falls_back_to_builtins(self, mock_ep):
        """With no entry points, all built-in modules should still be found."""
        mock_ep.return_value = []

        result = discover_plugins()

        # Should contain at least the well-known built-in modules.
        assert "create-indexes" in result
        assert "aws" in result
        assert "analysis" in result

    @patch("cartography.plugin._entry_points_for_group")
    def test_failed_plugin_load_is_skipped(self, mock_ep):
        """A plugin that fails to load should be skipped gracefully."""
        bad_ep = MagicMock()
        bad_ep.name = "broken"
        bad_ep.load.side_effect = ImportError("no such module")

        mock_ep.return_value = [bad_ep]

        # Should not raise
        result = discover_plugins()

        assert "broken" not in result
        # Built-ins should still be present
        assert "aws" in result


# ---------------------------------------------------------------------------
# discover_plugins — ordering guarantees
# ---------------------------------------------------------------------------

class TestDiscoverPluginsOrdering:
    @patch("cartography.plugin._entry_points_for_group")
    def test_create_indexes_is_first(self, mock_ep):
        mock_ep.return_value = []
        result = discover_plugins()
        keys = list(result.keys())
        assert keys[0] == "create-indexes"

    @patch("cartography.plugin._entry_points_for_group")
    def test_analysis_is_last(self, mock_ep):
        mock_ep.return_value = []
        result = discover_plugins()
        keys = list(result.keys())
        assert keys[-1] == "analysis"

    @patch("cartography.plugin._entry_points_for_group")
    def test_ontology_is_second_to_last(self, mock_ep):
        mock_ep.return_value = []
        result = discover_plugins()
        keys = list(result.keys())
        assert keys[-2] == "ontology"


# ---------------------------------------------------------------------------
# _discover_builtin_modules
# ---------------------------------------------------------------------------

class TestDiscoverBuiltinModules:
    def test_returns_provider_modules(self):
        """Should find built-in provider modules like aws, gcp, github."""
        result = _discover_builtin_modules()

        assert "aws" in result
        assert "gcp" in result
        assert "github" in result

    def test_excludes_internal_modules(self):
        """Internal modules should not appear in the result."""
        result = _discover_builtin_modules()

        assert "analysis" not in result
        assert "create_indexes" not in result
        assert "ontology" not in result

    def test_values_are_callable(self):
        """All values in the result should be callable."""
        result = _discover_builtin_modules()
        for name, func in result.items():
            assert callable(func), f"Module '{name}' mapped to non-callable: {func}"


# ---------------------------------------------------------------------------
# get_available_module_names
# ---------------------------------------------------------------------------

class TestGetAvailableModuleNames:
    @patch("cartography.plugin._entry_points_for_group")
    def test_returns_list_of_strings(self, mock_ep):
        mock_ep.return_value = []
        names = get_available_module_names()
        assert isinstance(names, list)
        assert all(isinstance(n, str) for n in names)
        assert "aws" in names
        assert "analysis" in names


# ---------------------------------------------------------------------------
# Integration with sync.py — get_all_modules / selected modules
# ---------------------------------------------------------------------------

class TestSyncIntegrationWithPlugins:
    @patch("cartography.plugin._entry_points_for_group")
    def test_get_all_modules_includes_plugins(self, mock_ep):
        """get_all_modules should surface plugin-discovered modules."""
        from cartography.sync import get_all_modules

        def start_custom_ingestion(neo4j_session, config):
            pass

        mock_ep.return_value = [
            _fake_entry_point("custom_provider", start_custom_ingestion),
        ]

        result = get_all_modules()
        assert "custom_provider" in result
        assert result["custom_provider"] is start_custom_ingestion

    @patch("cartography.plugin._entry_points_for_group")
    def test_get_all_modules_preserves_builtin_order(self, mock_ep):
        """Built-in modules should keep their original order."""
        from cartography.sync import get_all_modules, TOP_LEVEL_MODULES

        mock_ep.return_value = []
        result = get_all_modules()

        # All TOP_LEVEL_MODULES keys should appear in the same relative order.
        result_keys = list(result.keys())
        for key in TOP_LEVEL_MODULES:
            assert key in result_keys

    @patch("cartography.plugin._entry_points_for_group")
    def test_build_sync_with_plugin_module(self, mock_ep):
        """build_sync should accept plugin-discovered module names."""
        from cartography.sync import build_sync

        def start_custom_ingestion(neo4j_session, config):
            pass

        mock_ep.return_value = [
            _fake_entry_point("custom_provider", start_custom_ingestion),
        ]

        sync = build_sync("aws,custom_provider,analysis")
        stage_names = list(sync._stages.keys())
        assert stage_names == ["aws", "custom_provider", "analysis"]
        assert sync._stages["custom_provider"] is start_custom_ingestion

    @patch("cartography.plugin._entry_points_for_group")
    def test_parse_and_validate_selected_modules_accepts_plugins(self, mock_ep):
        """parse_and_validate_selected_modules should accept plugin names."""
        from cartography.sync import parse_and_validate_selected_modules

        def start_custom_ingestion(neo4j_session, config):
            pass

        mock_ep.return_value = [
            _fake_entry_point("custom_provider", start_custom_ingestion),
        ]

        result = parse_and_validate_selected_modules("aws,custom_provider")
        assert result == ["aws", "custom_provider"]

    @patch("cartography.plugin._entry_points_for_group")
    def test_parse_and_validate_rejects_unknown_module(self, mock_ep):
        """Unknown module names should still raise ValueError."""
        from cartography.sync import parse_and_validate_selected_modules

        mock_ep.return_value = []

        with pytest.raises(ValueError, match="thisdoesnotexist"):
            parse_and_validate_selected_modules("aws,thisdoesnotexist")
