"""
Unit tests for Pydantic response models and the validate_response utility.

Tests cover all five modules: EC2, IAM, S3, GitHub, and GCP Compute.
Each section verifies that:
  - Valid sample data passes validation
  - Malformed data raises ValidationError with clear field-level messages
  - Extra unknown fields do not cause failures (extra='allow')
"""
import datetime

import pytest
from pydantic import ValidationError

from cartography.intel.aws.ec2.response_models import EC2Instance
from cartography.intel.aws.ec2.response_models import EC2Reservation
from cartography.intel.aws.iam_response_models import IAMGroup
from cartography.intel.aws.iam_response_models import IAMGroupListResponse
from cartography.intel.aws.iam_response_models import IAMRole
from cartography.intel.aws.iam_response_models import IAMRoleListResponse
from cartography.intel.aws.iam_response_models import IAMUser
from cartography.intel.aws.iam_response_models import IAMUserListResponse
from cartography.intel.aws.s3_response_models import S3Bucket
from cartography.intel.aws.s3_response_models import S3ListBucketsResponse
from cartography.intel.gcp.response_models import GCPInstance
from cartography.intel.gcp.response_models import GCPInstanceListResponse
from cartography.intel.github.response_models import GitHubRepo
from cartography.intel.validation import validate_response


# ============================================================================
# EC2 Instances
# ============================================================================

class TestEC2ResponseModels:
    """Tests for EC2 DescribeInstances response models."""

    VALID_INSTANCE = {
        "InstanceId": "i-01",
        "ImageId": "ami-abc123",
        "InstanceType": "t2.micro",
        "LaunchTime": datetime.datetime(2024, 1, 1, 0, 0, 0),
        "Monitoring": {"State": "enabled"},
        "Placement": {"AvailabilityZone": "us-east-1a", "Tenancy": "default"},
        "State": {"Code": 16, "Name": "running"},
        "PrivateIpAddress": "10.0.0.1",
        "PublicIpAddress": "1.2.3.4",
        "PublicDnsName": "ec2-1-2-3-4.compute-1.amazonaws.com",
        "SubnetId": "subnet-abc",
        "SecurityGroups": [{"GroupId": "sg-123", "GroupName": "my-sg"}],
        "NetworkInterfaces": [
            {
                "NetworkInterfaceId": "eni-01",
                "Status": "in-use",
                "MacAddress": "00:00:00:00:00:01",
                "Description": "",
                "Groups": [{"GroupId": "sg-123"}],
                "SubnetId": "subnet-abc",
            },
        ],
        "BlockDeviceMappings": [
            {
                "DeviceName": "/dev/sda1",
                "Ebs": {"VolumeId": "vol-01", "DeleteOnTermination": True},
            },
        ],
        "Tags": [{"Key": "Name", "Value": "test-instance"}],
    }

    VALID_RESERVATION = {
        "ReservationId": "r-01",
        "OwnerId": "123456789012",
        "RequesterId": "requester",
        "Instances": [VALID_INSTANCE],
        "Groups": [],
    }

    def test_valid_instance(self):
        instance = EC2Instance.model_validate(self.VALID_INSTANCE)
        assert instance.InstanceId == "i-01"
        assert instance.InstanceType == "t2.micro"
        assert instance.Placement.AvailabilityZone == "us-east-1a"
        assert instance.SecurityGroups[0].GroupId == "sg-123"

    def test_valid_reservation(self):
        reservation = EC2Reservation.model_validate(self.VALID_RESERVATION)
        assert reservation.ReservationId == "r-01"
        assert len(reservation.Instances) == 1
        assert reservation.Instances[0].InstanceId == "i-01"

    def test_missing_instance_id_raises(self):
        bad = {**self.VALID_INSTANCE}
        del bad["InstanceId"]
        with pytest.raises(ValidationError) as exc_info:
            EC2Instance.model_validate(bad)
        errors = exc_info.value.errors()
        assert any(e["loc"] == ("InstanceId",) for e in errors)

    def test_missing_reservation_id_raises(self):
        bad = {**self.VALID_RESERVATION, "ReservationId": None}
        # ReservationId is str, not Optional[str], so None should fail
        with pytest.raises(ValidationError):
            EC2Reservation.model_validate(bad)

    def test_extra_fields_allowed(self):
        data = {**self.VALID_INSTANCE, "BrandNewField": "surprise"}
        instance = EC2Instance.model_validate(data)
        assert instance.InstanceId == "i-01"

    def test_minimal_instance(self):
        """Only the required field InstanceId should be enough."""
        instance = EC2Instance.model_validate({"InstanceId": "i-minimal"})
        assert instance.InstanceId == "i-minimal"
        assert instance.SecurityGroups == []

    def test_validate_response_utility_with_ec2(self):
        items = [self.VALID_INSTANCE, {"InstanceId": "i-02"}]
        results = validate_response(items, EC2Instance, raise_on_error=True)
        assert len(results) == 2
        assert results[0].InstanceId == "i-01"

    def test_validate_response_drops_invalid_by_default(self):
        items = [self.VALID_INSTANCE, {"no_id_here": True}]
        results = validate_response(items, EC2Instance)
        assert len(results) == 1

    def test_validate_response_raises_on_error(self):
        items = [{"no_id_here": True}]
        with pytest.raises(ValidationError):
            validate_response(items, EC2Instance, raise_on_error=True)


# ============================================================================
# IAM Users / Roles / Groups
# ============================================================================

class TestIAMResponseModels:
    """Tests for IAM response models."""

    VALID_USER = {
        "UserName": "alice",
        "UserId": "AIDA00000000000000000",
        "Arn": "arn:aws:iam::123456789012:user/alice",
        "Path": "/",
        "CreateDate": datetime.datetime(2024, 1, 1),
    }

    VALID_ROLE = {
        "RoleName": "my-role",
        "RoleId": "AROA00000000000000000",
        "Arn": "arn:aws:iam::123456789012:role/my-role",
        "Path": "/",
        "CreateDate": datetime.datetime(2024, 1, 1),
        "AssumeRolePolicyDocument": {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {"Service": "ec2.amazonaws.com"},
                    "Action": "sts:AssumeRole",
                },
            ],
        },
        "MaxSessionDuration": 3600,
    }

    VALID_GROUP = {
        "GroupName": "developers",
        "GroupId": "AGPA00000000000000000",
        "Arn": "arn:aws:iam::123456789012:group/developers",
        "Path": "/",
        "CreateDate": datetime.datetime(2024, 1, 1),
    }

    def test_valid_user(self):
        user = IAMUser.model_validate(self.VALID_USER)
        assert user.UserName == "alice"
        assert user.Arn.endswith("user/alice")

    def test_missing_user_arn_raises(self):
        bad = {**self.VALID_USER}
        del bad["Arn"]
        with pytest.raises(ValidationError) as exc_info:
            IAMUser.model_validate(bad)
        assert any(e["loc"] == ("Arn",) for e in exc_info.value.errors())

    def test_valid_role(self):
        role = IAMRole.model_validate(self.VALID_ROLE)
        assert role.RoleName == "my-role"
        assert role.AssumeRolePolicyDocument.Statement[0].Effect == "Allow"

    def test_missing_role_name_raises(self):
        bad = {**self.VALID_ROLE}
        del bad["RoleName"]
        with pytest.raises(ValidationError):
            IAMRole.model_validate(bad)

    def test_valid_group(self):
        group = IAMGroup.model_validate(self.VALID_GROUP)
        assert group.GroupName == "developers"

    def test_user_list_response(self):
        resp = IAMUserListResponse.model_validate({"Users": [self.VALID_USER]})
        assert len(resp.Users) == 1

    def test_group_list_response(self):
        resp = IAMGroupListResponse.model_validate({"Groups": [self.VALID_GROUP]})
        assert len(resp.Groups) == 1

    def test_role_list_response(self):
        resp = IAMRoleListResponse.model_validate({"Roles": [self.VALID_ROLE]})
        assert len(resp.Roles) == 1

    def test_extra_fields_allowed(self):
        data = {**self.VALID_USER, "PermissionsBoundary": {"some": "thing"}}
        user = IAMUser.model_validate(data)
        assert user.UserName == "alice"


# ============================================================================
# S3 Buckets
# ============================================================================

class TestS3ResponseModels:
    """Tests for S3 response models."""

    VALID_BUCKET = {
        "Name": "my-bucket",
        "CreationDate": datetime.datetime(2024, 1, 1),
        "Region": "us-east-1",
    }

    VALID_LIST_RESPONSE = {
        "Buckets": [
            {"Name": "bucket-1", "CreationDate": datetime.datetime(2024, 1, 1), "Region": "eu-west-1"},
            {"Name": "bucket-2", "CreationDate": datetime.datetime(2024, 2, 1), "Region": None},
        ],
        "Owner": {"DisplayName": "owner", "ID": "owner-id"},
    }

    def test_valid_bucket(self):
        bucket = S3Bucket.model_validate(self.VALID_BUCKET)
        assert bucket.Name == "my-bucket"

    def test_bucket_with_null_region(self):
        bucket = S3Bucket.model_validate({"Name": "us-east-bucket", "Region": None})
        assert bucket.Region is None

    def test_missing_name_raises(self):
        with pytest.raises(ValidationError) as exc_info:
            S3Bucket.model_validate({"CreationDate": datetime.datetime(2024, 1, 1)})
        assert any(e["loc"] == ("Name",) for e in exc_info.value.errors())

    def test_list_buckets_response(self):
        resp = S3ListBucketsResponse.model_validate(self.VALID_LIST_RESPONSE)
        assert len(resp.Buckets) == 2
        assert resp.Owner.DisplayName == "owner"

    def test_extra_fields_allowed(self):
        data = {**self.VALID_BUCKET, "BucketRegion": "us-west-2"}
        bucket = S3Bucket.model_validate(data)
        assert bucket.Name == "my-bucket"


# ============================================================================
# GitHub Repos
# ============================================================================

class TestGitHubResponseModels:
    """Tests for GitHub repo response models."""

    VALID_REPO = {
        "name": "my-repo",
        "nameWithOwner": "myorg/my-repo",
        "url": "https://github.com/myorg/my-repo",
        "sshUrl": "git@github.com:myorg/my-repo.git",
        "createdAt": "2024-01-01T00:00:00Z",
        "description": "A test repo",
        "updatedAt": "2024-06-01T00:00:00Z",
        "homepageUrl": "",
        "primaryLanguage": {"name": "Python"},
        "languages": {"totalCount": 1, "nodes": [{"name": "Python"}]},
        "defaultBranchRef": {"name": "main", "id": "ref-id"},
        "isPrivate": True,
        "isArchived": False,
        "isDisabled": False,
        "isLocked": False,
        "owner": {
            "url": "https://github.com/myorg",
            "login": "myorg",
            "__typename": "Organization",
        },
        "directCollaborators": {"totalCount": 5},
        "outsideCollaborators": {"totalCount": 2},
        "requirements": {"text": "requests>=2.0"},
        "setupCfg": None,
    }

    def test_valid_repo(self):
        repo = GitHubRepo.model_validate(self.VALID_REPO)
        assert repo.name == "my-repo"
        assert repo.nameWithOwner == "myorg/my-repo"
        assert repo.primaryLanguage.name == "Python"
        assert repo.defaultBranchRef.name == "main"

    def test_minimal_repo(self):
        repo = GitHubRepo.model_validate({
            "name": "min",
            "nameWithOwner": "org/min",
            "url": "https://github.com/org/min",
        })
        assert repo.name == "min"
        assert repo.defaultBranchRef is None

    def test_missing_name_raises(self):
        with pytest.raises(ValidationError) as exc_info:
            GitHubRepo.model_validate({"url": "https://github.com/org/repo", "nameWithOwner": "org/repo"})
        assert any(e["loc"] == ("name",) for e in exc_info.value.errors())

    def test_missing_url_raises(self):
        with pytest.raises(ValidationError) as exc_info:
            GitHubRepo.model_validate({"name": "repo", "nameWithOwner": "org/repo"})
        assert any(e["loc"] == ("url",) for e in exc_info.value.errors())

    def test_null_default_branch_ref(self):
        data = {**self.VALID_REPO, "defaultBranchRef": None}
        repo = GitHubRepo.model_validate(data)
        assert repo.defaultBranchRef is None

    def test_extra_fields_allowed(self):
        data = {**self.VALID_REPO, "stargazerCount": 42}
        repo = GitHubRepo.model_validate(data)
        assert repo.name == "my-repo"

    def test_validate_response_utility_with_repos(self):
        results = validate_response(
            [self.VALID_REPO],
            GitHubRepo,
            raise_on_error=True,
            context="GitHub repos",
        )
        assert len(results) == 1


# ============================================================================
# GCP Compute Instances
# ============================================================================

class TestGCPComputeResponseModels:
    """Tests for GCP Compute Engine response models."""

    VALID_INSTANCE = {
        "id": "1234",
        "name": "instance-1",
        "selfLink": "https://www.googleapis.com/compute/v1/projects/proj/zones/zone-a/instances/instance-1",
        "zone": "https://www.googleapis.com/compute/v1/projects/proj/zones/zone-a",
        "machineType": "https://www.googleapis.com/compute/v1/projects/proj/zones/zone-a/machineTypes/n1-standard-1",
        "status": "RUNNING",
        "canIpForward": False,
        "networkInterfaces": [
            {
                "name": "nic0",
                "network": "https://www.googleapis.com/compute/v1/projects/proj/global/networks/default",
                "subnetwork": "https://www.googleapis.com/compute/v1/projects/proj/regions/region/subnetworks/default",
                "networkIP": "10.0.0.2",
                "accessConfigs": [{"name": "External NAT", "natIP": "1.2.3.4", "type": "ONE_TO_ONE_NAT"}],
            },
        ],
        "disks": [
            {
                "deviceName": "instance-1",
                "boot": True,
                "autoDelete": True,
                "source": "https://www.googleapis.com/compute/v1/projects/proj/zones/zone-a/disks/instance-1",
            },
        ],
        "serviceAccounts": [
            {"email": "sa@proj.iam.gserviceaccount.com", "scopes": ["https://www.googleapis.com/auth/cloud-platform"]},
        ],
    }

    VALID_LIST_RESPONSE = {
        "id": "projects/proj/zones/zone-a/instances",
        "items": [VALID_INSTANCE],
        "kind": "compute#instanceList",
    }

    def test_valid_instance(self):
        inst = GCPInstance.model_validate(self.VALID_INSTANCE)
        assert inst.id == "1234"
        assert inst.name == "instance-1"
        assert inst.status == "RUNNING"
        assert inst.networkInterfaces[0].networkIP == "10.0.0.2"

    def test_valid_list_response(self):
        resp = GCPInstanceListResponse.model_validate(self.VALID_LIST_RESPONSE)
        assert len(resp.items) == 1
        assert resp.items[0].name == "instance-1"

    def test_missing_id_raises(self):
        bad = {**self.VALID_INSTANCE}
        del bad["id"]
        with pytest.raises(ValidationError) as exc_info:
            GCPInstance.model_validate(bad)
        assert any(e["loc"] == ("id",) for e in exc_info.value.errors())

    def test_missing_name_raises(self):
        bad = {**self.VALID_INSTANCE}
        del bad["name"]
        with pytest.raises(ValidationError) as exc_info:
            GCPInstance.model_validate(bad)
        assert any(e["loc"] == ("name",) for e in exc_info.value.errors())

    def test_minimal_instance(self):
        inst = GCPInstance.model_validate({"id": "5678", "name": "minimal"})
        assert inst.id == "5678"
        assert inst.networkInterfaces == []

    def test_extra_fields_allowed(self):
        data = {**self.VALID_INSTANCE, "confidentialInstanceConfig": {"enabled": True}}
        inst = GCPInstance.model_validate(data)
        assert inst.name == "instance-1"

    def test_empty_items_list_response(self):
        resp = GCPInstanceListResponse.model_validate({
            "id": "projects/proj/zones/zone-a/instances",
        })
        assert resp.items == []


# ============================================================================
# validate_response utility
# ============================================================================

class TestValidateResponse:
    """Tests for the validate_response() utility function."""

    def test_single_dict_input(self):
        result = validate_response(
            {"InstanceId": "i-single"},
            EC2Instance,
            raise_on_error=True,
        )
        assert len(result) == 1
        assert result[0].InstanceId == "i-single"

    def test_list_input(self):
        result = validate_response(
            [{"InstanceId": "i-1"}, {"InstanceId": "i-2"}],
            EC2Instance,
            raise_on_error=True,
        )
        assert len(result) == 2

    def test_drops_invalid_items_silently(self):
        result = validate_response(
            [{"InstanceId": "i-good"}, {"bad": "data"}],
            EC2Instance,
        )
        assert len(result) == 1
        assert result[0].InstanceId == "i-good"

    def test_raises_on_error_flag(self):
        with pytest.raises(ValidationError):
            validate_response(
                [{"bad": "data"}],
                EC2Instance,
                raise_on_error=True,
            )

    def test_empty_list_returns_empty(self):
        result = validate_response([], EC2Instance, raise_on_error=True)
        assert result == []

    def test_context_label_in_error(self):
        """Ensure context label doesn't break anything (coverage)."""
        result = validate_response(
            [{"bad": "data"}],
            EC2Instance,
            context="EC2 instances",
        )
        assert result == []
