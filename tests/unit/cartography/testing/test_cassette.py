"""Tests for cartography.testing.cassette — save/load roundtrip and CassetteRecorder."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from cartography.testing.cassette import Cassette
from cartography.testing.cassette import CassetteRecorder
from cartography.testing.cassette import load_cassette
from cartography.testing.cassette import save_cassette


@pytest.fixture
def sample_cassette() -> Cassette:
    return Cassette(
        module_name="aws.ec2.instances",
        api_name="describe_instances",
        response_data=[
            {"InstanceId": "i-001", "State": "running"},
            {"InstanceId": "i-002", "State": "stopped"},
        ],
        recorded_at="2026-03-15T12:00:00+00:00",
        schema_version="1.0",
    )


class TestCassetteSaveLoadRoundtrip:
    """Verify that saving then loading a cassette preserves all fields."""

    def test_roundtrip(self, sample_cassette: Cassette, tmp_path: Path) -> None:
        path = tmp_path / "test_cassette.json"
        save_cassette(sample_cassette, path)
        loaded = load_cassette(path)

        assert loaded.module_name == sample_cassette.module_name
        assert loaded.api_name == sample_cassette.api_name
        assert loaded.response_data == sample_cassette.response_data
        assert loaded.recorded_at == sample_cassette.recorded_at
        assert loaded.schema_version == sample_cassette.schema_version

    def test_saved_file_is_valid_json(self, sample_cassette: Cassette, tmp_path: Path) -> None:
        path = tmp_path / "test_cassette.json"
        save_cassette(sample_cassette, path)
        with open(path) as fh:
            data = json.load(fh)
        assert "module_name" in data
        assert "response_data" in data

    def test_roundtrip_with_dict_response(self, tmp_path: Path) -> None:
        cassette = Cassette(
            module_name="aws.s3.buckets",
            api_name="list_buckets",
            response_data={"Buckets": [{"Name": "my-bucket"}]},
        )
        path = tmp_path / "dict_cassette.json"
        save_cassette(cassette, path)
        loaded = load_cassette(path)
        assert loaded.response_data == cassette.response_data

    def test_load_missing_file_raises(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            load_cassette(tmp_path / "nonexistent.json")

    def test_creates_parent_directories(self, tmp_path: Path) -> None:
        path = tmp_path / "a" / "b" / "c" / "cassette.json"
        cassette = Cassette(
            module_name="test",
            api_name="test_api",
            response_data={"key": "value"},
        )
        save_cassette(cassette, path)
        assert path.exists()


class TestCassetteRecorder:
    """Verify CassetteRecorder recording and wrapping behaviour."""

    def test_record_creates_cassette(self) -> None:
        recorder = CassetteRecorder(module_name="aws.ec2.instances")
        cassette = recorder.record("describe_instances", [{"id": "i-1"}])
        assert cassette.module_name == "aws.ec2.instances"
        assert cassette.api_name == "describe_instances"
        assert len(recorder.cassettes) == 1

    def test_record_multiple(self) -> None:
        recorder = CassetteRecorder(module_name="aws.iam.users")
        recorder.record("list_users", [{"name": "alice"}])
        recorder.record("get_user", {"name": "alice", "arn": "arn:..."})
        assert len(recorder.cassettes) == 2

    def test_wrap_records_return_value(self) -> None:
        recorder = CassetteRecorder(module_name="test.module")

        def my_api(x: int) -> dict:
            return {"result": x * 2}

        wrapped = recorder.wrap("my_api", my_api)
        result = wrapped(5)
        assert result == {"result": 10}
        assert len(recorder.cassettes) == 1
        assert recorder.cassettes[0].response_data == {"result": 10}

    def test_save_all(self, tmp_path: Path) -> None:
        recorder = CassetteRecorder(module_name="aws.s3")
        recorder.record("list_buckets", [{"Name": "b1"}])
        recorder.record("get_bucket_acl", {"Grants": []})
        paths = recorder.save_all(tmp_path)
        assert len(paths) == 2
        for p in paths:
            assert p.exists()
            assert p.suffix == ".json"
