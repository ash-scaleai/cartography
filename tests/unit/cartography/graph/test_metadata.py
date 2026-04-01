"""Tests for cartography.graph.metadata — dependency graph validation and discovery."""
from __future__ import annotations

from unittest.mock import MagicMock
from unittest.mock import patch

import pytest

from cartography.graph.metadata import (
    ModuleMetadata,
    _collect_from_module,
    discover_module_metadata,
    validate_dependency_graph,
)


# ---------------------------------------------------------------------------
# ModuleMetadata construction
# ---------------------------------------------------------------------------

class TestModuleMetadata:
    def test_basic_creation(self):
        m = ModuleMetadata(name="aws.ec2.instances", depends_on=["aws"], provides=["EC2Instance"])
        assert m.name == "aws.ec2.instances"
        assert m.depends_on == ["aws"]
        assert m.provides == ["EC2Instance"]

    def test_defaults(self):
        m = ModuleMetadata(name="aws")
        assert m.depends_on == []
        assert m.provides == []

    def test_empty_name_raises(self):
        with pytest.raises(ValueError, match="must not be empty"):
            ModuleMetadata(name="")


# ---------------------------------------------------------------------------
# validate_dependency_graph — happy path
# ---------------------------------------------------------------------------

class TestValidateDependencyGraphValid:
    def test_single_module(self):
        modules = [ModuleMetadata(name="aws")]
        validate_dependency_graph(modules)  # should not raise

    def test_linear_chain(self):
        modules = [
            ModuleMetadata(name="aws"),
            ModuleMetadata(name="aws.ec2.instances", depends_on=["aws"]),
            ModuleMetadata(name="aws.ssm", depends_on=["aws.ec2.instances"]),
        ]
        validate_dependency_graph(modules)

    def test_diamond_dependency(self):
        modules = [
            ModuleMetadata(name="aws"),
            ModuleMetadata(name="aws.ec2.subnets", depends_on=["aws"]),
            ModuleMetadata(name="aws.ec2.instances", depends_on=["aws"]),
            ModuleMetadata(name="aws.ec2.load_balancers", depends_on=["aws.ec2.subnets", "aws.ec2.instances"]),
        ]
        validate_dependency_graph(modules)

    def test_empty_list(self):
        validate_dependency_graph([])


# ---------------------------------------------------------------------------
# validate_dependency_graph — missing dependency
# ---------------------------------------------------------------------------

class TestValidateDependencyGraphMissing:
    def test_missing_dependency_raises_valueerror(self):
        modules = [
            ModuleMetadata(name="aws"),
            ModuleMetadata(name="aws.ssm", depends_on=["aws.ec2.instances"]),
        ]
        with pytest.raises(ValueError, match="Module 'aws.ssm' depends on 'aws.ec2.instances' which is not registered"):
            validate_dependency_graph(modules)

    def test_missing_dependency_message_format(self):
        """Verify the exact error message format required by the spec."""
        modules = [
            ModuleMetadata(name="aws.ssm", depends_on=["aws.ec2.instances"]),
        ]
        with pytest.raises(ValueError) as exc_info:
            validate_dependency_graph(modules)
        assert "Module 'aws.ssm' depends on 'aws.ec2.instances' which is not registered" in str(exc_info.value)


# ---------------------------------------------------------------------------
# validate_dependency_graph — cycle detection
# ---------------------------------------------------------------------------

class TestValidateDependencyGraphCycles:
    def test_self_cycle(self):
        modules = [
            ModuleMetadata(name="a", depends_on=["a"]),
        ]
        with pytest.raises(ValueError, match="Dependency cycle detected"):
            validate_dependency_graph(modules)

    def test_two_node_cycle(self):
        modules = [
            ModuleMetadata(name="a", depends_on=["b"]),
            ModuleMetadata(name="b", depends_on=["a"]),
        ]
        with pytest.raises(ValueError, match="Dependency cycle detected"):
            validate_dependency_graph(modules)

    def test_three_node_cycle(self):
        modules = [
            ModuleMetadata(name="a", depends_on=["c"]),
            ModuleMetadata(name="b", depends_on=["a"]),
            ModuleMetadata(name="c", depends_on=["b"]),
        ]
        with pytest.raises(ValueError, match="Dependency cycle detected"):
            validate_dependency_graph(modules)

    def test_cycle_reports_members(self):
        modules = [
            ModuleMetadata(name="x"),
            ModuleMetadata(name="a", depends_on=["b"]),
            ModuleMetadata(name="b", depends_on=["a"]),
        ]
        with pytest.raises(ValueError, match="'a'"):
            validate_dependency_graph(modules)


# ---------------------------------------------------------------------------
# validate_dependency_graph — duplicate names
# ---------------------------------------------------------------------------

class TestValidateDependencyGraphDuplicates:
    def test_duplicate_name_raises(self):
        modules = [
            ModuleMetadata(name="aws"),
            ModuleMetadata(name="aws"),
        ]
        with pytest.raises(ValueError, match="Duplicate module name 'aws'"):
            validate_dependency_graph(modules)


# ---------------------------------------------------------------------------
# _collect_from_module helper
# ---------------------------------------------------------------------------

class TestCollectFromModule:
    def test_single_metadata(self):
        mod = MagicMock()
        mod.MODULE_METADATA = ModuleMetadata(name="test")
        dest: list[ModuleMetadata] = []
        _collect_from_module(mod, dest)
        assert len(dest) == 1
        assert dest[0].name == "test"

    def test_list_of_metadata(self):
        mod = MagicMock()
        mod.MODULE_METADATA = [
            ModuleMetadata(name="a"),
            ModuleMetadata(name="b"),
        ]
        dest: list[ModuleMetadata] = []
        _collect_from_module(mod, dest)
        assert len(dest) == 2

    def test_no_metadata(self):
        mod = MagicMock(spec=[])  # no MODULE_METADATA attribute
        dest: list[ModuleMetadata] = []
        _collect_from_module(mod, dest)
        assert dest == []


# ---------------------------------------------------------------------------
# discover_module_metadata
# ---------------------------------------------------------------------------

class TestDiscoverModuleMetadata:
    def test_discovers_metadata_from_intel_modules(self):
        """Verify that discover_module_metadata finds MODULE_METADATA from real modules."""
        all_meta = discover_module_metadata()
        # We added MODULE_METADATA to at least aws, github, gcp, okta, azure
        names = {m.name for m in all_meta}
        # AWS declares a list with many sub-modules; check for the top-level one
        assert "aws" in names, f"Expected 'aws' in discovered names, got {names}"
        assert "github" in names, f"Expected 'github' in discovered names, got {names}"
        assert "gcp" in names, f"Expected 'gcp' in discovered names, got {names}"
        assert "okta" in names, f"Expected 'okta' in discovered names, got {names}"
        assert "azure" in names, f"Expected 'azure' in discovered names, got {names}"


# ---------------------------------------------------------------------------
# All declared dependencies resolve (integration-level check)
# ---------------------------------------------------------------------------

class TestAllDeclaredDependenciesResolve:
    def test_all_declared_deps_are_valid(self):
        """Every depends_on reference in the codebase should point to a registered module."""
        all_meta = discover_module_metadata()
        # This will raise ValueError if any dependency is missing or cycles exist
        validate_dependency_graph(all_meta)
