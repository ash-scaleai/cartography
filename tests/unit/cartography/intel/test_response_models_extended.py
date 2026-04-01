"""
Tests for Pydantic response models across 10 extended modules.

Each module section verifies:
  1. Valid data passes validation.
  2. Missing required fields raise ValidationError.
  3. Extra fields are allowed (ConfigDict(extra="allow")).
"""
import pytest
from pydantic import ValidationError

# ---------------------------------------------------------------------------
# DynamoDB
# ---------------------------------------------------------------------------
from cartography.intel.aws.dynamodb_response_models import (
    DynamoDBBillingResponse,
    DynamoDBGSIResponse,
    DynamoDBSSEResponse,
    DynamoDBStreamResponse,
    DynamoDBTableResponse,
)


class TestDynamoDBTableResponse:
    def test_valid(self):
        obj = DynamoDBTableResponse(
            Arn="arn:aws:dynamodb:us-east-1:123456789012:table/MyTable",
            TableName="MyTable",
            Region="us-east-1",
            ProvisionedThroughputReadCapacityUnits=5,
            ProvisionedThroughputWriteCapacityUnits=5,
        )
        assert obj.TableName == "MyTable"

    def test_missing_required(self):
        with pytest.raises(ValidationError):
            DynamoDBTableResponse(
                Arn="arn:aws:dynamodb:us-east-1:123456789012:table/MyTable",
                # TableName missing
                Region="us-east-1",
                ProvisionedThroughputReadCapacityUnits=5,
                ProvisionedThroughputWriteCapacityUnits=5,
            )

    def test_extra_fields_allowed(self):
        obj = DynamoDBTableResponse(
            Arn="arn:aws:dynamodb:us-east-1:123456789012:table/MyTable",
            TableName="MyTable",
            Region="us-east-1",
            ProvisionedThroughputReadCapacityUnits=5,
            ProvisionedThroughputWriteCapacityUnits=5,
            SomeUnknownField="hello",
        )
        assert obj.SomeUnknownField == "hello"


class TestDynamoDBGSIResponse:
    def test_valid(self):
        obj = DynamoDBGSIResponse(
            Arn="arn:aws:dynamodb:us-east-1:123456789012:table/T/index/I",
            TableArn="arn:aws:dynamodb:us-east-1:123456789012:table/T",
            Region="us-east-1",
            GSIName="my-gsi",
            ProvisionedThroughputReadCapacityUnits=10,
            ProvisionedThroughputWriteCapacityUnits=10,
        )
        assert obj.GSIName == "my-gsi"

    def test_missing_required(self):
        with pytest.raises(ValidationError):
            DynamoDBGSIResponse(
                Arn="arn:aws:dynamodb:us-east-1:123456789012:table/T/index/I",
                # TableArn missing
                Region="us-east-1",
                GSIName="my-gsi",
                ProvisionedThroughputReadCapacityUnits=10,
                ProvisionedThroughputWriteCapacityUnits=10,
            )

    def test_extra_fields_allowed(self):
        obj = DynamoDBGSIResponse(
            Arn="a",
            TableArn="b",
            Region="us-east-1",
            GSIName="g",
            ProvisionedThroughputReadCapacityUnits=1,
            ProvisionedThroughputWriteCapacityUnits=1,
            ExtraField=42,
        )
        assert obj.ExtraField == 42


class TestDynamoDBBillingResponse:
    def test_valid(self):
        obj = DynamoDBBillingResponse(
            Id="arn:table/billing",
            TableArn="arn:table",
            BillingMode="PAY_PER_REQUEST",
        )
        assert obj.BillingMode == "PAY_PER_REQUEST"

    def test_missing_required(self):
        with pytest.raises(ValidationError):
            DynamoDBBillingResponse(TableArn="arn:table")

    def test_extra_fields_allowed(self):
        obj = DynamoDBBillingResponse(Id="x", TableArn="y", foo="bar")
        assert obj.foo == "bar"


class TestDynamoDBStreamResponse:
    def test_valid(self):
        obj = DynamoDBStreamResponse(
            Arn="arn:stream",
            TableArn="arn:table",
            StreamEnabled=True,
            StreamViewType="NEW_IMAGE",
        )
        assert obj.StreamEnabled is True

    def test_missing_required(self):
        with pytest.raises(ValidationError):
            DynamoDBStreamResponse(TableArn="arn:table")

    def test_extra_fields_allowed(self):
        obj = DynamoDBStreamResponse(Arn="a", TableArn="b", custom=True)
        assert obj.custom is True


class TestDynamoDBSSEResponse:
    def test_valid(self):
        obj = DynamoDBSSEResponse(
            Id="arn:table/sse",
            TableArn="arn:table",
            SSEStatus="ENABLED",
        )
        assert obj.SSEStatus == "ENABLED"

    def test_missing_required(self):
        with pytest.raises(ValidationError):
            DynamoDBSSEResponse(TableArn="arn:table")

    def test_extra_fields_allowed(self):
        obj = DynamoDBSSEResponse(Id="x", TableArn="y", bonus="data")
        assert obj.bonus == "data"


# ---------------------------------------------------------------------------
# Lambda
# ---------------------------------------------------------------------------
from cartography.intel.aws.lambda_response_models import (
    LambdaAliasResponse,
    LambdaEventSourceMappingResponse,
    LambdaFunctionResponse,
    LambdaLayerResponse,
)


class TestLambdaFunctionResponse:
    def test_valid(self):
        obj = LambdaFunctionResponse(
            FunctionName="my-func",
            FunctionArn="arn:aws:lambda:us-east-1:123456789012:function:my-func",
            Region="us-east-1",
        )
        assert obj.FunctionName == "my-func"

    def test_missing_required(self):
        with pytest.raises(ValidationError):
            LambdaFunctionResponse(
                FunctionName="my-func",
                # FunctionArn missing
                Region="us-east-1",
            )

    def test_extra_fields_allowed(self):
        obj = LambdaFunctionResponse(
            FunctionName="f",
            FunctionArn="arn:f",
            Region="us-east-1",
            PackageType="Zip",
        )
        assert obj.PackageType == "Zip"


class TestLambdaAliasResponse:
    def test_valid(self):
        obj = LambdaAliasResponse(
            AliasArn="arn:alias",
            Name="prod",
            FunctionArn="arn:func",
        )
        assert obj.Name == "prod"

    def test_missing_required(self):
        with pytest.raises(ValidationError):
            LambdaAliasResponse(AliasArn="arn:alias", Name="prod")

    def test_extra_fields_allowed(self):
        obj = LambdaAliasResponse(
            AliasArn="a", Name="n", FunctionArn="f", RoutingConfig={}
        )
        assert obj.RoutingConfig == {}


class TestLambdaLayerResponse:
    def test_valid(self):
        obj = LambdaLayerResponse(
            Arn="arn:aws:lambda:us-east-1:123456789012:layer:my-layer:1",
            FunctionArn="arn:func",
        )
        assert obj.Arn.endswith(":1")

    def test_missing_required(self):
        with pytest.raises(ValidationError):
            LambdaLayerResponse(Arn="arn:layer")

    def test_extra_fields_allowed(self):
        obj = LambdaLayerResponse(Arn="a", FunctionArn="f", SigningJobArn="s")
        assert obj.SigningJobArn == "s"


class TestLambdaEventSourceMappingResponse:
    def test_valid(self):
        obj = LambdaEventSourceMappingResponse(
            UUID="abc-123",
            EventSourceArn="arn:sqs:queue",
            FunctionArn="arn:func",
            State="Enabled",
        )
        assert obj.UUID == "abc-123"

    def test_missing_required(self):
        with pytest.raises(ValidationError):
            LambdaEventSourceMappingResponse(
                EventSourceArn="arn:sqs:queue",
                FunctionArn="arn:func",
            )

    def test_extra_fields_allowed(self):
        obj = LambdaEventSourceMappingResponse(UUID="u", MaximumRetryAttempts=3)
        assert obj.MaximumRetryAttempts == 3


# ---------------------------------------------------------------------------
# RDS
# ---------------------------------------------------------------------------
from cartography.intel.aws.rds_response_models import (
    RDSClusterResponse,
    RDSInstanceResponse,
    RDSSnapshotResponse,
)


class TestRDSInstanceResponse:
    def test_valid(self):
        obj = RDSInstanceResponse(
            DBInstanceIdentifier="my-db",
            DBInstanceArn="arn:aws:rds:us-east-1:123456789012:db:my-db",
            DBInstanceClass="db.t3.micro",
            Engine="mysql",
        )
        assert obj.DBInstanceIdentifier == "my-db"

    def test_missing_required(self):
        with pytest.raises(ValidationError):
            RDSInstanceResponse(
                DBInstanceIdentifier="my-db",
                # DBInstanceArn missing
            )

    def test_extra_fields_allowed(self):
        obj = RDSInstanceResponse(
            DBInstanceIdentifier="db",
            DBInstanceArn="arn:db",
            DbiResourceId="dbi-abc123",
        )
        assert obj.DbiResourceId == "dbi-abc123"


class TestRDSClusterResponse:
    def test_valid(self):
        obj = RDSClusterResponse(
            DBClusterIdentifier="my-cluster",
            DBClusterArn="arn:aws:rds:us-east-1:123456789012:cluster:my-cluster",
            Engine="aurora-mysql",
        )
        assert obj.DBClusterIdentifier == "my-cluster"

    def test_missing_required(self):
        with pytest.raises(ValidationError):
            RDSClusterResponse(
                DBClusterArn="arn:cluster",
                # DBClusterIdentifier missing
            )

    def test_extra_fields_allowed(self):
        obj = RDSClusterResponse(
            DBClusterIdentifier="c",
            DBClusterArn="arn:c",
            BackupRetentionPeriod=7,
        )
        assert obj.BackupRetentionPeriod == 7


class TestRDSSnapshotResponse:
    def test_valid(self):
        obj = RDSSnapshotResponse(
            DBSnapshotIdentifier="snap-1",
            DBSnapshotArn="arn:snap-1",
            Status="available",
        )
        assert obj.Status == "available"

    def test_missing_required(self):
        with pytest.raises(ValidationError):
            RDSSnapshotResponse(DBSnapshotIdentifier="snap-1")

    def test_extra_fields_allowed(self):
        obj = RDSSnapshotResponse(
            DBSnapshotIdentifier="s",
            DBSnapshotArn="arn:s",
            VpcId="vpc-123",
        )
        assert obj.VpcId == "vpc-123"


# ---------------------------------------------------------------------------
# EKS
# ---------------------------------------------------------------------------
from cartography.intel.aws.eks_response_models import EKSClusterResponse


class TestEKSClusterResponse:
    def test_valid(self):
        obj = EKSClusterResponse(
            name="my-cluster",
            arn="arn:aws:eks:us-east-1:123456789012:cluster/my-cluster",
            version="1.28",
            status="ACTIVE",
        )
        assert obj.name == "my-cluster"

    def test_missing_required(self):
        with pytest.raises(ValidationError):
            EKSClusterResponse(
                name="my-cluster",
                # arn missing
            )

    def test_extra_fields_allowed(self):
        obj = EKSClusterResponse(
            name="c",
            arn="arn:c",
            kubernetesNetworkConfig={"serviceIpv4Cidr": "10.100.0.0/16"},
        )
        assert obj.kubernetesNetworkConfig == {"serviceIpv4Cidr": "10.100.0.0/16"}

    def test_optional_cert_fields(self):
        obj = EKSClusterResponse(
            name="c",
            arn="arn:c",
            certificate_authority_data_present=True,
            certificate_authority_parse_status="parsed",
            certificate_authority_sha256_fingerprint="abcdef",
        )
        assert obj.certificate_authority_data_present is True


# ---------------------------------------------------------------------------
# Route53
# ---------------------------------------------------------------------------
from cartography.intel.aws.route53_response_models import (
    Route53NameServerResponse,
    Route53RecordResponse,
    Route53ZoneResponse,
)


class TestRoute53ZoneResponse:
    def test_valid(self):
        obj = Route53ZoneResponse(
            zoneid="/hostedzone/Z12345",
            name="example.com",
            privatezone=False,
            count=10,
        )
        assert obj.name == "example.com"

    def test_missing_required(self):
        with pytest.raises(ValidationError):
            Route53ZoneResponse(
                zoneid="/hostedzone/Z12345",
                # name missing
                privatezone=False,
            )

    def test_extra_fields_allowed(self):
        obj = Route53ZoneResponse(
            zoneid="z",
            name="n",
            privatezone=True,
            DelegationSetId="abc",
        )
        assert obj.DelegationSetId == "abc"


class TestRoute53RecordResponse:
    def test_valid(self):
        obj = Route53RecordResponse(
            id="/hostedzone/Z12345/www.example.com/A",
            name="www.example.com",
            type="A",
            zoneid="/hostedzone/Z12345",
            value="1.2.3.4",
        )
        assert obj.type == "A"

    def test_missing_required(self):
        with pytest.raises(ValidationError):
            Route53RecordResponse(
                id="r1",
                name="www.example.com",
                # type missing
                zoneid="z",
            )

    def test_extra_fields_allowed(self):
        obj = Route53RecordResponse(
            id="r1",
            name="n",
            type="CNAME",
            zoneid="z",
            ip_addresses=["1.2.3.4"],
        )
        assert obj.ip_addresses == ["1.2.3.4"]


class TestRoute53NameServerResponse:
    def test_valid(self):
        obj = Route53NameServerResponse(
            id="ns-1234.awsdns-01.org",
            zoneid="/hostedzone/Z12345",
        )
        assert obj.id == "ns-1234.awsdns-01.org"

    def test_missing_required(self):
        with pytest.raises(ValidationError):
            Route53NameServerResponse(id="ns-1234.awsdns-01.org")

    def test_extra_fields_allowed(self):
        obj = Route53NameServerResponse(id="ns", zoneid="z", ttl=300)
        assert obj.ttl == 300


# ---------------------------------------------------------------------------
# SQS
# ---------------------------------------------------------------------------
from cartography.intel.aws.sqs_response_models import SQSQueueResponse


class TestSQSQueueResponse:
    def test_valid(self):
        obj = SQSQueueResponse(
            QueueArn="arn:aws:sqs:us-east-1:123456789012:my-queue",
            url="https://sqs.us-east-1.amazonaws.com/123456789012/my-queue",
            name="my-queue",
            CreatedTimestamp=1700000000,
        )
        assert obj.name == "my-queue"

    def test_missing_required(self):
        with pytest.raises(ValidationError):
            SQSQueueResponse(
                QueueArn="arn:sqs",
                # url missing
                name="q",
            )

    def test_extra_fields_allowed(self):
        obj = SQSQueueResponse(
            QueueArn="arn:sqs",
            url="https://sqs",
            name="q",
            ApproximateNumberOfMessages="42",
        )
        assert obj.ApproximateNumberOfMessages == "42"


# ---------------------------------------------------------------------------
# SNS
# ---------------------------------------------------------------------------
from cartography.intel.aws.sns_response_models import (
    SNSSubscriptionResponse,
    SNSTopicResponse,
)


class TestSNSTopicResponse:
    def test_valid(self):
        obj = SNSTopicResponse(
            TopicArn="arn:aws:sns:us-east-1:123456789012:my-topic",
            TopicName="my-topic",
            Owner="123456789012",
        )
        assert obj.TopicName == "my-topic"

    def test_missing_required(self):
        with pytest.raises(ValidationError):
            SNSTopicResponse(
                TopicArn="arn:sns",
                # TopicName missing
            )

    def test_extra_fields_allowed(self):
        obj = SNSTopicResponse(
            TopicArn="arn:sns",
            TopicName="t",
            FifoTopic="true",
        )
        assert obj.FifoTopic == "true"


class TestSNSSubscriptionResponse:
    def test_valid(self):
        obj = SNSSubscriptionResponse(
            SubscriptionArn="arn:aws:sns:us-east-1:123456789012:my-topic:sub-1",
            TopicArn="arn:aws:sns:us-east-1:123456789012:my-topic",
            Protocol="email",
            Endpoint="user@example.com",
        )
        assert obj.Protocol == "email"

    def test_missing_required(self):
        with pytest.raises(ValidationError):
            SNSSubscriptionResponse(
                SubscriptionArn="arn:sub",
                # TopicArn missing
            )

    def test_extra_fields_allowed(self):
        obj = SNSSubscriptionResponse(
            SubscriptionArn="a",
            TopicArn="t",
            FilterPolicy="{}",
        )
        assert obj.FilterPolicy == "{}"


# ---------------------------------------------------------------------------
# Okta
# ---------------------------------------------------------------------------
from cartography.intel.okta.response_models import (
    OktaGroupResponse,
    OktaUserResponse,
)


class TestOktaUserResponse:
    def test_valid(self):
        obj = OktaUserResponse(
            id="00u1234",
            first_name="Jane",
            last_name="Doe",
            login="jane.doe@example.com",
            email="jane.doe@example.com",
            created="01/15/2024, 10:30:00",
        )
        assert obj.email == "jane.doe@example.com"

    def test_missing_required(self):
        with pytest.raises(ValidationError):
            OktaUserResponse(
                id="00u1234",
                first_name="Jane",
                # last_name missing
                login="jane.doe@example.com",
                email="jane.doe@example.com",
                created="01/15/2024, 10:30:00",
            )

    def test_extra_fields_allowed(self):
        obj = OktaUserResponse(
            id="u1",
            first_name="A",
            last_name="B",
            login="a@b",
            email="a@b",
            created="01/01/2024, 00:00:00",
            second_email="a2@b",
        )
        assert obj.second_email == "a2@b"


class TestOktaGroupResponse:
    def test_valid(self):
        obj = OktaGroupResponse(
            id="00g1234",
            name="Engineering",
            description="Engineering team",
        )
        assert obj.name == "Engineering"

    def test_missing_required(self):
        with pytest.raises(ValidationError):
            OktaGroupResponse(
                id="00g1234",
                # name missing
            )

    def test_extra_fields_allowed(self):
        obj = OktaGroupResponse(
            id="g1",
            name="Eng",
            group_type="OKTA_GROUP",
        )
        assert obj.group_type == "OKTA_GROUP"


# ---------------------------------------------------------------------------
# Azure
# ---------------------------------------------------------------------------
from cartography.intel.azure.response_models import (
    AzureSubscriptionResponse,
    AzureVirtualMachineResponse,
)


class TestAzureVirtualMachineResponse:
    def test_valid(self):
        obj = AzureVirtualMachineResponse(
            id="/subscriptions/sub1/resourcegroups/rg1/providers/microsoft.compute/virtualmachines/vm1",
            name="vm1",
            location="eastus",
            resource_group="rg1",
        )
        assert obj.name == "vm1"

    def test_missing_required(self):
        with pytest.raises(ValidationError):
            AzureVirtualMachineResponse(
                # id missing
                name="vm1",
            )

    def test_extra_fields_allowed(self):
        obj = AzureVirtualMachineResponse(
            id="/sub/vm",
            hardware_profile={"vm_size": "Standard_D2s_v3"},
        )
        assert obj.hardware_profile == {"vm_size": "Standard_D2s_v3"}


class TestAzureSubscriptionResponse:
    def test_valid(self):
        obj = AzureSubscriptionResponse(
            id="/subscriptions/sub-id-123",
            subscriptionId="sub-id-123",
            displayName="My Subscription",
            state="Enabled",
        )
        assert obj.subscriptionId == "sub-id-123"

    def test_missing_required(self):
        with pytest.raises(ValidationError):
            AzureSubscriptionResponse(
                id="/subscriptions/sub-id-123",
                # subscriptionId missing
            )

    def test_extra_fields_allowed(self):
        obj = AzureSubscriptionResponse(
            id="/sub",
            subscriptionId="s1",
            tenantId="tenant-123",
        )
        assert obj.tenantId == "tenant-123"


# ---------------------------------------------------------------------------
# GitLab
# ---------------------------------------------------------------------------
from cartography.intel.gitlab.response_models import (
    GitLabGroupResponse,
    GitLabProjectResponse,
)


class TestGitLabProjectResponse:
    def test_valid(self):
        obj = GitLabProjectResponse(
            web_url="https://gitlab.com/group/project",
            name="my-project",
            org_url="https://gitlab.com/group",
            visibility="private",
            archived=False,
        )
        assert obj.name == "my-project"

    def test_missing_required(self):
        with pytest.raises(ValidationError):
            GitLabProjectResponse(
                web_url="https://gitlab.com/group/project",
                # name missing
                org_url="https://gitlab.com/group",
            )

    def test_extra_fields_allowed(self):
        obj = GitLabProjectResponse(
            web_url="https://gitlab.com/g/p",
            name="p",
            org_url="https://gitlab.com/g",
            star_count=42,
        )
        assert obj.star_count == 42


class TestGitLabGroupResponse:
    def test_valid(self):
        obj = GitLabGroupResponse(
            web_url="https://gitlab.com/my-group",
            name="my-group",
            org_url="https://gitlab.com/my-org",
            full_path="my-org/my-group",
            visibility="internal",
        )
        assert obj.full_path == "my-org/my-group"

    def test_missing_required(self):
        with pytest.raises(ValidationError):
            GitLabGroupResponse(
                web_url="https://gitlab.com/my-group",
                name="my-group",
                # org_url missing
            )

    def test_extra_fields_allowed(self):
        obj = GitLabGroupResponse(
            web_url="https://gitlab.com/g",
            name="g",
            org_url="https://gitlab.com/o",
            avatar_url="https://gitlab.com/avatar.png",
        )
        assert obj.avatar_url == "https://gitlab.com/avatar.png"
