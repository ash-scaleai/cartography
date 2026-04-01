import asyncio
import time
from unittest.mock import MagicMock

import pytest

from cartography.config import Config
from cartography.sync import build_default_sync
from cartography.sync import build_sync
from cartography.sync import parse_and_validate_selected_modules
from cartography.sync import run_with_config
from cartography.sync import Sync
from cartography.sync import TOP_LEVEL_MODULES


def test_available_modules_import():
    # Check if all available modules are defined in the TOP_LEVEL_MODULES list
    assert sorted(TOP_LEVEL_MODULES.keys()) == sorted(Sync.list_intel_modules().keys())


def test_build_default_sync():
    sync = build_default_sync()
    # Use list because order matters
    assert [name for name in sync._stages.keys()] == list(TOP_LEVEL_MODULES.keys())


def test_build_sync():
    # Arrange
    selected_modules = "aws, gcp, analysis"

    # Act
    sync = build_sync(selected_modules)

    # Assert
    assert [name for name in sync._stages.keys()] == selected_modules.split(", ")


def test_parse_and_validate_selected_modules():
    no_spaces = "aws,gcp,oci,analysis"
    assert parse_and_validate_selected_modules(no_spaces) == [
        "aws",
        "gcp",
        "oci",
        "analysis",
    ]

    mismatch_spaces = "gcp, oci,analysis"
    assert parse_and_validate_selected_modules(mismatch_spaces) == [
        "gcp",
        "oci",
        "analysis",
    ]

    sync_that_does_not_exist = "gcp, thisdoesnotexist, aws"
    with pytest.raises(ValueError):
        parse_and_validate_selected_modules(sync_that_does_not_exist)

    absolute_garbage = "#@$@#RDFFHKjsdfkjsd,KDFJHW#@,"
    with pytest.raises(ValueError):
        parse_and_validate_selected_modules(absolute_garbage)


def test_run_with_config_forwards_optional_driver_kwargs(mocker):
    sync = mocker.Mock()
    driver = object()
    driver_mock = mocker.patch(
        "cartography.sync.GraphDatabase.driver", return_value=driver
    )
    mocker.patch("cartography.sync.time.time", return_value=123)

    config = Config(
        neo4j_uri="bolt://localhost:7687",
        neo4j_user="neo4j",
        neo4j_password="password",
        neo4j_max_connection_lifetime=300,
        neo4j_liveness_check_timeout=30,
        neo4j_connection_timeout=15.0,
        neo4j_keep_alive=True,
        neo4j_max_transaction_retry_time=30.0,
        neo4j_max_connection_pool_size=64,
        neo4j_connection_acquisition_timeout=60.0,
    )

    run_with_config(sync, config)

    driver_mock.assert_called_once_with(
        "bolt://localhost:7687",
        auth=("neo4j", "password"),
        max_connection_lifetime=300,
        liveness_check_timeout=30,
        connection_timeout=15.0,
        keep_alive=True,
        max_transaction_retry_time=30.0,
        max_connection_pool_size=64,
        connection_acquisition_timeout=60.0,
    )
    sync.run.assert_called_once_with(driver, config)
    assert config.update_tag == 123


def test_run_with_config_omits_unset_optional_driver_kwargs(mocker):
    sync = mocker.Mock()
    driver_mock = mocker.patch(
        "cartography.sync.GraphDatabase.driver", return_value=object()
    )
    mocker.patch("cartography.sync.time.time", return_value=123)

    config = Config(
        neo4j_uri="bolt://localhost:7687",
        neo4j_user="neo4j",
        neo4j_password="password",
    )

    run_with_config(sync, config)

    driver_mock.assert_called_once_with(
        "bolt://localhost:7687",
        auth=("neo4j", "password"),
    )


def test_config_preserves_existing_positional_arguments():
    config = Config(
        "bolt://localhost:7687",
        "neo4j",
        "password",
        300,
        30,
        "neo4j-db",
        "aws,analysis",
        456,
    )

    assert config.neo4j_database == "neo4j-db"
    assert config.selected_modules == "aws,analysis"
    assert config.update_tag == 456


def test_run_async_concurrent_execution():
    """Verify that async mode runs independent stages concurrently."""
    call_log = []

    def _make_stage(name, delay=0.1):
        def stage_func(neo4j_session, config):
            call_log.append(("start", name, time.monotonic()))
            time.sleep(delay)
            call_log.append(("end", name, time.monotonic()))
        return stage_func

    sync = Sync()
    sync.add_stage("create-indexes", _make_stage("create-indexes", delay=0.0))
    sync.add_stage("provider_a", _make_stage("provider_a", delay=0.2))
    sync.add_stage("provider_b", _make_stage("provider_b", delay=0.2))
    sync.add_stage("provider_c", _make_stage("provider_c", delay=0.2))
    sync.add_stage("analysis", _make_stage("analysis", delay=0.0))

    mock_driver = MagicMock()
    mock_session = MagicMock()
    mock_driver.session.return_value.__enter__ = MagicMock(return_value=mock_session)
    mock_driver.session.return_value.__exit__ = MagicMock(return_value=False)

    config = Config(neo4j_uri="bolt://localhost:7687")
    config.update_tag = 1
    config.neo4j_database = None

    result = asyncio.run(sync.run_async(mock_driver, config))
    assert result == 0

    # All 5 stages should have run
    started = [name for action, name, _ in call_log if action == "start"]
    ended = [name for action, name, _ in call_log if action == "end"]
    assert set(started) == {"create-indexes", "provider_a", "provider_b", "provider_c", "analysis"}
    assert set(ended) == {"create-indexes", "provider_a", "provider_b", "provider_c", "analysis"}

    # create-indexes must finish before any provider starts
    create_indexes_end = next(t for a, n, t in call_log if a == "end" and n == "create-indexes")
    provider_starts = [t for a, n, t in call_log if a == "start" and n.startswith("provider")]
    for t in provider_starts:
        assert t >= create_indexes_end, "create-indexes must complete before providers start"

    # analysis must start after all providers finish
    provider_ends = [t for a, n, t in call_log if a == "end" and n.startswith("provider")]
    analysis_start = next(t for a, n, t in call_log if a == "start" and n == "analysis")
    for t in provider_ends:
        assert analysis_start >= t, "analysis must start after all providers finish"

    # Concurrent providers should overlap -- total time should be much less than 0.6s
    first_provider_start = min(provider_starts)
    last_provider_end = max(provider_ends)
    concurrent_duration = last_provider_end - first_provider_start
    assert concurrent_duration < 0.5, (
        f"Providers took {concurrent_duration:.2f}s; expected < 0.5s if concurrent"
    )


def test_sequential_mode_unchanged():
    """Verify that the default sequential run method still executes stages in order."""
    call_order = []

    def _make_stage(name):
        def stage_func(neo4j_session, config):
            call_order.append(name)
        return stage_func

    sync = Sync()
    sync.add_stage("create-indexes", _make_stage("create-indexes"))
    sync.add_stage("aws", _make_stage("aws"))
    sync.add_stage("gcp", _make_stage("gcp"))
    sync.add_stage("analysis", _make_stage("analysis"))

    mock_driver = MagicMock()
    mock_session = MagicMock()
    mock_driver.session.return_value.__enter__ = MagicMock(return_value=mock_session)
    mock_driver.session.return_value.__exit__ = MagicMock(return_value=False)

    config = Config(neo4j_uri="bolt://localhost:7687")
    config.update_tag = 1
    config.neo4j_database = None

    result = sync.run(mock_driver, config)
    assert result == 0
    assert call_order == ["create-indexes", "aws", "gcp", "analysis"]


def test_run_with_config_uses_async_when_flag_set(mocker):
    """Verify that run_with_config dispatches to run_async when async_fetch is True."""
    sync = mocker.Mock()

    # Make run_async return a proper coroutine
    async def _fake_run_async(*a, **kw):
        return 0

    sync.run_async = mocker.Mock(side_effect=_fake_run_async)
    driver = object()
    mocker.patch("cartography.sync.GraphDatabase.driver", return_value=driver)
    mocker.patch("cartography.sync.time.time", return_value=123)

    config = Config(
        neo4j_uri="bolt://localhost:7687",
        async_fetch=True,
    )

    run_with_config(sync, config)

    sync.run_async.assert_called_once_with(driver, config)
    sync.run.assert_not_called()
