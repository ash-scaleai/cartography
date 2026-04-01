"""
Schema-declared computed relationships and properties for analysis jobs.

This module provides dataclasses that allow analysis jobs to be declared alongside
schema definitions rather than as raw Cypher in JSON files. ComputedRelationships
and ComputedProperties generate equivalent Cypher to the existing JSON-based
analysis jobs while being co-located with the schema they enrich.

Example:
    >>> from cartography.models.core.computed import ComputedRelationship
    >>> gcp_instance_to_vpc = ComputedRelationship(
    ...     name='GCP Instance to VPC',
    ...     source_label='GCPInstance',
    ...     target_label='GCPVpc',
    ...     relationship_type='MEMBER_OF_GCP_VPC',
    ...     cypher_match=(
    ...         '(source:GCPInstance)-[:NETWORK_INTERFACE]->(nic:GCPNetworkInterface)'
    ...         '-[:PART_OF_SUBNET]->(sn:GCPSubnet)<-[:HAS]-(target:GCPVpc)'
    ...     ),
    ... )
"""
from dataclasses import dataclass
from dataclasses import field
from typing import Dict
from typing import List
from typing import Optional


@dataclass(frozen=True)
class ComputedRelationship:
    """
    A schema-declared computed relationship that generates analysis Cypher.

    ComputedRelationships represent derived relationships that are computed by
    traversing existing graph paths. They replace raw Cypher in JSON analysis
    job files with structured, schema-co-located declarations.

    The generated Cypher will:
    1. MATCH the specified path pattern (cypher_match)
    2. Optionally filter with WHERE (cypher_where)
    3. MERGE the relationship between source and target
    4. SET firstseen on CREATE and lastupdated always
    5. Generate a cleanup query to delete stale relationships

    Attributes:
        name: Human-readable name for this computed relationship.
        source_label: Neo4j label of the source node (used in cleanup query).
        target_label: Neo4j label of the target node (used in cleanup query).
        relationship_type: The Neo4j relationship type to create (e.g., 'MEMBER_OF_GCP_VPC').
        cypher_match: The MATCH clause pattern. Must use 'source' and 'target' as aliases
            for the source and target nodes respectively.
        cypher_where: Optional WHERE clause filter (without the WHERE keyword).
        properties: Optional dict of additional properties to SET on the relationship.
            Keys are property names, values are Cypher expressions.
        cleanup_iterative: Whether the cleanup query should run iteratively. Defaults to True.
        cleanup_batch_size: Batch size for iterative cleanup. Defaults to 100.

    Examples:
        Basic computed relationship:
        >>> gcp_instance_vpc = ComputedRelationship(
        ...     name='GCP Instance to VPC',
        ...     source_label='GCPInstance',
        ...     target_label='GCPVpc',
        ...     relationship_type='MEMBER_OF_GCP_VPC',
        ...     cypher_match=(
        ...         '(source:GCPInstance)-[:NETWORK_INTERFACE]->(nic:GCPNetworkInterface)'
        ...         '-[:PART_OF_SUBNET]->(sn:GCPSubnet)<-[:HAS]-(target:GCPVpc)'
        ...     ),
        ... )

        Computed relationship with WHERE clause:
        >>> lambda_ecr = ComputedRelationship(
        ...     name='Lambda to ECR Image',
        ...     source_label='AWSLambda',
        ...     target_label='ECRImage',
        ...     relationship_type='HAS',
        ...     cypher_match='(source:AWSLambda), (target:ECRImage)',
        ...     cypher_where="target.digest = 'sha256:' + source.codesha256",
        ... )
    """

    name: str
    source_label: str
    target_label: str
    relationship_type: str
    cypher_match: str
    cypher_where: Optional[str] = None
    properties: Optional[Dict[str, str]] = None
    cleanup_iterative: bool = True
    cleanup_batch_size: int = 100


@dataclass(frozen=True)
class ComputedProperty:
    """
    A schema-declared computed property that generates analysis Cypher.

    ComputedProperties represent derived node properties that are computed from
    existing graph data. They replace raw Cypher SET operations in JSON analysis
    job files.

    Attributes:
        node_label: The Neo4j label of the node to set the property on.
        property_name: The name of the property to set.
        cypher_expression: A Cypher expression that computes the property value.
            The node is aliased as 'n' in the generated query.
        cypher_match: Optional custom MATCH clause. If not provided, defaults to
            'MATCH (n:<node_label>)'.
        cypher_where: Optional WHERE clause filter (without the WHERE keyword).

    Examples:
        Mark foreign AWS accounts:
        >>> foreign_account = ComputedProperty(
        ...     node_label='AWSAccount',
        ...     property_name='foreign',
        ...     cypher_expression='true',
        ...     cypher_where='n.inscope IS NULL',
        ... )
    """

    node_label: str
    property_name: str
    cypher_expression: str
    cypher_match: Optional[str] = None
    cypher_where: Optional[str] = None


@dataclass(frozen=True)
class AnalysisJob:
    """
    A collection of computed relationships and properties forming a complete analysis job.

    This groups related ComputedRelationships and ComputedProperties together,
    analogous to a JSON analysis job file.

    Attributes:
        name: Human-readable name for the analysis job.
        computed_relationships: List of computed relationships in this job.
        computed_properties: List of computed properties in this job.

    Examples:
        >>> job = AnalysisJob(
        ...     name='GCP Instance to VPC analysis',
        ...     computed_relationships=[gcp_instance_vpc],
        ... )
    """

    name: str
    computed_relationships: List[ComputedRelationship] = field(default_factory=list)
    computed_properties: List[ComputedProperty] = field(default_factory=list)
