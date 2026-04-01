"""
Execution engine for schema-declared computed relationships and properties.

This module generates and executes Cypher queries from ComputedRelationship and
ComputedProperty declarations, providing a schema-driven alternative to the
JSON-based analysis job system.

Example:
    >>> from cartography.graph.computed import materialize_computed_relationships
    >>> materialize_computed_relationships(
    ...     neo4j_session,
    ...     [gcp_instance_vpc_rel],
    ...     {'UPDATE_TAG': 12345},
    ... )
"""
import logging
from typing import Dict
from typing import List
from typing import Optional

import neo4j

from cartography.models.core.computed import AnalysisJob
from cartography.models.core.computed import ComputedProperty
from cartography.models.core.computed import ComputedRelationship

logger = logging.getLogger(__name__)


def generate_merge_cypher(computed_rel: ComputedRelationship) -> str:
    """
    Generate a MERGE Cypher query from a ComputedRelationship declaration.

    This creates the Cypher that establishes the computed relationship by matching
    the specified graph pattern and merging the relationship between source and
    target nodes.

    Args:
        computed_rel: The ComputedRelationship to generate Cypher for.

    Returns:
        A Cypher query string that can be executed against Neo4j.

    Examples:
        >>> rel = ComputedRelationship(
        ...     name='test',
        ...     source_label='A',
        ...     target_label='B',
        ...     relationship_type='CONNECTS',
        ...     cypher_match='(source:A)-[:PATH]->(target:B)',
        ... )
        >>> query = generate_merge_cypher(rel)
        >>> 'MATCH (source:A)-[:PATH]->(target:B)' in query
        True
        >>> 'MERGE (source)-[r:CONNECTS]->(target)' in query
        True
    """
    parts = [f"MATCH {computed_rel.cypher_match}"]

    if computed_rel.cypher_where:
        parts.append(f"WHERE {computed_rel.cypher_where}")

    parts.append(f"MERGE (source)-[r:{computed_rel.relationship_type}]->(target)")
    parts.append("ON CREATE SET r.firstseen = timestamp()")
    parts.append("SET r.lastupdated = $UPDATE_TAG")

    if computed_rel.properties:
        for prop_name, prop_expr in computed_rel.properties.items():
            parts.append(f"SET r.{prop_name} = {prop_expr}")

    return "\n".join(parts)


def generate_cleanup_cypher(computed_rel: ComputedRelationship) -> str:
    """
    Generate a cleanup Cypher query that removes stale computed relationships.

    The cleanup query deletes relationships whose lastupdated timestamp does not
    match the current UPDATE_TAG, indicating they were not refreshed in the
    latest analysis run.

    Args:
        computed_rel: The ComputedRelationship to generate cleanup Cypher for.

    Returns:
        A Cypher query string for cleaning up stale relationships.

    Examples:
        >>> rel = ComputedRelationship(
        ...     name='test',
        ...     source_label='A',
        ...     target_label='B',
        ...     relationship_type='CONNECTS',
        ...     cypher_match='(source:A)-[:PATH]->(target:B)',
        ... )
        >>> query = generate_cleanup_cypher(rel)
        >>> 'MATCH (source:A)-[r:CONNECTS]->(target:B)' in query
        True
        >>> 'WHERE r.lastupdated <> $UPDATE_TAG' in query
        True
    """
    parts = [
        f"MATCH (source:{computed_rel.source_label})"
        f"-[r:{computed_rel.relationship_type}]->"
        f"(target:{computed_rel.target_label})",
        "WHERE r.lastupdated <> $UPDATE_TAG",
    ]

    if computed_rel.cleanup_iterative:
        parts.append(f"WITH r LIMIT $LIMIT_SIZE")
        parts.append("DELETE r")
        parts.append("RETURN COUNT(*) as TotalCompleted")
    else:
        parts.append("DELETE r")

    return "\n".join(parts)


def generate_property_cypher(computed_prop: ComputedProperty) -> str:
    """
    Generate a Cypher query from a ComputedProperty declaration.

    Args:
        computed_prop: The ComputedProperty to generate Cypher for.

    Returns:
        A Cypher query string that sets the computed property.

    Examples:
        >>> prop = ComputedProperty(
        ...     node_label='AWSAccount',
        ...     property_name='foreign',
        ...     cypher_expression='true',
        ...     cypher_where='n.inscope IS NULL',
        ... )
        >>> query = generate_property_cypher(prop)
        >>> 'MATCH (n:AWSAccount)' in query
        True
        >>> 'SET n.foreign = true' in query
        True
    """
    if computed_prop.cypher_match:
        parts = [f"MATCH {computed_prop.cypher_match}"]
    else:
        parts = [f"MATCH (n:{computed_prop.node_label})"]

    if computed_prop.cypher_where:
        parts.append(f"WHERE {computed_prop.cypher_where}")

    parts.append(f"SET n.{computed_prop.property_name} = {computed_prop.cypher_expression}")

    return "\n".join(parts)


def materialize_computed_relationships(
    neo4j_session: neo4j.Session,
    computed_rels: List[ComputedRelationship],
    common_job_parameters: Dict,
) -> None:
    """
    Generate and execute Cypher for a list of ComputedRelationships.

    For each ComputedRelationship, this function:
    1. Generates and runs the MERGE query to create/update relationships
    2. Generates and runs the cleanup query to remove stale relationships

    For iterative cleanup queries, the function runs the cleanup in batches
    until no more stale relationships remain.

    Args:
        neo4j_session: Active Neo4j session.
        computed_rels: List of ComputedRelationship declarations to materialize.
        common_job_parameters: Dict containing at least 'UPDATE_TAG'. May also
            contain 'LIMIT_SIZE' for iterative cleanup (defaults to 100).

    Examples:
        >>> materialize_computed_relationships(
        ...     neo4j_session,
        ...     [gcp_instance_vpc_rel],
        ...     {'UPDATE_TAG': 12345},
        ... )
    """
    for rel in computed_rels:
        logger.info(f"Materializing computed relationship: {rel.name}")

        # Run the merge query
        merge_query = generate_merge_cypher(rel)
        neo4j_session.run(merge_query, **common_job_parameters)

        # Run cleanup
        cleanup_query = generate_cleanup_cypher(rel)
        params = dict(common_job_parameters)
        if 'LIMIT_SIZE' not in params:
            params['LIMIT_SIZE'] = rel.cleanup_batch_size

        if rel.cleanup_iterative:
            _run_iterative_cleanup(neo4j_session, cleanup_query, params)
        else:
            neo4j_session.run(cleanup_query, **params)


def materialize_computed_properties(
    neo4j_session: neo4j.Session,
    computed_props: List[ComputedProperty],
    common_job_parameters: Dict,
) -> None:
    """
    Generate and execute Cypher for a list of ComputedProperties.

    Args:
        neo4j_session: Active Neo4j session.
        computed_props: List of ComputedProperty declarations to materialize.
        common_job_parameters: Dict containing at least 'UPDATE_TAG'.

    Examples:
        >>> materialize_computed_properties(
        ...     neo4j_session,
        ...     [foreign_account_prop],
        ...     {'UPDATE_TAG': 12345},
        ... )
    """
    for prop in computed_props:
        logger.info(f"Materializing computed property: {prop.node_label}.{prop.property_name}")
        query = generate_property_cypher(prop)
        neo4j_session.run(query, **common_job_parameters)


def run_analysis_job_from_schema(
    neo4j_session: neo4j.Session,
    analysis_job: AnalysisJob,
    common_job_parameters: Dict,
) -> None:
    """
    Execute a complete schema-declared AnalysisJob.

    This is the primary entry point for running schema-declared analysis jobs,
    serving as the schema-based equivalent of ``run_analysis_job()`` from
    ``cartography.util``.

    Args:
        neo4j_session: Active Neo4j session.
        analysis_job: The AnalysisJob to execute.
        common_job_parameters: Dict containing at least 'UPDATE_TAG'.

    Examples:
        >>> run_analysis_job_from_schema(
        ...     neo4j_session,
        ...     gcp_vpc_analysis_job,
        ...     {'UPDATE_TAG': 12345},
        ... )
    """
    logger.info(f"Running schema-declared analysis job: {analysis_job.name}")

    if analysis_job.computed_relationships:
        materialize_computed_relationships(
            neo4j_session,
            analysis_job.computed_relationships,
            common_job_parameters,
        )

    if analysis_job.computed_properties:
        materialize_computed_properties(
            neo4j_session,
            analysis_job.computed_properties,
            common_job_parameters,
        )


def _run_iterative_cleanup(
    neo4j_session: neo4j.Session,
    query: str,
    params: Dict,
) -> None:
    """
    Run a cleanup query iteratively until no more results are returned.

    Args:
        neo4j_session: Active Neo4j session.
        query: The cleanup Cypher query with LIMIT and RETURN COUNT(*).
        params: Query parameters including LIMIT_SIZE.
    """
    while True:
        result = neo4j_session.run(query, **params)
        record = result.single()
        if record is None or record['TotalCompleted'] == 0:
            break
