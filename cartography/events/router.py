"""
Event routing for event-driven incremental sync.

The EventRouter matches incoming CloudEvents against registered EventRoutes
and returns the list of cartography module names that should be re-synced.
"""
import logging
import re

from cartography.events.models import CloudEvent
from cartography.events.models import EventRoute

logger = logging.getLogger(__name__)


# Default routes for common AWS CloudTrail events.
# Each maps a CloudTrail event name pattern to the corresponding
# cartography AWS resource function key in RESOURCE_FUNCTIONS.
DEFAULT_AWS_ROUTES: list[EventRoute] = [
    # EC2 Instances
    EventRoute(r"^RunInstances$", "ec2:instance"),
    EventRoute(r"^TerminateInstances$", "ec2:instance"),
    EventRoute(r"^StartInstances$", "ec2:instance"),
    EventRoute(r"^StopInstances$", "ec2:instance"),

    # S3
    EventRoute(r"^CreateBucket$", "s3"),
    EventRoute(r"^DeleteBucket$", "s3"),
    EventRoute(r"^PutBucketPolicy$", "s3"),
    EventRoute(r"^PutBucketAcl$", "s3"),

    # IAM
    EventRoute(r"^CreateRole$", "iam"),
    EventRoute(r"^DeleteRole$", "iam"),
    EventRoute(r"^AttachRolePolicy$", "iam"),
    EventRoute(r"^DetachRolePolicy$", "iam"),
    EventRoute(r"^CreateUser$", "iam"),
    EventRoute(r"^DeleteUser$", "iam"),
    EventRoute(r"^AttachUserPolicy$", "iam"),
    EventRoute(r"^DetachUserPolicy$", "iam"),
    EventRoute(r"^CreateGroup$", "iam"),
    EventRoute(r"^DeleteGroup$", "iam"),
    EventRoute(r"^PutGroupPolicy$", "iam"),

    # Security Groups
    EventRoute(r"^(Authorize|Revoke)SecurityGroup(Ingress|Egress)$", "ec2:security_group"),
    EventRoute(r"^(Create|Delete)SecurityGroup$", "ec2:security_group"),

    # VPC
    EventRoute(r"^CreateVpc$", "ec2:vpc"),
    EventRoute(r"^DeleteVpc$", "ec2:vpc"),
    EventRoute(r"^CreateVpc$", "ec2:subnet"),

    # Subnets
    EventRoute(r"^CreateSubnet$", "ec2:subnet"),
    EventRoute(r"^DeleteSubnet$", "ec2:subnet"),

    # Load Balancers
    EventRoute(r"^CreateLoadBalancer$", "ec2:load_balancer"),
    EventRoute(r"^DeleteLoadBalancer$", "ec2:load_balancer"),
    EventRoute(r"^CreateTargetGroup$", "ec2:load_balancer_v2"),
    EventRoute(r"^DeleteTargetGroup$", "ec2:load_balancer_v2"),

    # Lambda
    EventRoute(r"^CreateFunction", "lambda_function"),
    EventRoute(r"^DeleteFunction", "lambda_function"),
    EventRoute(r"^UpdateFunctionConfiguration", "lambda_function"),

    # RDS
    EventRoute(r"^CreateDBInstance$", "rds"),
    EventRoute(r"^DeleteDBInstance$", "rds"),
    EventRoute(r"^ModifyDBInstance$", "rds"),

    # EKS
    EventRoute(r"^CreateCluster$", "eks"),
    EventRoute(r"^DeleteCluster$", "eks"),

    # DynamoDB
    EventRoute(r"^CreateTable$", "dynamodb"),
    EventRoute(r"^DeleteTable$", "dynamodb"),

    # SQS
    EventRoute(r"^CreateQueue$", "sqs"),
    EventRoute(r"^DeleteQueue$", "sqs"),

    # SNS
    EventRoute(r"^CreateTopic$", "sns"),
    EventRoute(r"^DeleteTopic$", "sns"),

    # KMS
    EventRoute(r"^CreateKey$", "kms"),
    EventRoute(r"^DisableKey$", "kms"),
    EventRoute(r"^ScheduleKeyDeletion$", "kms"),

    # ECS
    EventRoute(r"^CreateCluster$", "ecs"),
    EventRoute(r"^(Register|Deregister)TaskDefinition$", "ecs"),
    EventRoute(r"^(Create|Delete|Update)Service$", "ecs"),

    # Route53
    EventRoute(r"^ChangeResourceRecordSets$", "route53"),
    EventRoute(r"^CreateHostedZone$", "route53"),
    EventRoute(r"^DeleteHostedZone$", "route53"),
]


class EventRouter:
    """
    Routes CloudEvents to cartography sync module names.

    The router maintains a list of EventRoute objects. When an event is
    routed, all matching routes' target_module values are returned (deduplicated).
    """

    def __init__(self) -> None:
        self._routes: list[EventRoute] = []

    def add_route(self, route: EventRoute) -> None:
        """Register a single route."""
        self._routes.append(route)

    def add_routes(self, routes: list[EventRoute]) -> None:
        """Register multiple routes at once."""
        self._routes.extend(routes)

    def route(self, event: CloudEvent) -> list[str]:
        """
        Match the event against all registered routes and return the list
        of unique module names that should be re-synced.

        Args:
            event: The CloudEvent to route.

        Returns:
            A deduplicated list of module name strings (preserving first-seen order).
        """
        matched: list[str] = []
        seen: set[str] = set()
        for r in self._routes:
            if re.search(r.event_pattern, event.event_type):
                if r.target_module not in seen:
                    matched.append(r.target_module)
                    seen.add(r.target_module)
                    logger.debug(
                        "Event '%s' matched route pattern '%s' -> module '%s'",
                        event.event_type,
                        r.event_pattern,
                        r.target_module,
                    )
        if not matched:
            logger.debug(
                "No routes matched for event type '%s' from source '%s'",
                event.event_type,
                event.source,
            )
        return matched


def build_default_router() -> EventRouter:
    """
    Create an EventRouter pre-loaded with DEFAULT_AWS_ROUTES.
    """
    router = EventRouter()
    router.add_routes(DEFAULT_AWS_ROUTES)
    return router
