"""
Schema-declared computed relationships for GCP Instance to VPC analysis.

This replaces the JSON analysis job at:
    cartography/data/jobs/analysis/gcp_compute_instance_vpc_analysis.json
"""
from cartography.models.core.computed import AnalysisJob
from cartography.models.core.computed import ComputedRelationship


GCP_INSTANCE_TO_VPC = ComputedRelationship(
    name='GCP Instance to VPC derived relationship',
    source_label='GCPInstance',
    target_label='GCPVpc',
    relationship_type='MEMBER_OF_GCP_VPC',
    cypher_match=(
        '(source:GCPInstance)-[:NETWORK_INTERFACE]->(nic:GCPNetworkInterface)'
        '-[:PART_OF_SUBNET]->(sn:GCPSubnet)<-[:HAS]-(target:GCPVpc)'
    ),
)

GCP_INSTANCE_VPC_ANALYSIS = AnalysisJob(
    name='GCP Instance to VPC derived relationship analysis',
    computed_relationships=[GCP_INSTANCE_TO_VPC],
)
