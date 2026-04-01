"""
Tests for the CLI split into per-provider modules.

Verifies that:
1. The CLI parses the same arguments as before the split.
2. Help output includes all provider options.
3. Provider CLI modules are importable and well-formed.
4. Backward compatibility is maintained (cartography.cli.CLI and cartography.cli.main).
"""
import importlib
import unittest.mock

import typer

import cartography.cli
from cartography.cli.core import CLI
from cartography.cli.core import PROVIDER_CLI_MODULES
from cartography.cli.core import STATUS_FAILURE
from cartography.cli.core import STATUS_SUCCESS


class TestCLIBackwardCompatibility:
    """Verify backward compatibility of the CLI split."""

    def test_cli_class_importable_from_package(self):
        """CLI class should be importable from cartography.cli."""
        assert cartography.cli.CLI is CLI

    def test_main_importable_from_package(self):
        """main function should be importable from cartography.cli."""
        from cartography.cli.core import main
        assert cartography.cli.main is main

    def test_status_codes_importable(self):
        """Status codes should be importable from cartography.cli."""
        assert cartography.cli.STATUS_SUCCESS == 0
        assert cartography.cli.STATUS_FAILURE == 1
        assert cartography.cli.STATUS_KEYBOARD_INTERRUPT == 130

    def test_cli_basic_invocation(self):
        """CLI should work with basic neo4j-uri argument."""
        sync = unittest.mock.MagicMock()
        cli = CLI(sync, "test")
        exit_code = cli.main(["--neo4j-uri", "bolt://localhost:7687"])
        assert exit_code == STATUS_SUCCESS
        sync.run.assert_called_once()

    def test_cli_version_flag(self, capsys):
        """--version should print version info and exit 0."""
        sync = unittest.mock.MagicMock()
        cli = CLI(sync, "test")
        exit_code = cli.main(["--version"])
        captured = capsys.readouterr()
        assert exit_code == 0
        assert "cartography release " in captured.out
        assert "commit revision " in captured.out
        sync.run.assert_not_called()

    def test_cli_debug_alias(self):
        """-d should work as alias for --debug/--verbose."""
        sync = unittest.mock.MagicMock()
        cli = CLI(sync, "test")
        exit_code = cli.main(["-d", "--neo4j-uri", "bolt://localhost:7687"])
        assert exit_code == STATUS_SUCCESS
        sync.run.assert_called_once()

    def test_cli_short_help_flag(self, capsys):
        """-h should show help and exit 0."""
        sync = unittest.mock.MagicMock()
        cli = CLI(sync, "test")
        exit_code = cli.main(["-h"])
        captured = capsys.readouterr()
        assert exit_code == 0
        assert "Usage:" in captured.out
        sync.run.assert_not_called()

    def test_cli_handles_typer_exit_code_zero(self):
        """Typer exit with code 0 should return STATUS_SUCCESS."""
        sync = unittest.mock.MagicMock()
        cli = CLI(sync, "test")

        def _app(*_args, **_kwargs):
            raise typer.Exit(code=0)

        with unittest.mock.patch.object(cli, "_build_app", return_value=_app):
            exit_code = cli.main([])

        assert exit_code == 0

    def test_cli_neo4j_liveness_check_timeout(self):
        """--neo4j-liveness-check-timeout should be passed to Config."""
        sync = unittest.mock.MagicMock()
        cli = CLI(sync, "test")
        cli.main([
            "--neo4j-uri", "bolt://localhost:7687",
            "--neo4j-liveness-check-timeout", "60",
        ])
        sync.run.assert_called_once()
        config = sync.run.call_args[0][1]
        assert config.neo4j_liveness_check_timeout == 60


class TestProviderCLIModules:
    """Verify that all provider CLI modules are well-formed."""

    def test_all_provider_modules_importable(self):
        """All registered provider CLI modules should be importable."""
        for module_path in PROVIDER_CLI_MODULES:
            mod = importlib.import_module(module_path)
            assert hasattr(mod, "PANEL"), f"{module_path} missing PANEL"
            assert hasattr(mod, "MODULE_NAME"), f"{module_path} missing MODULE_NAME"
            assert hasattr(mod, "OPTION_DEFINITIONS"), f"{module_path} missing OPTION_DEFINITIONS"
            assert hasattr(mod, "process_cli_args"), f"{module_path} missing process_cli_args"
            assert callable(mod.process_cli_args), f"{module_path}.process_cli_args not callable"

    def test_option_definitions_format(self):
        """Each OPTION_DEFINITIONS entry should have the correct structure."""
        for module_path in PROVIDER_CLI_MODULES:
            mod = importlib.import_module(module_path)
            for defn in mod.OPTION_DEFINITIONS:
                assert len(defn) == 6, (
                    f"{module_path}: OPTION_DEFINITIONS entry should be a 6-tuple, "
                    f"got {len(defn)}: {defn[0] if defn else '?'}"
                )
                param_name, param_type, cli_flag, help_text, default, extra = defn
                assert isinstance(param_name, str), f"{module_path}: param_name should be str"
                assert isinstance(cli_flag, str), f"{module_path}: cli_flag should be str"
                assert cli_flag.startswith("--"), f"{module_path}: cli_flag should start with --"
                assert isinstance(help_text, str), f"{module_path}: help_text should be str"
                assert isinstance(extra, dict), f"{module_path}: extra_kwargs should be dict"

    def test_module_names_unique(self):
        """Each provider should have a unique MODULE_NAME."""
        names = []
        for module_path in PROVIDER_CLI_MODULES:
            mod = importlib.import_module(module_path)
            names.append(mod.MODULE_NAME)
        assert len(names) == len(set(names)), f"Duplicate MODULE_NAMEs found: {names}"


class TestProviderOptionPassthrough:
    """Verify that provider-specific CLI options pass through to Config correctly."""

    def test_aws_options(self):
        """AWS options should be set on the Config object."""
        sync = unittest.mock.MagicMock()
        cli = CLI(sync, "test")
        cli.main([
            "--neo4j-uri", "bolt://localhost:7687",
            "--aws-sync-all-profiles",
            "--aws-best-effort-mode",
            "--experimental-aws-inspector-batch", "500",
        ])
        config = sync.run.call_args[0][1]
        assert config.aws_sync_all_profiles is True
        assert config.aws_best_effort_mode is True
        assert config.experimental_aws_inspector_batch == 500

    def test_azure_options(self):
        """Azure options should be set on the Config object."""
        sync = unittest.mock.MagicMock()
        cli = CLI(sync, "test")
        cli.main([
            "--neo4j-uri", "bolt://localhost:7687",
            "--azure-sync-all-subscriptions",
            "--azure-sp-auth",
            "--azure-tenant-id", "test-tenant",
        ])
        config = sync.run.call_args[0][1]
        assert config.azure_sync_all_subscriptions is True
        assert config.azure_sp_auth is True
        assert config.azure_tenant_id == "test-tenant"

    def test_gcp_options(self):
        """GCP options should be set on the Config object."""
        sync = unittest.mock.MagicMock()
        cli = CLI(sync, "test")
        cli.main([
            "--neo4j-uri", "bolt://localhost:7687",
            "--gcp-requested-syncs", "compute,iam",
        ])
        config = sync.run.call_args[0][1]
        assert config.gcp_requested_syncs == "compute,iam"

    def test_okta_options(self):
        """Okta options should be set on the Config object."""
        sync = unittest.mock.MagicMock()
        cli = CLI(sync, "test")
        cli.main([
            "--neo4j-uri", "bolt://localhost:7687",
            "--okta-org-id", "test-org",
            "--okta-base-domain", "custom.okta.com",
        ])
        config = sync.run.call_args[0][1]
        assert config.okta_org_id == "test-org"
        assert config.okta_base_domain == "custom.okta.com"

    def test_statsd_options(self):
        """StatsD options should be set on the Config object."""
        sync = unittest.mock.MagicMock()
        cli = CLI(sync, "test")
        cli.main([
            "--neo4j-uri", "bolt://localhost:7687",
            "--statsd-enabled",
            "--statsd-prefix", "myapp",
            "--statsd-host", "10.0.0.1",
            "--statsd-port", "9125",
        ])
        config = sync.run.call_args[0][1]
        assert config.statsd_enabled is True
        assert config.statsd_prefix == "myapp"
        assert config.statsd_host == "10.0.0.1"
        assert config.statsd_port == 9125


class TestHelpOutput:
    """Verify that help output includes all expected provider sections."""

    def test_help_includes_all_provider_panels(self, capsys):
        """Help output should include panel headers for all providers."""
        sync = unittest.mock.MagicMock()
        cli = CLI(sync, "test")
        cli.main(["-h"])
        captured = capsys.readouterr()
        help_text = captured.out

        expected_panels = [
            "Core Options",
            "Neo4j Connection",
            "AWS Options",
            "Azure Options",
            "GCP Options",
            "Okta Options",
            "GitHub Options",
            "GitLab Options",
            "StatsD Metrics",
            "Analysis Options",
        ]
        for panel in expected_panels:
            assert panel in help_text, f"Help output missing panel: {panel}"

    def test_help_includes_key_options(self, capsys):
        """Help output should include key CLI option flags."""
        sync = unittest.mock.MagicMock()
        cli = CLI(sync, "test")
        cli.main(["-h"])
        captured = capsys.readouterr()
        help_text = captured.out

        key_flags = [
            "--neo4j-uri",
            "--selected-modules",
            "--aws-sync-all-profiles",
            "--azure-sp-auth",
            "--gcp-requested-syncs",
            "--okta-org-id",
            "--github-config-env-var",
            "--statsd-enabled",
        ]
        for flag in key_flags:
            assert flag in help_text, f"Help output missing flag: {flag}"
