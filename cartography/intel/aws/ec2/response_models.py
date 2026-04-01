"""
Pydantic response models for AWS EC2 DescribeInstances API data.

These models validate the raw API response *before* it enters the
transform/load pipeline.  They are intentionally permissive
(``extra='allow'``) so that new fields added by AWS do not break syncs.
"""
from __future__ import annotations

import datetime
from typing import Any
from typing import Optional

from pydantic import BaseModel
from pydantic import ConfigDict


class EC2SecurityGroup(BaseModel):
    """A security group reference on an EC2 instance."""

    model_config = ConfigDict(extra="allow")

    GroupId: str
    GroupName: Optional[str] = None


class EC2EbsAttachment(BaseModel):
    """EBS volume attachment within a BlockDeviceMapping."""

    model_config = ConfigDict(extra="allow")

    VolumeId: str
    Status: Optional[str] = None
    AttachTime: Optional[datetime.datetime] = None
    DeleteOnTermination: Optional[bool] = None


class EC2BlockDeviceMapping(BaseModel):
    """A single block-device mapping entry."""

    model_config = ConfigDict(extra="allow")

    DeviceName: Optional[str] = None
    Ebs: Optional[EC2EbsAttachment] = None


class EC2NetworkInterfaceGroup(BaseModel):
    """Security group associated with a network interface."""

    model_config = ConfigDict(extra="allow")

    GroupId: str
    GroupName: Optional[str] = None


class EC2NetworkInterface(BaseModel):
    """Network interface attached to an EC2 instance."""

    model_config = ConfigDict(extra="allow")

    NetworkInterfaceId: str
    Status: Optional[str] = None
    MacAddress: Optional[str] = None
    Description: Optional[str] = None
    PrivateDnsName: Optional[str] = None
    PrivateIpAddress: Optional[str] = None
    SubnetId: Optional[str] = None
    Groups: list[EC2NetworkInterfaceGroup] = []


class EC2Placement(BaseModel):
    """Placement information for an instance."""

    model_config = ConfigDict(extra="allow")

    AvailabilityZone: Optional[str] = None
    Tenancy: Optional[str] = None
    HostResourceGroupArn: Optional[str] = None
    GroupName: Optional[str] = None


class EC2Monitoring(BaseModel):
    """Instance monitoring state."""

    model_config = ConfigDict(extra="allow")

    State: Optional[str] = None


class EC2InstanceState(BaseModel):
    """Current state of the instance."""

    model_config = ConfigDict(extra="allow")

    Code: Optional[int] = None
    Name: Optional[str] = None


class EC2IamInstanceProfile(BaseModel):
    """IAM instance profile attached to an instance."""

    model_config = ConfigDict(extra="allow")

    Arn: Optional[str] = None
    Id: Optional[str] = None


class EC2MetadataOptions(BaseModel):
    """Instance metadata options (IMDS configuration)."""

    model_config = ConfigDict(extra="allow")

    HttpTokens: Optional[str] = None
    HttpPutResponseHopLimit: Optional[int] = None
    HttpEndpoint: Optional[str] = None
    HttpProtocolIpv6: Optional[str] = None
    InstanceMetadataTags: Optional[str] = None
    State: Optional[str] = None


class EC2HibernationOptions(BaseModel):
    """Hibernation options."""

    model_config = ConfigDict(extra="allow")

    Configured: Optional[bool] = None


class EC2Tag(BaseModel):
    """An EC2 resource tag."""

    model_config = ConfigDict(extra="allow")

    Key: Optional[str] = None
    Value: Optional[str] = None


class EC2Instance(BaseModel):
    """
    A single EC2 instance as returned by DescribeInstances.

    Only the fields that Cartography reads in its transform step are
    declared explicitly; everything else is captured by ``extra='allow'``.
    """

    model_config = ConfigDict(extra="allow")

    InstanceId: str
    ImageId: Optional[str] = None
    InstanceType: Optional[str] = None
    KeyName: Optional[str] = None
    LaunchTime: Optional[datetime.datetime] = None
    Monitoring: Optional[EC2Monitoring] = None
    Placement: Optional[EC2Placement] = None
    PrivateIpAddress: Optional[str] = None
    PublicDnsName: Optional[str] = None
    PublicIpAddress: Optional[str] = None
    State: Optional[EC2InstanceState] = None
    SubnetId: Optional[str] = None
    Architecture: Optional[str] = None
    EbsOptimized: Optional[bool] = None
    BootMode: Optional[str] = None
    InstanceLifecycle: Optional[str] = None
    Platform: Optional[str] = None
    IamInstanceProfile: Optional[EC2IamInstanceProfile] = None
    HibernationOptions: Optional[EC2HibernationOptions] = None
    MetadataOptions: Optional[EC2MetadataOptions] = None
    SecurityGroups: list[EC2SecurityGroup] = []
    NetworkInterfaces: list[EC2NetworkInterface] = []
    BlockDeviceMappings: list[EC2BlockDeviceMapping] = []
    Tags: list[EC2Tag] = []


class EC2Reservation(BaseModel):
    """
    A single reservation from the DescribeInstances response.
    Each reservation contains one or more instances.
    """

    model_config = ConfigDict(extra="allow")

    ReservationId: str
    OwnerId: str
    RequesterId: Optional[str] = None
    Instances: list[EC2Instance] = []
    Groups: list[dict[str, Any]] = []
