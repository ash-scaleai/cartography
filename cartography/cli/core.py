"""
Core CLI module for cartography.

This module contains the CLI class, core (non-provider) options, and the main
entrypoint. Provider-specific options are defined in each provider's cli.py
module under cartography/intel/<provider>/cli.py.

Each provider CLI module exports:
    - PANEL: str - the help panel name
    - MODULE_NAME: str - the module name for --selected-modules filtering
    - OPTION_DEFINITIONS: list of option specs
    - process_cli_args(args) -> dict: processes raw CLI values into Config kwargs
"""
import getpass
import logging
import os
import sys
from types import ModuleType
from typing import Any
from typing import TYPE_CHECKING

import typer
from typing_extensions import Annotated

from cartography.config import Config
from cartography.version import get_release_version_and_commit_revision

if TYPE_CHECKING:
    from cartography.sync import Sync

logger = logging.getLogger(__name__)

# Keep these local to avoid importing cartography.util (and its heavy deps) on --help/--version paths.
STATUS_SUCCESS = 0
STATUS_FAILURE = 1
STATUS_KEYBOARD_INTERRUPT = 130

# Help Panel Names for non-provider options
PANEL_CORE = "Core Options"
PANEL_NEO4J = "Neo4j Connection"
PANEL_STATSD = "StatsD Metrics"
PANEL_ANALYSIS = "Analysis Options"

# Panels that should always be shown (not module-specific)
ALWAYS_SHOW_PANELS = {PANEL_CORE, PANEL_NEO4J, PANEL_STATSD, PANEL_ANALYSIS}

# Registry of all provider CLI modules.
# Each entry maps a module name to its import path.
# These are imported lazily when building the CLI.
PROVIDER_CLI_MODULES: list[str] = [
    "cartography.intel.aws.cli",
    "cartography.intel.azure.cli",
    "cartography.intel.entra.cli",
    "cartography.intel.gcp.cli",
    "cartography.intel.oci.cli",
    "cartography.intel.okta.cli",
    "cartography.intel.github.cli",
    "cartography.intel.gitlab.cli",
    "cartography.intel.digitalocean.cli",
    "cartography.intel.crowdstrike.cli",
    "cartography.intel.jamf.cli",
    "cartography.intel.kandji.cli",
    "cartography.intel.kubernetes.cli",
    "cartography.intel.cve.cli",
    "cartography.intel.pagerduty.cli",
    "cartography.intel.gsuite.cli",
    "cartography.intel.googleworkspace.cli",
    "cartography.intel.lastpass.cli",
    "cartography.intel.jumpcloud.cli",
    "cartography.intel.bigfix.cli",
    "cartography.intel.duo.cli",
    "cartography.intel.workday.cli",
    "cartography.intel.semgrep.cli",
    "cartography.intel.snipeit.cli",
    "cartography.intel.cloudflare.cli",
    "cartography.intel.tailscale.cli",
    "cartography.intel.openai.cli",
    "cartography.intel.anthropic.cli",
    "cartography.intel.sentry.cli",
    "cartography.intel.subimage.cli",
    "cartography.intel.airbyte.cli",
    "cartography.intel.docker_scout.cli",
    "cartography.intel.trivy.cli",
    "cartography.intel.syft.cli",
    "cartography.intel.aibom.cli",
    "cartography.intel.ubuntu.cli",
    "cartography.intel.ontology.cli",
    "cartography.intel.scaleway.cli",
    "cartography.intel.sentinelone.cli",
    "cartography.intel.keycloak.cli",
    "cartography.intel.slack.cli",
    "cartography.intel.spacelift.cli",
]


def _load_provider_cli_modules() -> list[ModuleType]:
    """
    Import and return all provider CLI modules.

    Returns:
        List of imported provider CLI module objects.
    """
    import importlib
    modules = []
    for module_path in PROVIDER_CLI_MODULES:
        mod = importlib.import_module(module_path)
        modules.append(mod)
    return modules


def _build_module_panels_map(provider_modules: list[ModuleType]) -> dict[str, str]:
    """
    Build the MODULE_PANELS mapping from loaded provider modules.

    Returns:
        Dict mapping module name -> panel name.
    """
    panels = {}
    for mod in provider_modules:
        panels[mod.MODULE_NAME] = mod.PANEL
    # Add non-provider panels
    panels["analysis"] = PANEL_ANALYSIS
    return panels


def _version_callback(value: bool) -> None:
    """
    Handle eager --version processing before command execution.
    """
    if not value:
        return

    release_version, commit_revision = get_release_version_and_commit_revision()
    typer.echo(
        f"cartography release {release_version}, commit revision {commit_revision}"
    )
    raise typer.Exit(code=0)


def _parse_selected_modules_from_argv(
    argv: list[str],
    module_panels: dict[str, str],
) -> set[str]:
    """
    Pre-parse argv to extract --selected-modules value for dynamic help visibility.

    Returns:
        Set of visible panel names. If no modules specified, returns all panels.
    """
    selected_modules: str | None = None

    for i, arg in enumerate(argv):
        if arg == "--selected-modules" and i + 1 < len(argv):
            selected_modules = argv[i + 1]
            break
        elif arg.startswith("--selected-modules="):
            selected_modules = arg.split("=", 1)[1]
            break

    if not selected_modules:
        return set(module_panels.values()) | ALWAYS_SHOW_PANELS

    visible_panels = set(ALWAYS_SHOW_PANELS)
    for module in selected_modules.split(","):
        module = module.strip().lower()
        if module in module_panels:
            visible_panels.add(module_panels[module])

    return visible_panels


class CLI:
    """
    Command Line Interface for cartography using Typer.

    This class provides the main command line interface for cartography, handling
    argument parsing, configuration, and execution of sync operations.

    Note:
        We maintain this class-based structure (rather than using module-level Typer
        functions like cartography-rules does) for backward compatibility. The existing
        codebase and tests rely on being able to:

        1. Inject a custom Sync object: `CLI(sync=my_custom_sync)`
        2. Set a custom program name: `CLI(prog="my-cartography")`
        3. Call main() with explicit argv: `cli.main(["--neo4j-uri", "..."])`

        This allows users to create custom sync configurations and test the CLI
        with mock objects. See tests/integration/cartography/test_cli.py for examples.

    Attributes:
        sync: A cartography.sync.Sync object for executing sync operations.
        prog: The name of the command line program for display in help output.

    Example:
        >>> sync = cartography.sync.build_default_sync()
        >>> cli = CLI(sync=sync, prog="cartography")
        >>> exit_code = cli.main(["--neo4j-uri", "bolt://localhost:7687"])
    """

    def __init__(
        self,
        sync: "Sync | None" = None,
        prog: str | None = None,
    ):
        # Defer default sync construction until command execution to keep --help fast.
        self.sync = sync
        self.prog = prog

    def main(self, argv: list[str]) -> int:
        """
        Main entrypoint for the command line interface.

        This method parses command line arguments, configures logging and various
        service connections, validates input parameters, and executes the cartography
        sync operation with the provided configuration.

        Args:
            argv: The command line arguments to parse. Should be a list of strings
                  representing the command line parameters (excluding the program name).

        Returns:
            An integer exit code. Returns 0 for successful execution, or a non-zero
            value for errors or keyboard interruption.
        """
        # Load provider CLI modules
        provider_modules = _load_provider_cli_modules()
        module_panels = _build_module_panels_map(provider_modules)

        # Pre-parse argv to determine which help panels to show
        visible_panels = _parse_selected_modules_from_argv(argv, module_panels)

        # Build the Typer app with our sync object in closure
        app = self._build_app(visible_panels, provider_modules)

        # Typer doesn't return exit codes directly, so we catch SystemExit
        try:
            app(argv, standalone_mode=False)
            return STATUS_SUCCESS
        except typer.Exit as e:
            if e.exit_code is None:
                return STATUS_SUCCESS
            return e.exit_code
        except SystemExit as e:
            if e.code is None:
                return STATUS_SUCCESS
            elif isinstance(e.code, int):
                return e.code
            else:
                # e.code can be a string message in some cases
                return STATUS_FAILURE
        except KeyboardInterrupt:
            return STATUS_KEYBOARD_INTERRUPT
        except Exception as e:
            logger.error("Cartography failed: %s", e)
            return STATUS_FAILURE

    def _build_app(
        self,
        visible_panels: set[str],
        provider_modules: list[ModuleType],
    ) -> typer.Typer:
        """
        Build the Typer application with all CLI options.

        Provider options are registered from each provider's CLI module via their
        OPTION_DEFINITIONS. Core options (logging, Neo4j, StatsD, analysis) are
        defined directly here.

        Args:
            visible_panels: Set of panel names to show in help. Options in other
                panels are hidden but still functional (backward compatibility).
            provider_modules: List of loaded provider CLI modules.

        Returns:
            A configured Typer application.
        """
        app = typer.Typer(
            name=self.prog,
            help=(
                "Cartography consolidates infrastructure assets and the relationships "
                "between them in an intuitive graph view. This application can be used "
                "to pull configuration data from multiple sources, load it into Neo4j, "
                "and run arbitrary enrichment and analysis on that data."
            ),
            epilog="For more documentation please visit: https://github.com/cartography-cncf/cartography",
            no_args_is_help=False,
            add_completion=True,
            context_settings={"help_option_names": ["-h", "--help"]},
        )

        # Store reference to self for use in the command function
        cli_instance = self
        # Capture provider modules for use in the command closure
        _provider_modules = provider_modules

        @app.command()  # type: ignore[misc]
        def run(
            # =================================================================
            # Core Options
            # =================================================================
            # DEPRECATED: `--verbose` will be removed in v1.0.0. Use `--debug` instead.
            verbose: Annotated[
                bool,
                typer.Option(
                    "--verbose",
                    "-v",
                    "--debug",
                    "-d",
                    help=(
                        "Enable verbose logging for cartography. "
                        "DEPRECATED: --verbose will be removed in v1.0.0; use --debug instead."
                    ),
                    rich_help_panel=PANEL_CORE,
                ),
            ] = False,
            show_version: Annotated[
                bool,
                typer.Option(
                    "--version",
                    callback=_version_callback,
                    is_eager=True,
                    help="Show cartography release version and commit revision, then exit.",
                    rich_help_panel=PANEL_CORE,
                ),
            ] = False,
            quiet: Annotated[
                bool,
                typer.Option(
                    "--quiet",
                    "-q",
                    help="Restrict cartography logging to warnings and errors only.",
                    rich_help_panel=PANEL_CORE,
                ),
            ] = False,
            selected_modules: Annotated[
                str | None,
                typer.Option(
                    "--selected-modules",
                    help=(
                        "Comma-separated list of cartography top-level modules to sync. "
                        'Example: "aws,gcp" to run AWS and GCP modules. '
                        "If not specified, cartography will run all available modules. "
                        'We recommend including "create-indexes" first and "analysis" last.'
                    ),
                    rich_help_panel=PANEL_CORE,
                ),
            ] = None,
            update_tag: Annotated[
                int | None,
                typer.Option(
                    "--update-tag",
                    help=(
                        "A unique tag to apply to all Neo4j nodes and relationships created "
                        "or updated during the sync run. Used by cleanup jobs to identify stale data. "
                        "By default, cartography will use a UNIX timestamp."
                    ),
                    rich_help_panel=PANEL_CORE,
                ),
            ] = None,
            async_fetch: Annotated[
                bool,
                typer.Option(
                    "--async-fetch",
                    help=(
                        "Run independent provider sync stages concurrently using asyncio. "
                        "Stages like 'create-indexes' and 'analysis' still run sequentially. "
                        "This is an opt-in experimental feature; the default is sequential execution."
                    ),
                    rich_help_panel=PANEL_CORE,
                ),
            ] = False,
            cleanup_threshold: Annotated[
                float,
                typer.Option(
                    "--cleanup-threshold",
                    help=(
                        "Minimum ratio (0.0-1.0) of current vs. previous record counts required "
                        "to proceed with cleanup. If the current count drops below this fraction "
                        "of the previous count, cleanup is skipped as a safety net. Default: 0.5."
                    ),
                    min=0.0,
                    max=1.0,
                    rich_help_panel=PANEL_CORE,
                ),
            ] = 0.5,
            skip_cleanup_safety: Annotated[
                bool,
                typer.Option(
                    "--skip-cleanup-safety",
                    help=(
                        "Disable the cleanup safety net entirely. When set, cleanup always runs "
                        "regardless of record count changes between sync runs."
                    ),
                    rich_help_panel=PANEL_CORE,
                ),
            ] = False,
            # =================================================================
            # Neo4j Connection Options
            # =================================================================
            neo4j_uri: Annotated[
                str,
                typer.Option(
                    "--neo4j-uri",
                    help=(
                        "A valid Neo4j URI to sync against. See "
                        "https://neo4j.com/docs/browser-manual/current/operations/dbms-connection/#uri-scheme"
                    ),
                    rich_help_panel=PANEL_NEO4J,
                ),
            ] = "bolt://localhost:7687",
            neo4j_user: Annotated[
                str | None,
                typer.Option(
                    "--neo4j-user",
                    help="A username with which to authenticate to Neo4j.",
                    rich_help_panel=PANEL_NEO4J,
                ),
            ] = None,
            neo4j_password_env_var: Annotated[
                str | None,
                typer.Option(
                    "--neo4j-password-env-var",
                    help="The name of an environment variable containing the Neo4j password.",
                    rich_help_panel=PANEL_NEO4J,
                ),
            ] = None,
            neo4j_password_prompt: Annotated[
                bool,
                typer.Option(
                    "--neo4j-password-prompt",
                    help="Present an interactive prompt for the Neo4j password. Supersedes other password methods.",
                    rich_help_panel=PANEL_NEO4J,
                ),
            ] = False,
            neo4j_max_connection_lifetime: Annotated[
                int,
                typer.Option(
                    "--neo4j-max-connection-lifetime",
                    help="Time in seconds for the Neo4j driver to consider a TCP connection alive. Default: 3600.",
                    rich_help_panel=PANEL_NEO4J,
                ),
            ] = 3600,
            neo4j_liveness_check_timeout: Annotated[
                int | None,
                typer.Option(
                    "--neo4j-liveness-check-timeout",
                    help=(
                        "Time in seconds that a connection can be idle before the driver performs a liveness check "
                        "(RESET ping) before reusing it. Helps prevent SessionExpired or ConnectionResetError on "
                        "Aura or clustered Neo4j instances that close idle connections server-side. "
                        "Uses the Neo4j driver default when not specified."
                    ),
                    rich_help_panel=PANEL_NEO4J,
                ),
            ] = None,
            neo4j_database: Annotated[
                str | None,
                typer.Option(
                    "--neo4j-database",
                    help="The name of the database in Neo4j to connect to. Uses Neo4j default if not specified.",
                    rich_help_panel=PANEL_NEO4J,
                ),
            ] = None,
            # =================================================================
            # AWS Options (from cartography.intel.aws.cli)
            # =================================================================
            aws_sync_all_profiles: Annotated[
                bool,
                typer.Option(
                    "--aws-sync-all-profiles",
                    help=(
                        "Enable AWS sync for all discovered named profiles. "
                        "Cartography will discover all configured AWS named profiles and run the AWS sync "
                        'for each profile not named "default".'
                    ),
                    rich_help_panel="AWS Options",
                    hidden="AWS Options" not in visible_panels,
                ),
            ] = False,
            aws_regions: Annotated[
                str | None,
                typer.Option(
                    "--aws-regions",
                    help=(
                        "[EXPERIMENTAL] Comma-separated list of AWS regions to sync. "
                        'Example: "us-east-1,us-east-2". '
                        "CAUTION: Previously synced regions not in this list will have their assets deleted."
                    ),
                    rich_help_panel="AWS Options",
                    hidden="AWS Options" not in visible_panels,
                ),
            ] = None,
            aws_best_effort_mode: Annotated[
                bool,
                typer.Option(
                    "--aws-best-effort-mode",
                    help="Continue syncing other accounts if one fails, raising exceptions at the end.",
                    rich_help_panel="AWS Options",
                    hidden="AWS Options" not in visible_panels,
                ),
            ] = False,
            aws_cloudtrail_management_events_lookback_hours: Annotated[
                int | None,
                typer.Option(
                    "--aws-cloudtrail-management-events-lookback-hours",
                    help="Number of hours back to retrieve CloudTrail management events. Not retrieved if not specified.",
                    rich_help_panel="AWS Options",
                    hidden="AWS Options" not in visible_panels,
                ),
            ] = None,
            aws_requested_syncs: Annotated[
                str | None,
                typer.Option(
                    "--aws-requested-syncs",
                    help=(
                        "Comma-separated list of AWS resources to sync. "
                        'Example: "ecr,s3,ec2:instance". See cartography.intel.aws.resources for full list.'
                    ),
                    rich_help_panel="AWS Options",
                    hidden="AWS Options" not in visible_panels,
                ),
            ] = None,
            aws_guardduty_severity_threshold: Annotated[
                str | None,
                typer.Option(
                    "--aws-guardduty-severity-threshold",
                    help="GuardDuty severity threshold. Valid values: LOW, MEDIUM, HIGH, CRITICAL.",
                    rich_help_panel="AWS Options",
                    hidden="AWS Options" not in visible_panels,
                ),
            ] = None,
            experimental_aws_inspector_batch: Annotated[
                int,
                typer.Option(
                    "--experimental-aws-inspector-batch",
                    help="[EXPERIMENTAL] Batch size for AWS Inspector findings sync. Default: 1000.",
                    rich_help_panel="AWS Options",
                    hidden="AWS Options" not in visible_panels,
                ),
            ] = 1000,
            aws_tagging_api_cleanup_batch: Annotated[
                int,
                typer.Option(
                    "--aws-tagging-api-cleanup-batch",
                    help="Batch size for Resource Groups Tagging API cleanup (AWSTag nodes). Default: 1000.",
                    rich_help_panel="AWS Options",
                    hidden="AWS Options" not in visible_panels,
                ),
            ] = 1000,
            permission_relationships_file: Annotated[
                str,
                typer.Option(
                    "--permission-relationships-file",
                    help="Path to the AWS permission relationships mapping file.",
                    rich_help_panel="AWS Options",
                    hidden="AWS Options" not in visible_panels,
                ),
            ] = "cartography/data/permission_relationships.yaml",
            # =================================================================
            # Azure Options (from cartography.intel.azure.cli)
            # =================================================================
            azure_sync_all_subscriptions: Annotated[
                bool,
                typer.Option(
                    "--azure-sync-all-subscriptions",
                    help="Enable Azure sync for all discovered subscriptions.",
                    rich_help_panel="Azure Options",
                    hidden="Azure Options" not in visible_panels,
                ),
            ] = False,
            azure_sp_auth: Annotated[
                bool,
                typer.Option(
                    "--azure-sp-auth",
                    help="Use Service Principal authentication for Azure sync.",
                    rich_help_panel="Azure Options",
                    hidden="Azure Options" not in visible_panels,
                ),
            ] = False,
            azure_tenant_id: Annotated[
                str | None,
                typer.Option(
                    "--azure-tenant-id",
                    help="Azure Tenant ID for Service Principal Authentication.",
                    rich_help_panel="Azure Options",
                    hidden="Azure Options" not in visible_panels,
                ),
            ] = None,
            azure_client_id: Annotated[
                str | None,
                typer.Option(
                    "--azure-client-id",
                    help="Azure Client ID for Service Principal Authentication.",
                    rich_help_panel="Azure Options",
                    hidden="Azure Options" not in visible_panels,
                ),
            ] = None,
            azure_client_secret_env_var: Annotated[
                str | None,
                typer.Option(
                    "--azure-client-secret-env-var",
                    help="Environment variable name containing Azure Client Secret.",
                    rich_help_panel="Azure Options",
                    hidden="Azure Options" not in visible_panels,
                ),
            ] = None,
            azure_subscription_id: Annotated[
                str | None,
                typer.Option(
                    "--azure-subscription-id",
                    help="The Azure Subscription ID to sync.",
                    rich_help_panel="Azure Options",
                    hidden="Azure Options" not in visible_panels,
                ),
            ] = None,
            azure_permission_relationships_file: Annotated[
                str,
                typer.Option(
                    "--azure-permission-relationships-file",
                    help="Path to the Azure permission relationships mapping file.",
                    rich_help_panel="Azure Options",
                    hidden="Azure Options" not in visible_panels,
                ),
            ] = "cartography/data/azure_permission_relationships.yaml",
            # =================================================================
            # Entra ID Options (from cartography.intel.entra.cli)
            # =================================================================
            entra_tenant_id: Annotated[
                str | None,
                typer.Option(
                    "--entra-tenant-id",
                    help="Entra Tenant ID for Service Principal Authentication.",
                    rich_help_panel="Entra ID Options",
                    hidden="Entra ID Options" not in visible_panels,
                ),
            ] = None,
            entra_client_id: Annotated[
                str | None,
                typer.Option(
                    "--entra-client-id",
                    help="Entra Client ID for Service Principal Authentication.",
                    rich_help_panel="Entra ID Options",
                    hidden="Entra ID Options" not in visible_panels,
                ),
            ] = None,
            entra_client_secret_env_var: Annotated[
                str | None,
                typer.Option(
                    "--entra-client-secret-env-var",
                    help="Environment variable name containing Entra Client Secret.",
                    rich_help_panel="Entra ID Options",
                    hidden="Entra ID Options" not in visible_panels,
                ),
            ] = None,
            # =================================================================
            # GCP Options (from cartography.intel.gcp.cli)
            # =================================================================
            gcp_requested_syncs: Annotated[
                str | None,
                typer.Option(
                    "--gcp-requested-syncs",
                    help=(
                        "Comma-separated list of GCP resources to sync. "
                        'Example: "compute,iam,storage". See cartography.intel.gcp.resources for full list.'
                    ),
                    rich_help_panel="GCP Options",
                    hidden="GCP Options" not in visible_panels,
                ),
            ] = None,
            gcp_permission_relationships_file: Annotated[
                str,
                typer.Option(
                    "--gcp-permission-relationships-file",
                    help="Path to the GCP permission relationships mapping file.",
                    rich_help_panel="GCP Options",
                    hidden="GCP Options" not in visible_panels,
                ),
            ] = "cartography/data/gcp_permission_relationships.yaml",
            # =================================================================
            # OCI Options (from cartography.intel.oci.cli)
            # =================================================================
            oci_sync_all_profiles: Annotated[
                bool,
                typer.Option(
                    "--oci-sync-all-profiles",
                    help='Enable OCI sync for all discovered named profiles (excluding "DEFAULT").',
                    rich_help_panel="OCI Options",
                    hidden="OCI Options" not in visible_panels,
                ),
            ] = False,
            # =================================================================
            # Okta Options (from cartography.intel.okta.cli)
            # =================================================================
            okta_org_id: Annotated[
                str | None,
                typer.Option(
                    "--okta-org-id",
                    help="Okta organizational ID to sync. Required for Okta module.",
                    rich_help_panel="Okta Options",
                    hidden="Okta Options" not in visible_panels,
                ),
            ] = None,
            okta_api_key_env_var: Annotated[
                str | None,
                typer.Option(
                    "--okta-api-key-env-var",
                    help="Environment variable name containing Okta API key.",
                    rich_help_panel="Okta Options",
                    hidden="Okta Options" not in visible_panels,
                ),
            ] = None,
            okta_base_domain: Annotated[
                str,
                typer.Option(
                    "--okta-base-domain",
                    help="Base domain for Okta API requests. Defaults to 'okta.com'. "
                    "Set this if your organization uses a custom Okta domain.",
                    rich_help_panel="Okta Options",
                    hidden="Okta Options" not in visible_panels,
                ),
            ] = "okta.com",
            okta_saml_role_regex: Annotated[
                str,
                typer.Option(
                    "--okta-saml-role-regex",
                    help="Regex to map Okta groups to AWS roles. Must contain {{role}} and {{accountid}} tags.",
                    rich_help_panel="Okta Options",
                    hidden="Okta Options" not in visible_panels,
                ),
            ] = r"^aws\#\S+\#(?{{role}}[\w\-]+)\#(?{{accountid}}\d+)$",
            # =================================================================
            # GitHub Options (from cartography.intel.github.cli)
            # =================================================================
            github_config_env_var: Annotated[
                str | None,
                typer.Option(
                    "--github-config-env-var",
                    help="Environment variable name containing Base64 encoded GitHub config.",
                    rich_help_panel="GitHub Options",
                    hidden="GitHub Options" not in visible_panels,
                ),
            ] = None,
            github_commit_lookback_days: Annotated[
                int,
                typer.Option(
                    "--github-commit-lookback-days",
                    help="Number of days to look back for GitHub commit tracking. Default: 30.",
                    rich_help_panel="GitHub Options",
                    hidden="GitHub Options" not in visible_panels,
                ),
            ] = 30,
            # =================================================================
            # GitLab Options (from cartography.intel.gitlab.cli)
            # =================================================================
            gitlab_url: Annotated[
                str,
                typer.Option(
                    "--gitlab-url",
                    help="GitLab instance URL. Defaults to https://gitlab.com.",
                    rich_help_panel="GitLab Options",
                    hidden="GitLab Options" not in visible_panels,
                ),
            ] = "https://gitlab.com",
            gitlab_token_env_var: Annotated[
                str | None,
                typer.Option(
                    "--gitlab-token-env-var",
                    help="Environment variable name containing GitLab personal access token.",
                    rich_help_panel="GitLab Options",
                    hidden="GitLab Options" not in visible_panels,
                ),
            ] = None,
            gitlab_organization_id: Annotated[
                int | None,
                typer.Option(
                    "--gitlab-organization-id",
                    help="GitLab organization (top-level group) ID to sync.",
                    rich_help_panel="GitLab Options",
                    hidden="GitLab Options" not in visible_panels,
                ),
            ] = None,
            gitlab_commits_since_days: Annotated[
                int,
                typer.Option(
                    "--gitlab-commits-since-days",
                    help="Number of days of commit history to fetch. Default: 90.",
                    rich_help_panel="GitLab Options",
                    hidden="GitLab Options" not in visible_panels,
                ),
            ] = 90,
            # =================================================================
            # DigitalOcean Options (from cartography.intel.digitalocean.cli)
            # =================================================================
            digitalocean_token_env_var: Annotated[
                str | None,
                typer.Option(
                    "--digitalocean-token-env-var",
                    help="Environment variable name containing DigitalOcean access token.",
                    rich_help_panel="DigitalOcean Options",
                    hidden="DigitalOcean Options" not in visible_panels,
                ),
            ] = None,
            # =================================================================
            # CrowdStrike Options (from cartography.intel.crowdstrike.cli)
            # =================================================================
            crowdstrike_client_id_env_var: Annotated[
                str | None,
                typer.Option(
                    "--crowdstrike-client-id-env-var",
                    help="Environment variable name containing CrowdStrike client ID.",
                    rich_help_panel="CrowdStrike Options",
                    hidden="CrowdStrike Options" not in visible_panels,
                ),
            ] = None,
            crowdstrike_client_secret_env_var: Annotated[
                str | None,
                typer.Option(
                    "--crowdstrike-client-secret-env-var",
                    help="Environment variable name containing CrowdStrike client secret.",
                    rich_help_panel="CrowdStrike Options",
                    hidden="CrowdStrike Options" not in visible_panels,
                ),
            ] = None,
            crowdstrike_api_url: Annotated[
                str | None,
                typer.Option(
                    "--crowdstrike-api-url",
                    help="CrowdStrike API URL for self-hosted instances.",
                    rich_help_panel="CrowdStrike Options",
                    hidden="CrowdStrike Options" not in visible_panels,
                ),
            ] = None,
            # =================================================================
            # Jamf Options (from cartography.intel.jamf.cli)
            # =================================================================
            jamf_base_uri: Annotated[
                str | None,
                typer.Option(
                    "--jamf-base-uri",
                    help="Jamf base URI, e.g. https://hostname.com/JSSResource.",
                    rich_help_panel="Jamf Options",
                    hidden="Jamf Options" not in visible_panels,
                ),
            ] = None,
            jamf_user: Annotated[
                str | None,
                typer.Option(
                    "--jamf-user",
                    help="Username to authenticate to Jamf.",
                    rich_help_panel="Jamf Options",
                    hidden="Jamf Options" not in visible_panels,
                ),
            ] = None,
            jamf_password_env_var: Annotated[
                str | None,
                typer.Option(
                    "--jamf-password-env-var",
                    help="Environment variable name containing Jamf password.",
                    rich_help_panel="Jamf Options",
                    hidden="Jamf Options" not in visible_panels,
                ),
            ] = None,
            # =================================================================
            # Kandji Options (from cartography.intel.kandji.cli)
            # =================================================================
            kandji_base_uri: Annotated[
                str | None,
                typer.Option(
                    "--kandji-base-uri",
                    help="Kandji base URI, e.g. https://company.api.kandji.io.",
                    rich_help_panel="Kandji Options",
                    hidden="Kandji Options" not in visible_panels,
                ),
            ] = None,
            kandji_tenant_id: Annotated[
                str | None,
                typer.Option(
                    "--kandji-tenant-id",
                    help="Kandji tenant ID.",
                    rich_help_panel="Kandji Options",
                    hidden="Kandji Options" not in visible_panels,
                ),
            ] = None,
            kandji_token_env_var: Annotated[
                str | None,
                typer.Option(
                    "--kandji-token-env-var",
                    help="Environment variable name containing Kandji API token.",
                    rich_help_panel="Kandji Options",
                    hidden="Kandji Options" not in visible_panels,
                ),
            ] = None,
            # =================================================================
            # Kubernetes Options (from cartography.intel.kubernetes.cli)
            # =================================================================
            k8s_kubeconfig: Annotated[
                str | None,
                typer.Option(
                    "--k8s-kubeconfig",
                    help="Path to kubeconfig file for K8s cluster(s).",
                    rich_help_panel="Kubernetes Options",
                    hidden="Kubernetes Options" not in visible_panels,
                ),
            ] = None,
            managed_kubernetes: Annotated[
                str | None,
                typer.Option(
                    "--managed-kubernetes",
                    help="Type of managed Kubernetes service (e.g., 'eks').",
                    rich_help_panel="Kubernetes Options",
                    hidden="Kubernetes Options" not in visible_panels,
                ),
            ] = None,
            # =================================================================
            # CVE Options (from cartography.intel.cve.cli)
            # =================================================================
            nist_cve_url: Annotated[
                str,
                typer.Option(
                    "--nist-cve-url",
                    help="Base URL for NIST CVE data.",
                    rich_help_panel="CVE Options",
                    hidden="CVE Options" not in visible_panels,
                ),
            ] = "https://services.nvd.nist.gov/rest/json/cves/2.0/",
            cve_enabled: Annotated[
                bool,
                typer.Option(
                    "--cve-enabled",
                    help="Enable CVE data sync from NIST.",
                    rich_help_panel="CVE Options",
                    hidden="CVE Options" not in visible_panels,
                ),
            ] = False,
            cve_api_key_env_var: Annotated[
                str | None,
                typer.Option(
                    "--cve-api-key-env-var",
                    help="Environment variable name containing NIST NVD API v2.0 key.",
                    rich_help_panel="CVE Options",
                    hidden="CVE Options" not in visible_panels,
                ),
            ] = None,
            # =================================================================
            # PagerDuty Options (from cartography.intel.pagerduty.cli)
            # =================================================================
            pagerduty_api_key_env_var: Annotated[
                str | None,
                typer.Option(
                    "--pagerduty-api-key-env-var",
                    help="Environment variable name containing PagerDuty API key.",
                    rich_help_panel="PagerDuty Options",
                    hidden="PagerDuty Options" not in visible_panels,
                ),
            ] = None,
            pagerduty_request_timeout: Annotated[
                int | None,
                typer.Option(
                    "--pagerduty-request-timeout",
                    help="Timeout in seconds for PagerDuty API requests.",
                    rich_help_panel="PagerDuty Options",
                    hidden="PagerDuty Options" not in visible_panels,
                ),
            ] = None,
            # =================================================================
            # GSuite Options (from cartography.intel.gsuite.cli)
            # =================================================================
            gsuite_auth_method: Annotated[
                str,
                typer.Option(
                    "--gsuite-auth-method",
                    help='GSuite authentication method: "delegated", "oauth", or "default".',
                    rich_help_panel="GSuite Options",
                    hidden="GSuite Options" not in visible_panels,
                ),
            ] = "delegated",
            gsuite_tokens_env_var: Annotated[
                str,
                typer.Option(
                    "--gsuite-tokens-env-var",
                    help="Environment variable name containing GSuite credentials.",
                    rich_help_panel="GSuite Options",
                    hidden="GSuite Options" not in visible_panels,
                ),
            ] = "GSUITE_GOOGLE_APPLICATION_CREDENTIALS",
            # =================================================================
            # Google Workspace Options (from cartography.intel.googleworkspace.cli)
            # =================================================================
            googleworkspace_auth_method: Annotated[
                str,
                typer.Option(
                    "--googleworkspace-auth-method",
                    help='Google Workspace authentication method: "delegated", "oauth", or "default".',
                    rich_help_panel="Google Workspace Options",
                    hidden="Google Workspace Options" not in visible_panels,
                ),
            ] = "delegated",
            googleworkspace_tokens_env_var: Annotated[
                str,
                typer.Option(
                    "--googleworkspace-tokens-env-var",
                    help="Environment variable name containing Google Workspace credentials.",
                    rich_help_panel="Google Workspace Options",
                    hidden="Google Workspace Options" not in visible_panels,
                ),
            ] = "GOOGLEWORKSPACE_GOOGLE_APPLICATION_CREDENTIALS",
            # =================================================================
            # LastPass Options (from cartography.intel.lastpass.cli)
            # =================================================================
            lastpass_cid_env_var: Annotated[
                str | None,
                typer.Option(
                    "--lastpass-cid-env-var",
                    help="Environment variable name containing LastPass CID.",
                    rich_help_panel="LastPass Options",
                    hidden="LastPass Options" not in visible_panels,
                ),
            ] = None,
            lastpass_provhash_env_var: Annotated[
                str | None,
                typer.Option(
                    "--lastpass-provhash-env-var",
                    help="Environment variable name containing LastPass provhash.",
                    rich_help_panel="LastPass Options",
                    hidden="LastPass Options" not in visible_panels,
                ),
            ] = None,
            # =================================================================
            # JumpCloud Options (from cartography.intel.jumpcloud.cli)
            # =================================================================
            jumpcloud_api_key_env_var: Annotated[
                str | None,
                typer.Option(
                    "--jumpcloud-api-key-env-var",
                    help="Environment variable name containing JumpCloud API key.",
                    rich_help_panel="JumpCloud Options",
                    hidden="JumpCloud Options" not in visible_panels,
                ),
            ] = None,
            jumpcloud_org_id: Annotated[
                str | None,
                typer.Option(
                    "--jumpcloud-org-id",
                    help="JumpCloud organization ID used as the tenant identifier.",
                    rich_help_panel="JumpCloud Options",
                    hidden="JumpCloud Options" not in visible_panels,
                ),
            ] = None,
            # =================================================================
            # BigFix Options (from cartography.intel.bigfix.cli)
            # =================================================================
            bigfix_username: Annotated[
                str | None,
                typer.Option(
                    "--bigfix-username",
                    help="BigFix username for authentication.",
                    rich_help_panel="BigFix Options",
                    hidden="BigFix Options" not in visible_panels,
                ),
            ] = None,
            bigfix_password_env_var: Annotated[
                str | None,
                typer.Option(
                    "--bigfix-password-env-var",
                    help="Environment variable name containing BigFix password.",
                    rich_help_panel="BigFix Options",
                    hidden="BigFix Options" not in visible_panels,
                ),
            ] = None,
            bigfix_root_url: Annotated[
                str | None,
                typer.Option(
                    "--bigfix-root-url",
                    help="BigFix API URL.",
                    rich_help_panel="BigFix Options",
                    hidden="BigFix Options" not in visible_panels,
                ),
            ] = None,
            # =================================================================
            # Duo Options (from cartography.intel.duo.cli)
            # =================================================================
            duo_api_key_env_var: Annotated[
                str | None,
                typer.Option(
                    "--duo-api-key-env-var",
                    help="Environment variable name containing Duo API key.",
                    rich_help_panel="Duo Options",
                    hidden="Duo Options" not in visible_panels,
                ),
            ] = None,
            duo_api_secret_env_var: Annotated[
                str | None,
                typer.Option(
                    "--duo-api-secret-env-var",
                    help="Environment variable name containing Duo API secret.",
                    rich_help_panel="Duo Options",
                    hidden="Duo Options" not in visible_panels,
                ),
            ] = None,
            duo_api_hostname: Annotated[
                str | None,
                typer.Option(
                    "--duo-api-hostname",
                    help="Duo API hostname.",
                    rich_help_panel="Duo Options",
                    hidden="Duo Options" not in visible_panels,
                ),
            ] = None,
            # =================================================================
            # Workday Options (from cartography.intel.workday.cli)
            # =================================================================
            workday_api_url: Annotated[
                str | None,
                typer.Option(
                    "--workday-api-url",
                    help="Workday API URL.",
                    rich_help_panel="Workday Options",
                    hidden="Workday Options" not in visible_panels,
                ),
            ] = None,
            workday_api_login: Annotated[
                str | None,
                typer.Option(
                    "--workday-api-login",
                    help="Workday API login username.",
                    rich_help_panel="Workday Options",
                    hidden="Workday Options" not in visible_panels,
                ),
            ] = None,
            workday_api_password_env_var: Annotated[
                str | None,
                typer.Option(
                    "--workday-api-password-env-var",
                    help="Environment variable name containing Workday API password.",
                    rich_help_panel="Workday Options",
                    hidden="Workday Options" not in visible_panels,
                ),
            ] = None,
            # =================================================================
            # Semgrep Options (from cartography.intel.semgrep.cli)
            # =================================================================
            semgrep_app_token_env_var: Annotated[
                str | None,
                typer.Option(
                    "--semgrep-app-token-env-var",
                    help="Environment variable name containing Semgrep app token.",
                    rich_help_panel="Semgrep Options",
                    hidden="Semgrep Options" not in visible_panels,
                ),
            ] = None,
            semgrep_dependency_ecosystems: Annotated[
                str | None,
                typer.Option(
                    "--semgrep-dependency-ecosystems",
                    help='Comma-separated list of ecosystems for Semgrep dependencies. Example: "gomod,npm".',
                    rich_help_panel="Semgrep Options",
                    hidden="Semgrep Options" not in visible_panels,
                ),
            ] = None,
            # =================================================================
            # SnipeIT Options (from cartography.intel.snipeit.cli)
            # =================================================================
            snipeit_base_uri: Annotated[
                str | None,
                typer.Option(
                    "--snipeit-base-uri",
                    help="SnipeIT base URI.",
                    rich_help_panel="SnipeIT Options",
                    hidden="SnipeIT Options" not in visible_panels,
                ),
            ] = None,
            snipeit_token_env_var: Annotated[
                str | None,
                typer.Option(
                    "--snipeit-token-env-var",
                    help="Environment variable name containing SnipeIT API token.",
                    rich_help_panel="SnipeIT Options",
                    hidden="SnipeIT Options" not in visible_panels,
                ),
            ] = None,
            snipeit_tenant_id: Annotated[
                str | None,
                typer.Option(
                    "--snipeit-tenant-id",
                    help="SnipeIT tenant ID.",
                    rich_help_panel="SnipeIT Options",
                    hidden="SnipeIT Options" not in visible_panels,
                ),
            ] = None,
            # =================================================================
            # Cloudflare Options (from cartography.intel.cloudflare.cli)
            # =================================================================
            cloudflare_token_env_var: Annotated[
                str | None,
                typer.Option(
                    "--cloudflare-token-env-var",
                    help="Environment variable name containing Cloudflare API key.",
                    rich_help_panel="Cloudflare Options",
                    hidden="Cloudflare Options" not in visible_panels,
                ),
            ] = None,
            # =================================================================
            # Tailscale Options (from cartography.intel.tailscale.cli)
            # =================================================================
            tailscale_token_env_var: Annotated[
                str | None,
                typer.Option(
                    "--tailscale-token-env-var",
                    help="Environment variable name containing Tailscale API token.",
                    rich_help_panel="Tailscale Options",
                    hidden="Tailscale Options" not in visible_panels,
                ),
            ] = None,
            tailscale_org: Annotated[
                str | None,
                typer.Option(
                    "--tailscale-org",
                    help="Tailscale organization name to sync.",
                    rich_help_panel="Tailscale Options",
                    hidden="Tailscale Options" not in visible_panels,
                ),
            ] = None,
            tailscale_base_url: Annotated[
                str,
                typer.Option(
                    "--tailscale-base-url",
                    help="Tailscale API base URL.",
                    rich_help_panel="Tailscale Options",
                    hidden="Tailscale Options" not in visible_panels,
                ),
            ] = "https://api.tailscale.com/api/v2",
            # =================================================================
            # OpenAI Options (from cartography.intel.openai.cli)
            # =================================================================
            openai_apikey_env_var: Annotated[
                str | None,
                typer.Option(
                    "--openai-apikey-env-var",
                    help="Environment variable name containing OpenAI API key.",
                    rich_help_panel="OpenAI Options",
                    hidden="OpenAI Options" not in visible_panels,
                ),
            ] = None,
            openai_org_id: Annotated[
                str | None,
                typer.Option(
                    "--openai-org-id",
                    help="OpenAI organization ID to sync.",
                    rich_help_panel="OpenAI Options",
                    hidden="OpenAI Options" not in visible_panels,
                ),
            ] = None,
            # =================================================================
            # Anthropic Options (from cartography.intel.anthropic.cli)
            # =================================================================
            anthropic_apikey_env_var: Annotated[
                str | None,
                typer.Option(
                    "--anthropic-apikey-env-var",
                    help="Environment variable name containing Anthropic API key.",
                    rich_help_panel="Anthropic Options",
                    hidden="Anthropic Options" not in visible_panels,
                ),
            ] = None,
            # =================================================================
            # Sentry Options (from cartography.intel.sentry.cli)
            # =================================================================
            sentry_token_env_var: Annotated[
                str | None,
                typer.Option(
                    "--sentry-token-env-var",
                    help="Environment variable name containing Sentry internal integration token.",
                    rich_help_panel="Sentry Options",
                    hidden="Sentry Options" not in visible_panels,
                ),
            ] = None,
            sentry_org: Annotated[
                str | None,
                typer.Option(
                    "--sentry-org",
                    help="Sentry organization slug. Required when using an internal integration token.",
                    rich_help_panel="Sentry Options",
                    hidden="Sentry Options" not in visible_panels,
                ),
            ] = None,
            sentry_host: Annotated[
                str,
                typer.Option(
                    "--sentry-host",
                    help="Sentry host URL (default: https://sentry.io). Use for self-hosted instances.",
                    rich_help_panel="Sentry Options",
                    hidden="Sentry Options" not in visible_panels,
                ),
            ] = "https://sentry.io",
            # =================================================================
            # SubImage Options (from cartography.intel.subimage.cli)
            # =================================================================
            subimage_client_id_env_var: Annotated[
                str | None,
                typer.Option(
                    "--subimage-client-id-env-var",
                    help="Environment variable name containing SubImage client ID.",
                    rich_help_panel="SubImage Options",
                    hidden="SubImage Options" not in visible_panels,
                ),
            ] = None,
            subimage_client_secret_env_var: Annotated[
                str | None,
                typer.Option(
                    "--subimage-client-secret-env-var",
                    help="Environment variable name containing SubImage client secret.",
                    rich_help_panel="SubImage Options",
                    hidden="SubImage Options" not in visible_panels,
                ),
            ] = None,
            subimage_tenant_url: Annotated[
                str | None,
                typer.Option(
                    "--subimage-tenant-url",
                    help="SubImage tenant URL, e.g. https://tenant.subimage.io.",
                    rich_help_panel="SubImage Options",
                    hidden="SubImage Options" not in visible_panels,
                ),
            ] = None,
            subimage_authkit_url: Annotated[
                str,
                typer.Option(
                    "--subimage-authkit-url",
                    help="SubImage AuthKit URL for OAuth2 token exchange.",
                    rich_help_panel="SubImage Options",
                    hidden="SubImage Options" not in visible_panels,
                ),
            ] = "https://auth.subimage.io",
            # =================================================================
            # Airbyte Options (from cartography.intel.airbyte.cli)
            # =================================================================
            airbyte_client_id: Annotated[
                str | None,
                typer.Option(
                    "--airbyte-client-id",
                    help="Airbyte client ID for authentication.",
                    rich_help_panel="Airbyte Options",
                    hidden="Airbyte Options" not in visible_panels,
                ),
            ] = None,
            airbyte_client_secret_env_var: Annotated[
                str | None,
                typer.Option(
                    "--airbyte-client-secret-env-var",
                    help="Environment variable name containing Airbyte client secret.",
                    rich_help_panel="Airbyte Options",
                    hidden="Airbyte Options" not in visible_panels,
                ),
            ] = None,
            airbyte_api_url: Annotated[
                str,
                typer.Option(
                    "--airbyte-api-url",
                    help="Airbyte API base URL.",
                    rich_help_panel="Airbyte Options",
                    hidden="Airbyte Options" not in visible_panels,
                ),
            ] = "https://api.airbyte.com/v1",
            # =================================================================
            # Docker Scout Options (from cartography.intel.docker_scout.cli)
            # =================================================================
            docker_scout_results_dir: Annotated[
                str | None,
                typer.Option(
                    "--docker-scout-results-dir",
                    help="Local directory containing Docker Scout recommendation text reports.",
                    rich_help_panel="Docker Scout Options",
                    hidden="Docker Scout Options" not in visible_panels,
                ),
            ] = None,
            docker_scout_s3_bucket: Annotated[
                str | None,
                typer.Option(
                    "--docker-scout-s3-bucket",
                    help="S3 bucket name containing Docker Scout recommendation text reports.",
                    rich_help_panel="Docker Scout Options",
                    hidden="Docker Scout Options" not in visible_panels,
                ),
            ] = None,
            docker_scout_s3_prefix: Annotated[
                str | None,
                typer.Option(
                    "--docker-scout-s3-prefix",
                    help="S3 prefix path for Docker Scout recommendation text reports.",
                    rich_help_panel="Docker Scout Options",
                    hidden="Docker Scout Options" not in visible_panels,
                ),
            ] = None,
            # =================================================================
            # Trivy Options (from cartography.intel.trivy.cli)
            # =================================================================
            trivy_s3_bucket: Annotated[
                str | None,
                typer.Option(
                    "--trivy-s3-bucket",
                    help="S3 bucket name containing Trivy scan results.",
                    rich_help_panel="Trivy Options",
                    hidden="Trivy Options" not in visible_panels,
                ),
            ] = None,
            trivy_s3_prefix: Annotated[
                str | None,
                typer.Option(
                    "--trivy-s3-prefix",
                    help="S3 prefix path for Trivy scan results.",
                    rich_help_panel="Trivy Options",
                    hidden="Trivy Options" not in visible_panels,
                ),
            ] = None,
            trivy_results_dir: Annotated[
                str | None,
                typer.Option(
                    "--trivy-results-dir",
                    help="Local directory containing Trivy JSON results.",
                    rich_help_panel="Trivy Options",
                    hidden="Trivy Options" not in visible_panels,
                ),
            ] = None,
            # =================================================================
            # Syft Options (from cartography.intel.syft.cli)
            # =================================================================
            syft_s3_bucket: Annotated[
                str | None,
                typer.Option(
                    "--syft-s3-bucket",
                    help="S3 bucket name containing Syft scan results.",
                    rich_help_panel="Syft Options",
                    hidden="Syft Options" not in visible_panels,
                ),
            ] = None,
            syft_s3_prefix: Annotated[
                str | None,
                typer.Option(
                    "--syft-s3-prefix",
                    help="S3 prefix path for Syft scan results.",
                    rich_help_panel="Syft Options",
                    hidden="Syft Options" not in visible_panels,
                ),
            ] = None,
            syft_results_dir: Annotated[
                str | None,
                typer.Option(
                    "--syft-results-dir",
                    help="Local directory containing Syft JSON results.",
                    rich_help_panel="Syft Options",
                    hidden="Syft Options" not in visible_panels,
                ),
            ] = None,
            # =================================================================
            # AIBOM Options (from cartography.intel.aibom.cli)
            # =================================================================
            aibom_s3_bucket: Annotated[
                str | None,
                typer.Option(
                    "--aibom-s3-bucket",
                    help="S3 bucket name containing AIBOM scan results.",
                    rich_help_panel="AIBOM Options",
                    hidden="AIBOM Options" not in visible_panels,
                ),
            ] = None,
            aibom_s3_prefix: Annotated[
                str | None,
                typer.Option(
                    "--aibom-s3-prefix",
                    help="S3 prefix path for AIBOM scan results.",
                    rich_help_panel="AIBOM Options",
                    hidden="AIBOM Options" not in visible_panels,
                ),
            ] = None,
            aibom_results_dir: Annotated[
                str | None,
                typer.Option(
                    "--aibom-results-dir",
                    help="Local directory containing AIBOM JSON results.",
                    rich_help_panel="AIBOM Options",
                    hidden="AIBOM Options" not in visible_panels,
                ),
            ] = None,
            # =================================================================
            # Ubuntu Security Options (from cartography.intel.ubuntu.cli)
            # =================================================================
            ubuntu_security_enabled: Annotated[
                bool,
                typer.Option(
                    "--ubuntu-security-enabled",
                    help="Enable Ubuntu Security CVE and Notice ingestion.",
                    rich_help_panel="Ubuntu Security Options",
                    hidden="Ubuntu Security Options" not in visible_panels,
                ),
            ] = False,
            ubuntu_security_api_url: Annotated[
                str | None,
                typer.Option(
                    "--ubuntu-security-api-url",
                    help="Ubuntu Security API base URL. Defaults to https://ubuntu.com.",
                    rich_help_panel="Ubuntu Security Options",
                    hidden="Ubuntu Security Options" not in visible_panels,
                ),
            ] = None,
            # =================================================================
            # Ontology Options (from cartography.intel.ontology.cli)
            # =================================================================
            ontology_users_source: Annotated[
                str | None,
                typer.Option(
                    "--ontology-users-source",
                    help="Comma-separated list of sources of truth for user data in the ontology.",
                    rich_help_panel="Ontology Options",
                    hidden="Ontology Options" not in visible_panels,
                ),
            ] = None,
            ontology_devices_source: Annotated[
                str | None,
                typer.Option(
                    "--ontology-devices-source",
                    help="Comma-separated list of sources of truth for device data in the ontology.",
                    rich_help_panel="Ontology Options",
                    hidden="Ontology Options" not in visible_panels,
                ),
            ] = None,
            # =================================================================
            # Scaleway Options (from cartography.intel.scaleway.cli)
            # =================================================================
            scaleway_org: Annotated[
                str | None,
                typer.Option(
                    "--scaleway-org",
                    help="Scaleway organization ID to sync.",
                    rich_help_panel="Scaleway Options",
                    hidden="Scaleway Options" not in visible_panels,
                ),
            ] = None,
            scaleway_access_key: Annotated[
                str | None,
                typer.Option(
                    "--scaleway-access-key",
                    help="Scaleway access key for authentication.",
                    rich_help_panel="Scaleway Options",
                    hidden="Scaleway Options" not in visible_panels,
                ),
            ] = None,
            scaleway_secret_key_env_var: Annotated[
                str | None,
                typer.Option(
                    "--scaleway-secret-key-env-var",
                    help="Environment variable name containing Scaleway secret key.",
                    rich_help_panel="Scaleway Options",
                    hidden="Scaleway Options" not in visible_panels,
                ),
            ] = None,
            # =================================================================
            # SentinelOne Options (from cartography.intel.sentinelone.cli)
            # =================================================================
            sentinelone_account_ids: Annotated[
                str | None,
                typer.Option(
                    "--sentinelone-account-ids",
                    help="Comma-separated list of SentinelOne account IDs to sync.",
                    rich_help_panel="SentinelOne Options",
                    hidden="SentinelOne Options" not in visible_panels,
                ),
            ] = None,
            sentinelone_site_ids: Annotated[
                str | None,
                typer.Option(
                    "--sentinelone-site-ids",
                    help="Comma-separated list of SentinelOne site IDs to sync.",
                    rich_help_panel="SentinelOne Options",
                    hidden="SentinelOne Options" not in visible_panels,
                ),
            ] = None,
            sentinelone_api_url: Annotated[
                str | None,
                typer.Option(
                    "--sentinelone-api-url",
                    help="SentinelOne API URL.",
                    rich_help_panel="SentinelOne Options",
                    hidden="SentinelOne Options" not in visible_panels,
                ),
            ] = None,
            sentinelone_api_token_env_var: Annotated[
                str,
                typer.Option(
                    "--sentinelone-api-token-env-var",
                    help="Environment variable name containing SentinelOne API token.",
                    rich_help_panel="SentinelOne Options",
                    hidden="SentinelOne Options" not in visible_panels,
                ),
            ] = "SENTINELONE_API_TOKEN",
            # =================================================================
            # Keycloak Options (from cartography.intel.keycloak.cli)
            # =================================================================
            keycloak_client_id: Annotated[
                str | None,
                typer.Option(
                    "--keycloak-client-id",
                    help="Keycloak client ID to sync.",
                    rich_help_panel="Keycloak Options",
                    hidden="Keycloak Options" not in visible_panels,
                ),
            ] = None,
            keycloak_client_secret_env_var: Annotated[
                str,
                typer.Option(
                    "--keycloak-client-secret-env-var",
                    help="Environment variable name containing Keycloak client secret.",
                    rich_help_panel="Keycloak Options",
                    hidden="Keycloak Options" not in visible_panels,
                ),
            ] = "KEYCLOAK_CLIENT_SECRET",
            keycloak_url: Annotated[
                str | None,
                typer.Option(
                    "--keycloak-url",
                    help="Keycloak base URL.",
                    rich_help_panel="Keycloak Options",
                    hidden="Keycloak Options" not in visible_panels,
                ),
            ] = None,
            keycloak_realm: Annotated[
                str,
                typer.Option(
                    "--keycloak-realm",
                    help="Keycloak realm for authentication (all realms will be synced).",
                    rich_help_panel="Keycloak Options",
                    hidden="Keycloak Options" not in visible_panels,
                ),
            ] = "master",
            # =================================================================
            # Slack Options (from cartography.intel.slack.cli)
            # =================================================================
            slack_token_env_var: Annotated[
                str | None,
                typer.Option(
                    "--slack-token-env-var",
                    help="Environment variable name containing Slack token.",
                    rich_help_panel="Slack Options",
                    hidden="Slack Options" not in visible_panels,
                ),
            ] = None,
            slack_teams: Annotated[
                str | None,
                typer.Option(
                    "--slack-teams",
                    help="Comma-separated list of Slack Team IDs to sync.",
                    rich_help_panel="Slack Options",
                    hidden="Slack Options" not in visible_panels,
                ),
            ] = None,
            slack_channels_memberships: Annotated[
                bool,
                typer.Option(
                    "--slack-channels-memberships",
                    help="Pull memberships for Slack channels (can be time consuming).",
                    rich_help_panel="Slack Options",
                    hidden="Slack Options" not in visible_panels,
                ),
            ] = False,
            # =================================================================
            # Spacelift Options (from cartography.intel.spacelift.cli)
            # =================================================================
            spacelift_api_endpoint: Annotated[
                str | None,
                typer.Option(
                    "--spacelift-api-endpoint",
                    help="Spacelift GraphQL API endpoint.",
                    rich_help_panel="Spacelift Options",
                    hidden="Spacelift Options" not in visible_panels,
                ),
            ] = None,
            spacelift_api_token_env_var: Annotated[
                str,
                typer.Option(
                    "--spacelift-api-token-env-var",
                    help="Environment variable name containing Spacelift API token.",
                    rich_help_panel="Spacelift Options",
                    hidden="Spacelift Options" not in visible_panels,
                ),
            ] = "SPACELIFT_API_TOKEN",
            spacelift_api_key_id_env_var: Annotated[
                str,
                typer.Option(
                    "--spacelift-api-key-id-env-var",
                    help="Environment variable name containing Spacelift API key ID.",
                    rich_help_panel="Spacelift Options",
                    hidden="Spacelift Options" not in visible_panels,
                ),
            ] = "SPACELIFT_API_KEY_ID",
            spacelift_api_key_secret_env_var: Annotated[
                str,
                typer.Option(
                    "--spacelift-api-key-secret-env-var",
                    help="Environment variable name containing Spacelift API key secret.",
                    rich_help_panel="Spacelift Options",
                    hidden="Spacelift Options" not in visible_panels,
                ),
            ] = "SPACELIFT_API_KEY_SECRET",
            spacelift_ec2_ownership_aws_profile: Annotated[
                str | None,
                typer.Option(
                    "--spacelift-ec2-ownership-aws-profile",
                    help="AWS profile for fetching EC2 ownership data from S3.",
                    rich_help_panel="Spacelift Options",
                    hidden="Spacelift Options" not in visible_panels,
                ),
            ] = None,
            spacelift_ec2_ownership_s3_bucket: Annotated[
                str | None,
                typer.Option(
                    "--spacelift-ec2-ownership-s3-bucket",
                    help="S3 bucket for EC2 ownership CloudTrail data.",
                    rich_help_panel="Spacelift Options",
                    hidden="Spacelift Options" not in visible_panels,
                ),
            ] = None,
            spacelift_ec2_ownership_s3_prefix: Annotated[
                str | None,
                typer.Option(
                    "--spacelift-ec2-ownership-s3-prefix",
                    help="S3 prefix for EC2 ownership CloudTrail data.",
                    rich_help_panel="Spacelift Options",
                    hidden="Spacelift Options" not in visible_panels,
                ),
            ] = None,
            # =================================================================
            # StatsD Metrics Options
            # =================================================================
            statsd_enabled: Annotated[
                bool,
                typer.Option(
                    "--statsd-enabled",
                    help="Enable sending metrics using statsd.",
                    rich_help_panel=PANEL_STATSD,
                ),
            ] = False,
            statsd_prefix: Annotated[
                str,
                typer.Option(
                    "--statsd-prefix",
                    help="Prefix for statsd metrics.",
                    rich_help_panel=PANEL_STATSD,
                ),
            ] = "",
            statsd_host: Annotated[
                str,
                typer.Option(
                    "--statsd-host",
                    help="StatsD server IP address.",
                    rich_help_panel=PANEL_STATSD,
                ),
            ] = "127.0.0.1",
            statsd_port: Annotated[
                int,
                typer.Option(
                    "--statsd-port",
                    help="StatsD server port.",
                    rich_help_panel=PANEL_STATSD,
                ),
            ] = 8125,
            # =================================================================
            # Analysis Options
            # =================================================================
            analysis_job_directory: Annotated[
                str | None,
                typer.Option(
                    "--analysis-job-directory",
                    help="Path to directory containing analysis jobs to run at sync conclusion.",
                    rich_help_panel=PANEL_ANALYSIS,
                ),
            ] = None,
        ) -> None:
            """
            Run cartography sync to pull infrastructure data into Neo4j.

            This command pulls configuration data from multiple sources, loads it
            into Neo4j, and runs arbitrary enrichment and analysis on that data.
            """
            # Configure logging based on verbosity
            if verbose:
                logging.getLogger("cartography").setLevel(logging.DEBUG)
            elif quiet:
                logging.getLogger("cartography").setLevel(logging.WARNING)
            else:
                logging.getLogger("cartography").setLevel(logging.INFO)

            logger.debug("Launching cartography with CLI configuration")

            # Handle Neo4j password
            neo4j_password = None
            if neo4j_user:
                if neo4j_password_prompt:
                    logger.info(
                        "Reading password for Neo4j user '%s' interactively.",
                        neo4j_user,
                    )
                    neo4j_password = getpass.getpass()
                elif neo4j_password_env_var:
                    logger.debug(
                        "Reading password for Neo4j user '%s' from environment variable '%s'.",
                        neo4j_user,
                        neo4j_password_env_var,
                    )
                    neo4j_password = os.environ.get(neo4j_password_env_var)
                if not neo4j_password:
                    logger.warning(
                        "Neo4j username was provided but a password could not be found.",
                    )

            # Load sync helpers lazily so --help/--version don't import all intel modules.
            import cartography.sync

            # Update sync if selected_modules specified
            sync = cli_instance.sync
            if selected_modules:
                sync = cartography.sync.build_sync(selected_modules)
            elif sync is None:
                sync = cartography.sync.build_default_sync()

            if statsd_enabled:
                logger.debug(
                    "statsd enabled. Sending metrics to server %s:%d. Metrics have prefix '%s'.",
                    statsd_host,
                    statsd_port,
                    statsd_prefix,
                )

            # Collect all local variables as a dict for provider processing
            all_args = locals()

            # Delegate to each provider's process_cli_args to build Config kwargs
            config_kwargs: dict[str, Any] = {}
            for provider_mod in _provider_modules:
                provider_kwargs = provider_mod.process_cli_args(all_args)
                config_kwargs.update(provider_kwargs)

            # Build the Config object with core options + provider options
            config = Config(
                neo4j_uri=neo4j_uri,
                neo4j_user=neo4j_user,
                neo4j_password=neo4j_password,
                neo4j_max_connection_lifetime=neo4j_max_connection_lifetime,
                neo4j_liveness_check_timeout=neo4j_liveness_check_timeout,
                neo4j_database=neo4j_database,
                selected_modules=selected_modules,
                update_tag=update_tag,
                analysis_job_directory=analysis_job_directory,
                statsd_enabled=statsd_enabled,
                statsd_prefix=statsd_prefix,
                statsd_host=statsd_host,
                statsd_port=statsd_port,
                async_fetch=async_fetch,
                cleanup_threshold=cleanup_threshold,
                skip_cleanup_safety=skip_cleanup_safety,
                **config_kwargs,
            )

            # Run the sync
            cartography.sync.run_with_config(sync, config)

        return app


def main(argv: list[str] | None = None) -> None:
    """
    Default entrypoint for the cartography command line interface.

    This function sets up basic logging configuration and creates a CLI instance
    with the default cartography sync configuration. It serves as the main entry
    point when cartography is executed as a command line tool.

    Args:
        argv: Optional command line arguments. If None, uses sys.argv[1:].
              Should be a list of strings representing command line parameters.

    Returns:
        Does not return - calls sys.exit() with the appropriate exit code.
        Exit code 0 indicates successful execution, non-zero indicates errors.
    """
    logging.basicConfig(level=logging.INFO)
    logging.getLogger("botocore").setLevel(logging.WARNING)
    logging.getLogger("googleapiclient").setLevel(logging.WARNING)
    logging.getLogger("neo4j").setLevel(logging.WARNING)
    logging.getLogger("azure.identity").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("slack_sdk").setLevel(logging.WARNING)
    logging.getLogger("azure.core.pipeline.policies.http_logging_policy").setLevel(
        logging.WARNING
    )

    argv = argv if argv is not None else sys.argv[1:]
    sys.exit(CLI(prog="cartography").main(argv))
