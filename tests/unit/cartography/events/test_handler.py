from unittest.mock import MagicMock
from unittest.mock import patch

from cartography.events.handler import EventHandler
from cartography.events.models import CloudEvent
from cartography.events.models import EventRoute
from cartography.events.router import EventRouter


def _make_event(
    event_type: str = "RunInstances",
    region: str = "us-east-1",
    account_id: str = "123456789012",
) -> CloudEvent:
    return CloudEvent(
        source="aws.cloudtrail",
        event_type=event_type,
        region=region,
        account_id=account_id,
        timestamp=1700000000,
    )


def _make_router(*routes: tuple[str, str]) -> EventRouter:
    router = EventRouter()
    for pattern, module in routes:
        router.add_route(EventRoute(pattern, module))
    return router


class TestEventHandler:
    def test_handle_calls_correct_sync_function(self) -> None:
        mock_sync_fn = MagicMock()
        router = _make_router((r"^RunInstances$", "ec2:instance"))

        handler = EventHandler(
            router=router,
            sync_fn_provider=lambda name: mock_sync_fn if name == "ec2:instance" else None,
            neo4j_session=MagicMock(),
            common_job_parameters={"UPDATE_TAG": 0},
        )

        result = handler.handle(_make_event("RunInstances"))

        assert result == ["ec2:instance"]
        mock_sync_fn.assert_called_once()

    def test_handle_passes_scoped_params(self) -> None:
        mock_sync_fn = MagicMock()
        router = _make_router((r"^RunInstances$", "ec2:instance"))

        handler = EventHandler(
            router=router,
            sync_fn_provider=lambda name: mock_sync_fn,
            neo4j_session=MagicMock(),
            common_job_parameters={"UPDATE_TAG": 0, "existing_key": "value"},
        )

        with patch("cartography.events.handler.time") as mock_time:
            mock_time.time.return_value = 1700000099
            handler.handle(_make_event("RunInstances", region="eu-west-1"))

        call_kwargs = mock_sync_fn.call_args[1]
        assert call_kwargs["regions"] == ["eu-west-1"]
        assert call_kwargs["current_aws_account_id"] == "123456789012"
        assert call_kwargs["update_tag"] == 1700000099
        assert call_kwargs["common_job_parameters"]["UPDATE_TAG"] == 1700000099
        assert call_kwargs["common_job_parameters"]["AWS_ID"] == "123456789012"
        # Original common_job_parameters should not be modified
        assert call_kwargs["common_job_parameters"]["existing_key"] == "value"

    def test_handle_no_matching_routes(self) -> None:
        mock_sync_fn = MagicMock()
        router = _make_router((r"^RunInstances$", "ec2:instance"))

        handler = EventHandler(
            router=router,
            sync_fn_provider=lambda name: mock_sync_fn,
            neo4j_session=MagicMock(),
            common_job_parameters={},
        )

        result = handler.handle(_make_event("UnknownEvent"))
        assert result == []
        mock_sync_fn.assert_not_called()

    def test_handle_unknown_module(self) -> None:
        """If sync_fn_provider returns None, the module is skipped."""
        router = _make_router((r"^RunInstances$", "ec2:instance"))

        handler = EventHandler(
            router=router,
            sync_fn_provider=lambda name: None,
            neo4j_session=MagicMock(),
            common_job_parameters={},
        )

        result = handler.handle(_make_event("RunInstances"))
        assert result == []

    def test_handle_sync_failure_continues_other_modules(self) -> None:
        """If one module fails, others should still be synced."""
        failing_fn = MagicMock(side_effect=RuntimeError("boom"))
        success_fn = MagicMock()

        router = _make_router(
            (r"^CreateVpc$", "ec2:vpc"),
            (r"^CreateVpc$", "ec2:subnet"),
        )

        def provider(name: str):
            if name == "ec2:vpc":
                return failing_fn
            return success_fn

        handler = EventHandler(
            router=router,
            sync_fn_provider=provider,
            neo4j_session=MagicMock(),
            common_job_parameters={},
        )

        result = handler.handle(_make_event("CreateVpc"))
        assert "ec2:subnet" in result
        assert "ec2:vpc" not in result
        success_fn.assert_called_once()

    def test_handle_uses_boto3_session_factory(self) -> None:
        mock_sync_fn = MagicMock()
        mock_boto3_session = MagicMock()
        mock_factory = MagicMock(return_value=mock_boto3_session)

        router = _make_router((r"^RunInstances$", "ec2:instance"))

        handler = EventHandler(
            router=router,
            sync_fn_provider=lambda name: mock_sync_fn,
            neo4j_session=MagicMock(),
            common_job_parameters={},
            boto3_session_factory=mock_factory,
        )

        handler.handle(_make_event("RunInstances", account_id="999888777666"))

        mock_factory.assert_called_once_with("999888777666")
        call_kwargs = mock_sync_fn.call_args[1]
        assert call_kwargs["boto3_session"] is mock_boto3_session

    def test_handle_multiple_modules_for_single_event(self) -> None:
        """A single event can trigger syncs for multiple modules."""
        sync_fns: dict[str, MagicMock] = {
            "ec2:vpc": MagicMock(),
            "ec2:subnet": MagicMock(),
        }
        router = _make_router(
            (r"^CreateVpc$", "ec2:vpc"),
            (r"^CreateVpc$", "ec2:subnet"),
        )

        handler = EventHandler(
            router=router,
            sync_fn_provider=lambda name: sync_fns.get(name),
            neo4j_session=MagicMock(),
            common_job_parameters={},
        )

        result = handler.handle(_make_event("CreateVpc"))
        assert "ec2:vpc" in result
        assert "ec2:subnet" in result
        sync_fns["ec2:vpc"].assert_called_once()
        sync_fns["ec2:subnet"].assert_called_once()

    def test_each_module_gets_own_update_tag(self) -> None:
        """Each targeted sync should get its own update_tag."""
        update_tags: list[int] = []

        def capture_sync_fn(**kwargs):
            update_tags.append(kwargs["update_tag"])

        mock_fn = MagicMock(side_effect=capture_sync_fn)
        router = _make_router(
            (r"^CreateVpc$", "ec2:vpc"),
            (r"^CreateVpc$", "ec2:subnet"),
        )

        time_values = [1700000001, 1700000002]

        handler = EventHandler(
            router=router,
            sync_fn_provider=lambda name: mock_fn,
            neo4j_session=MagicMock(),
            common_job_parameters={},
        )

        with patch("cartography.events.handler.time") as mock_time:
            mock_time.time.side_effect = time_values
            handler.handle(_make_event("CreateVpc"))

        assert len(update_tags) == 2
        assert update_tags[0] == 1700000001
        assert update_tags[1] == 1700000002
