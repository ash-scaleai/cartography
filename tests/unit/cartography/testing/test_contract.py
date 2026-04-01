"""Tests for cartography.testing.contract — validation, comparison, and run_contract_tests."""
from __future__ import annotations

import json
from pathlib import Path
from typing import List
from typing import Optional

import pytest
from pydantic import BaseModel

from cartography.testing.cassette import Cassette
from cartography.testing.cassette import save_cassette
from cartography.testing.contract import ContractTest
from cartography.testing.contract import ShapeChange


# ---------------------------------------------------------------------------
# Sample Pydantic models used by tests
# ---------------------------------------------------------------------------


class EC2InstanceModel(BaseModel):
    InstanceId: str
    State: str
    InstanceType: str
    PublicIpAddress: Optional[str] = None


class IAMUserModel(BaseModel):
    arn: str
    userid: str
    name: str
    path: str


class S3BucketModel(BaseModel):
    Name: str
    Region: str
    Arn: str


class GCPInstanceModel(BaseModel):
    partial_uri: str
    name: str
    status: str
    zone_name: str
    project_id: str


class GitHubRepoModel(BaseModel):
    name: str
    url: str
    isPrivate: bool


# ---------------------------------------------------------------------------
# Test validate_cassette
# ---------------------------------------------------------------------------


class TestValidateCassette:
    def test_passes_with_matching_model(self) -> None:
        cassette = Cassette(
            module_name="aws.ec2.instances",
            api_name="describe_instances",
            response_data=[
                {"InstanceId": "i-001", "State": "running", "InstanceType": "t3.micro"},
            ],
        )
        errors = ContractTest.validate_cassette(cassette, EC2InstanceModel)
        assert errors == []

    def test_passes_with_dict_response(self) -> None:
        cassette = Cassette(
            module_name="aws.s3.buckets",
            api_name="list_buckets",
            response_data={
                "Name": "my-bucket",
                "Region": "us-east-1",
                "Arn": "arn:aws:s3:::my-bucket",
            },
        )
        errors = ContractTest.validate_cassette(cassette, S3BucketModel)
        assert errors == []

    def test_fails_with_missing_required_field(self) -> None:
        cassette = Cassette(
            module_name="aws.ec2.instances",
            api_name="describe_instances",
            response_data=[
                {"InstanceId": "i-001", "State": "running"},
                # Missing InstanceType — required by model
            ],
        )
        errors = ContractTest.validate_cassette(cassette, EC2InstanceModel)
        assert len(errors) >= 1
        assert "InstanceType" in errors[0]

    def test_fails_with_wrong_type(self) -> None:
        cassette = Cassette(
            module_name="github.repos",
            api_name="get_repos",
            response_data=[
                {"name": "repo", "url": "https://example.com", "isPrivate": [1, 2, 3]},
                # isPrivate should be bool; a list is not coercible to bool
            ],
        )
        errors = ContractTest.validate_cassette(cassette, GitHubRepoModel)
        assert len(errors) >= 1

    def test_fails_with_completely_wrong_shape(self) -> None:
        cassette = Cassette(
            module_name="aws.iam.users",
            api_name="list_users",
            response_data=[
                {"totally": "wrong", "shape": "here"},
            ],
        )
        errors = ContractTest.validate_cassette(cassette, IAMUserModel)
        assert len(errors) >= 1

    def test_optional_fields_allowed_to_be_missing(self) -> None:
        cassette = Cassette(
            module_name="aws.ec2.instances",
            api_name="describe_instances",
            response_data=[
                {
                    "InstanceId": "i-001",
                    "State": "running",
                    "InstanceType": "t3.micro",
                    # PublicIpAddress is Optional and omitted
                },
            ],
        )
        errors = ContractTest.validate_cassette(cassette, EC2InstanceModel)
        assert errors == []


# ---------------------------------------------------------------------------
# Test compare_cassettes
# ---------------------------------------------------------------------------


class TestCompareCassettes:
    def _make_cassette(self, data: dict) -> Cassette:
        return Cassette(
            module_name="test",
            api_name="test_api",
            response_data=data,
        )

    def test_detects_removed_field(self) -> None:
        old = self._make_cassette({"InstanceId": "i-1", "State": "running", "Platform": "linux"})
        new = self._make_cassette({"InstanceId": "i-1", "State": "running"})
        changes = ContractTest.compare_cassettes(old, new)

        removed = [c for c in changes if c.change_type == "removed"]
        assert len(removed) == 1
        assert removed[0].field == "Platform"
        assert removed[0].is_breaking()

    def test_detects_type_change(self) -> None:
        old = self._make_cassette({"InstanceId": "i-1", "Count": 5})
        new = self._make_cassette({"InstanceId": "i-1", "Count": "five"})
        changes = ContractTest.compare_cassettes(old, new)

        type_changed = [c for c in changes if c.change_type == "type_changed"]
        assert len(type_changed) == 1
        assert type_changed[0].field == "Count"
        assert type_changed[0].old_value == "int"
        assert type_changed[0].new_value == "str"
        assert type_changed[0].is_breaking()

    def test_detects_added_field_non_breaking(self) -> None:
        old = self._make_cassette({"InstanceId": "i-1"})
        new = self._make_cassette({"InstanceId": "i-1", "NewField": "value"})
        changes = ContractTest.compare_cassettes(old, new)

        added = [c for c in changes if c.change_type == "added"]
        assert len(added) == 1
        assert added[0].field == "NewField"
        assert not added[0].is_breaking()

    def test_no_changes_for_identical_cassettes(self) -> None:
        data = {"InstanceId": "i-1", "State": "running"}
        old = self._make_cassette(data)
        new = self._make_cassette(data)
        changes = ContractTest.compare_cassettes(old, new)
        assert changes == []

    def test_nested_field_changes(self) -> None:
        old = self._make_cassette({
            "Instance": {"Id": "i-1", "Meta": {"Version": 1}},
        })
        new = self._make_cassette({
            "Instance": {"Id": "i-1", "Meta": {"Version": "v1"}},
        })
        changes = ContractTest.compare_cassettes(old, new)
        type_changed = [c for c in changes if c.change_type == "type_changed"]
        assert any("Version" in c.field for c in type_changed)

    def test_multiple_changes_at_once(self) -> None:
        old = self._make_cassette({"a": 1, "b": "hello", "c": True})
        new = self._make_cassette({"a": 1, "b": 42, "d": "new"})
        changes = ContractTest.compare_cassettes(old, new)

        removed = {c.field for c in changes if c.change_type == "removed"}
        added = {c.field for c in changes if c.change_type == "added"}
        type_changed = {c.field for c in changes if c.change_type == "type_changed"}

        assert "c" in removed
        assert "d" in added
        assert "b" in type_changed


# ---------------------------------------------------------------------------
# Test ShapeChange
# ---------------------------------------------------------------------------


class TestShapeChange:
    def test_removed_is_breaking(self) -> None:
        change = ShapeChange(field="f", change_type="removed", old_value="str", new_value=None)
        assert change.is_breaking()

    def test_type_changed_is_breaking(self) -> None:
        change = ShapeChange(field="f", change_type="type_changed", old_value="int", new_value="str")
        assert change.is_breaking()

    def test_added_is_not_breaking(self) -> None:
        change = ShapeChange(field="f", change_type="added", old_value=None, new_value="str")
        assert not change.is_breaking()

    def test_fields_populated_correctly(self) -> None:
        change = ShapeChange(
            field="Instance.Meta.Version",
            change_type="type_changed",
            old_value="int",
            new_value="str",
        )
        assert change.field == "Instance.Meta.Version"
        assert change.old_value == "int"
        assert change.new_value == "str"


# ---------------------------------------------------------------------------
# Test run_contract_tests
# ---------------------------------------------------------------------------


class TestRunContractTests:
    def test_run_with_sample_cassettes(self, tmp_path: Path) -> None:
        """Write cassettes to a temp dir and run contract tests against them."""
        # Create two valid cassettes
        c1 = Cassette(
            module_name="aws.ec2.instances",
            api_name="describe_instances",
            response_data=[
                {"InstanceId": "i-1", "State": "running", "InstanceType": "t3.micro"},
            ],
        )
        c2 = Cassette(
            module_name="aws.s3.buckets",
            api_name="list_buckets",
            response_data=[
                {"Name": "bucket-1", "Region": "us-east-1", "Arn": "arn:aws:s3:::bucket-1"},
            ],
        )
        save_cassette(c1, tmp_path / "ec2.json")
        save_cassette(c2, tmp_path / "s3.json")

        registry = {
            "aws.ec2.instances": EC2InstanceModel,
            "aws.s3.buckets": S3BucketModel,
        }
        results = ContractTest.run_contract_tests(tmp_path, registry)

        assert "ec2.json" in results
        assert "s3.json" in results
        assert results["ec2.json"] == []
        assert results["s3.json"] == []

    def test_run_detects_failures(self, tmp_path: Path) -> None:
        bad = Cassette(
            module_name="aws.ec2.instances",
            api_name="describe_instances",
            response_data=[
                {"InstanceId": "i-1"},  # missing required State and InstanceType
            ],
        )
        save_cassette(bad, tmp_path / "bad_ec2.json")

        registry = {"aws.ec2.instances": EC2InstanceModel}
        results = ContractTest.run_contract_tests(tmp_path, registry)

        assert len(results["bad_ec2.json"]) >= 1

    def test_skips_unregistered_modules(self, tmp_path: Path) -> None:
        c = Cassette(
            module_name="unknown.module",
            api_name="some_api",
            response_data={"key": "value"},
        )
        save_cassette(c, tmp_path / "unknown.json")

        results = ContractTest.run_contract_tests(tmp_path, {})
        # unregistered modules are skipped, not present in results
        assert "unknown.json" not in results

    def test_run_empty_directory(self, tmp_path: Path) -> None:
        results = ContractTest.run_contract_tests(tmp_path, {"m": EC2InstanceModel})
        assert results == {}
