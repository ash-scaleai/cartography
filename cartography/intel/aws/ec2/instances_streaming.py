"""
Example migration: EC2 instances using streaming ingestion.

This module demonstrates how an existing intel module can opt-in to the new
streaming ingestion path.  The original ``instances.py`` module is untouched
and continues to work as before (backward compatible).

Key differences from the non-streaming version:

* ``get_ec2_instances_streaming()`` returns a *generator* that yields one page
  of reservations at a time, instead of accumulating all pages into a list.
* ``sync_ec2_instances_streaming()`` feeds each page through
  ``transform_ec2_instances()`` and then into a ``StreamingLoader``, so only
  one page's worth of data is in memory at any time.
* Cleanup still runs once at the end, using the same update_tag that was
  applied to every batch.
"""

import logging
from typing import Any
from typing import Dict
from typing import Generator
from typing import List

import boto3
import neo4j

from cartography.client.core.streaming import StreamingLoader
from cartography.graph.job import GraphJob
from cartography.intel.aws.ec2.instances import transform_ec2_instances
from cartography.intel.aws.ec2.instances import cleanup
from cartography.intel.aws.util.botocore_config import create_boto3_client
from cartography.intel.aws.util.botocore_config import get_botocore_config
from cartography.intel.util.pagination import paginated_get_aws
from cartography.models.aws.ec2.instances import EC2InstanceSchema
from cartography.models.aws.ec2.reservations import EC2ReservationSchema
from cartography.util import timeit

logger = logging.getLogger(__name__)


@timeit
def get_ec2_instances_streaming(
    boto3_session: boto3.session.Session,
    region: str,
) -> Generator[List[Dict[str, Any]], None, None]:
    """
    Yield pages of EC2 reservations one at a time (streaming).

    Unlike ``get_ec2_instances()`` which returns a complete list, this function
    returns a generator so the caller can process and discard each page before
    fetching the next.
    """
    client = create_boto3_client(
        boto3_session,
        "ec2",
        region_name=region,
        config=get_botocore_config(),
    )
    paginator = client.get_paginator("describe_instances")
    yield from paginated_get_aws(paginator, result_key="Reservations")


def _instance_page_generator(
    boto3_session: boto3.session.Session,
    region: str,
    current_aws_account_id: str,
) -> Generator[List[Dict[str, Any]], None, None]:
    """
    Yield transformed instance dicts, one page at a time.

    Each page of raw reservations is transformed and then yielded so the
    StreamingLoader can write it to Neo4j immediately.
    """
    for reservation_page in get_ec2_instances_streaming(boto3_session, region):
        ec2_data = transform_ec2_instances(
            reservation_page, region, current_aws_account_id,
        )
        if ec2_data.instance_list:
            yield ec2_data.instance_list


@timeit
def sync_ec2_instances_streaming(
    neo4j_session: neo4j.Session,
    boto3_session: boto3.session.Session,
    regions: List[str],
    current_aws_account_id: str,
    update_tag: int,
    common_job_parameters: Dict[str, Any],
    batch_size: int = 1000,
) -> None:
    """
    Sync EC2 instances using streaming ingestion.

    This is a drop-in replacement for ``sync_ec2_instances`` that streams
    pages to Neo4j rather than buffering everything in memory.  The same
    cleanup runs at the end, and the same update_tag is used for every batch.
    """
    for region in regions:
        logger.info(
            "Syncing EC2 instances (streaming) for region '%s' in account '%s'.",
            region,
            current_aws_account_id,
        )

        loader = StreamingLoader(
            neo4j_session=neo4j_session,
            node_schema=EC2InstanceSchema(),
            update_tag=update_tag,
            batch_size=batch_size,
            labeling_kwargs={
                "AWS_ID": current_aws_account_id,
                "Region": region,
            },
        )

        pages = _instance_page_generator(
            boto3_session, region, current_aws_account_id,
        )
        loader.load_batches(pages)

    # Cleanup runs once after all regions, same as the non-streaming path.
    cleanup(neo4j_session, common_job_parameters)
