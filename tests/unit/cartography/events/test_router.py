from cartography.events.models import CloudEvent
from cartography.events.models import EventRoute
from cartography.events.router import DEFAULT_AWS_ROUTES
from cartography.events.router import EventRouter
from cartography.events.router import build_default_router


def _make_event(event_type: str, region: str = "us-east-1") -> CloudEvent:
    return CloudEvent(
        source="aws.cloudtrail",
        event_type=event_type,
        region=region,
        account_id="123456789012",
        timestamp=1700000000,
    )


class TestEventRouter:
    def test_route_run_instances(self) -> None:
        router = build_default_router()
        result = router.route(_make_event("RunInstances"))
        assert "ec2:instance" in result

    def test_route_terminate_instances(self) -> None:
        router = build_default_router()
        result = router.route(_make_event("TerminateInstances"))
        assert "ec2:instance" in result

    def test_route_create_bucket(self) -> None:
        router = build_default_router()
        result = router.route(_make_event("CreateBucket"))
        assert "s3" in result

    def test_route_delete_bucket(self) -> None:
        router = build_default_router()
        result = router.route(_make_event("DeleteBucket"))
        assert "s3" in result

    def test_route_iam_events(self) -> None:
        router = build_default_router()
        for event_type in ["CreateRole", "DeleteRole", "AttachRolePolicy",
                           "CreateUser", "DeleteUser"]:
            result = router.route(_make_event(event_type))
            assert "iam" in result, f"Expected 'iam' in routes for {event_type}"

    def test_route_security_group_events(self) -> None:
        router = build_default_router()
        for event_type in ["AuthorizeSecurityGroupIngress",
                           "RevokeSecurityGroupEgress",
                           "CreateSecurityGroup",
                           "DeleteSecurityGroup"]:
            result = router.route(_make_event(event_type))
            assert "ec2:security_group" in result, (
                f"Expected 'ec2:security_group' in routes for {event_type}"
            )

    def test_route_create_vpc_triggers_multiple_modules(self) -> None:
        """CreateVpc should trigger both ec2:vpc and ec2:subnet."""
        router = build_default_router()
        result = router.route(_make_event("CreateVpc"))
        assert "ec2:vpc" in result
        assert "ec2:subnet" in result

    def test_route_lambda_events(self) -> None:
        router = build_default_router()
        result = router.route(_make_event("CreateFunction20150331"))
        assert "lambda_function" in result

    def test_route_rds_events(self) -> None:
        router = build_default_router()
        result = router.route(_make_event("CreateDBInstance"))
        assert "rds" in result

    def test_route_eks_events(self) -> None:
        router = build_default_router()
        result = router.route(_make_event("CreateCluster"))
        assert "eks" in result

    def test_route_dynamodb_events(self) -> None:
        router = build_default_router()
        result = router.route(_make_event("CreateTable"))
        assert "dynamodb" in result

    def test_route_kms_events(self) -> None:
        router = build_default_router()
        result = router.route(_make_event("CreateKey"))
        assert "kms" in result

    def test_route_sqs_events(self) -> None:
        router = build_default_router()
        result = router.route(_make_event("CreateQueue"))
        assert "sqs" in result

    def test_route_sns_events(self) -> None:
        router = build_default_router()
        result = router.route(_make_event("CreateTopic"))
        assert "sns" in result

    def test_route_ecs_events(self) -> None:
        router = build_default_router()
        result = router.route(_make_event("RegisterTaskDefinition"))
        assert "ecs" in result

    def test_route_route53_events(self) -> None:
        router = build_default_router()
        result = router.route(_make_event("ChangeResourceRecordSets"))
        assert "route53" in result

    def test_unrecognized_event_returns_empty(self) -> None:
        router = build_default_router()
        result = router.route(_make_event("SomeUnknownAPICall"))
        assert result == []

    def test_empty_router_returns_empty(self) -> None:
        router = EventRouter()
        result = router.route(_make_event("RunInstances"))
        assert result == []

    def test_custom_route(self) -> None:
        router = EventRouter()
        router.add_route(EventRoute(r"^MyCustomEvent$", "custom:module"))
        result = router.route(_make_event("MyCustomEvent"))
        assert result == ["custom:module"]

    def test_add_routes_batch(self) -> None:
        router = EventRouter()
        router.add_routes([
            EventRoute(r"^EventA$", "module_a"),
            EventRoute(r"^EventB$", "module_b"),
        ])
        assert router.route(_make_event("EventA")) == ["module_a"]
        assert router.route(_make_event("EventB")) == ["module_b"]

    def test_deduplication(self) -> None:
        """Multiple routes to the same module should be deduplicated."""
        router = EventRouter()
        router.add_routes([
            EventRoute(r"^Run", "ec2:instance"),
            EventRoute(r"Instances$", "ec2:instance"),
        ])
        result = router.route(_make_event("RunInstances"))
        assert result == ["ec2:instance"]

    def test_region_extraction_from_event(self) -> None:
        event = _make_event("RunInstances", region="eu-west-1")
        router = build_default_router()
        result = router.route(event)
        assert "ec2:instance" in result
        # The event itself carries the region; routing does not filter by it
        assert event.region == "eu-west-1"


class TestDefaultAwsRoutes:
    def test_default_routes_not_empty(self) -> None:
        assert len(DEFAULT_AWS_ROUTES) > 0

    def test_all_default_routes_are_event_routes(self) -> None:
        for route in DEFAULT_AWS_ROUTES:
            assert isinstance(route, EventRoute)

    def test_default_router_has_routes(self) -> None:
        router = build_default_router()
        assert len(router._routes) == len(DEFAULT_AWS_ROUTES)
