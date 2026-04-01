"""
Tests for schema-declared computed relationships and properties.

Tests cover:
- Cypher generation from ComputedRelationship declarations
- Cypher generation from ComputedProperty declarations
- Materialization execution
- Equivalence between generated Cypher and original JSON job Cypher
- Handling of optional fields
"""
from unittest.mock import call
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest

from cartography.graph.computed import generate_cleanup_cypher
from cartography.graph.computed import generate_merge_cypher
from cartography.graph.computed import generate_property_cypher
from cartography.graph.computed import materialize_computed_properties
from cartography.graph.computed import materialize_computed_relationships
from cartography.graph.computed import run_analysis_job_from_schema
from cartography.models.core.computed import AnalysisJob
from cartography.models.core.computed import ComputedProperty
from cartography.models.core.computed import ComputedRelationship


class TestGenerateMergeCypher:
    """Tests for generate_merge_cypher."""

    def test_basic_relationship(self):
        rel = ComputedRelationship(
            name='test rel',
            source_label='NodeA',
            target_label='NodeB',
            relationship_type='CONNECTS_TO',
            cypher_match='(source:NodeA)-[:PATH]->(x:Intermediate)<-[:OTHER]-(target:NodeB)',
        )
        query = generate_merge_cypher(rel)

        assert 'MATCH (source:NodeA)-[:PATH]->(x:Intermediate)<-[:OTHER]-(target:NodeB)' in query
        assert 'MERGE (source)-[r:CONNECTS_TO]->(target)' in query
        assert 'ON CREATE SET r.firstseen = timestamp()' in query
        assert 'SET r.lastupdated = $UPDATE_TAG' in query
        # No WHERE clause
        assert 'WHERE' not in query

    def test_relationship_with_where(self):
        rel = ComputedRelationship(
            name='test rel with where',
            source_label='AWSLambda',
            target_label='ECRImage',
            relationship_type='HAS',
            cypher_match='(source:AWSLambda), (target:ECRImage)',
            cypher_where="target.digest = 'sha256:' + source.codesha256",
        )
        query = generate_merge_cypher(rel)

        assert 'MATCH (source:AWSLambda), (target:ECRImage)' in query
        assert "WHERE target.digest = 'sha256:' + source.codesha256" in query
        assert 'MERGE (source)-[r:HAS]->(target)' in query

    def test_relationship_with_properties(self):
        rel = ComputedRelationship(
            name='test rel with props',
            source_label='A',
            target_label='B',
            relationship_type='LINKS',
            cypher_match='(source:A), (target:B)',
            properties={'weight': '1.0', 'source_type': "'computed'"},
        )
        query = generate_merge_cypher(rel)

        assert 'SET r.weight = 1.0' in query
        assert "SET r.source_type = 'computed'" in query

    def test_no_optional_fields(self):
        """Test that a minimal ComputedRelationship generates valid Cypher."""
        rel = ComputedRelationship(
            name='minimal',
            source_label='X',
            target_label='Y',
            relationship_type='REL',
            cypher_match='(source:X), (target:Y)',
        )
        query = generate_merge_cypher(rel)

        assert 'WHERE' not in query
        # Should only have firstseen and lastupdated SET clauses
        lines = query.split('\n')
        set_lines = [line for line in lines if line.startswith('SET r.')]
        assert len(set_lines) == 1  # Only lastupdated
        assert 'SET r.lastupdated = $UPDATE_TAG' in query


class TestGenerateCleanupCypher:
    """Tests for generate_cleanup_cypher."""

    def test_iterative_cleanup(self):
        rel = ComputedRelationship(
            name='test',
            source_label='GCPInstance',
            target_label='GCPVpc',
            relationship_type='MEMBER_OF_GCP_VPC',
            cypher_match='(source:GCPInstance)-[:NETWORK_INTERFACE]->(target:GCPVpc)',
            cleanup_iterative=True,
            cleanup_batch_size=100,
        )
        query = generate_cleanup_cypher(rel)

        assert 'MATCH (source:GCPInstance)-[r:MEMBER_OF_GCP_VPC]->(target:GCPVpc)' in query
        assert 'WHERE r.lastupdated <> $UPDATE_TAG' in query
        assert 'WITH r LIMIT $LIMIT_SIZE' in query
        assert 'DELETE r' in query
        assert 'RETURN COUNT(*) as TotalCompleted' in query

    def test_non_iterative_cleanup(self):
        rel = ComputedRelationship(
            name='test',
            source_label='AWSLambda',
            target_label='ECRImage',
            relationship_type='HAS',
            cypher_match='(source:AWSLambda), (target:ECRImage)',
            cleanup_iterative=False,
        )
        query = generate_cleanup_cypher(rel)

        assert 'MATCH (source:AWSLambda)-[r:HAS]->(target:ECRImage)' in query
        assert 'WHERE r.lastupdated <> $UPDATE_TAG' in query
        assert 'LIMIT' not in query
        assert 'TotalCompleted' not in query


class TestGeneratePropertyCypher:
    """Tests for generate_property_cypher."""

    def test_basic_property(self):
        prop = ComputedProperty(
            node_label='AWSAccount',
            property_name='foreign',
            cypher_expression='true',
            cypher_where='n.inscope IS NULL',
        )
        query = generate_property_cypher(prop)

        assert 'MATCH (n:AWSAccount)' in query
        assert 'WHERE n.inscope IS NULL' in query
        assert 'SET n.foreign = true' in query

    def test_property_without_where(self):
        prop = ComputedProperty(
            node_label='TestNode',
            property_name='computed_val',
            cypher_expression='42',
        )
        query = generate_property_cypher(prop)

        assert 'MATCH (n:TestNode)' in query
        assert 'WHERE' not in query
        assert 'SET n.computed_val = 42' in query

    def test_property_with_custom_match(self):
        prop = ComputedProperty(
            node_label='AWSAccount',
            property_name='foreign',
            cypher_expression='true',
            cypher_match='(n:AWSAccount)-[:RESOURCE]->(r:EC2Instance)',
            cypher_where='r.public = true',
        )
        query = generate_property_cypher(prop)

        assert 'MATCH (n:AWSAccount)-[:RESOURCE]->(r:EC2Instance)' in query
        assert 'WHERE r.public = true' in query

    def test_all_optional_fields_none(self):
        """Test ComputedProperty with only required fields."""
        prop = ComputedProperty(
            node_label='Node',
            property_name='status',
            cypher_expression="'active'",
        )
        query = generate_property_cypher(prop)

        assert 'MATCH (n:Node)' in query
        assert "SET n.status = 'active'" in query
        assert 'WHERE' not in query


class TestMaterializeComputedRelationships:
    """Tests for materialize_computed_relationships."""

    def test_runs_merge_and_cleanup(self):
        mock_session = MagicMock()
        # For iterative cleanup, simulate one batch then done
        mock_result = MagicMock()
        mock_record = MagicMock()
        mock_record.__getitem__ = MagicMock(return_value=0)
        mock_result.single.return_value = mock_record
        mock_session.run.return_value = mock_result

        rel = ComputedRelationship(
            name='test',
            source_label='A',
            target_label='B',
            relationship_type='REL',
            cypher_match='(source:A), (target:B)',
        )

        materialize_computed_relationships(
            mock_session, [rel], {'UPDATE_TAG': 123},
        )

        # Should have at least 2 calls: merge + cleanup
        assert mock_session.run.call_count >= 2

        # First call is the merge query
        first_call_query = mock_session.run.call_args_list[0][0][0]
        assert 'MERGE' in first_call_query

        # Second call is the cleanup query
        second_call_query = mock_session.run.call_args_list[1][0][0]
        assert 'DELETE' in second_call_query

    def test_multiple_relationships(self):
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_record = MagicMock()
        mock_record.__getitem__ = MagicMock(return_value=0)
        mock_result.single.return_value = mock_record
        mock_session.run.return_value = mock_result

        rels = [
            ComputedRelationship(
                name='rel1', source_label='A', target_label='B',
                relationship_type='REL1', cypher_match='(source:A), (target:B)',
            ),
            ComputedRelationship(
                name='rel2', source_label='C', target_label='D',
                relationship_type='REL2', cypher_match='(source:C), (target:D)',
            ),
        ]

        materialize_computed_relationships(
            mock_session, rels, {'UPDATE_TAG': 123},
        )

        # Should have calls for both relationships (merge + cleanup each)
        assert mock_session.run.call_count >= 4

    def test_non_iterative_cleanup(self):
        mock_session = MagicMock()

        rel = ComputedRelationship(
            name='test',
            source_label='A',
            target_label='B',
            relationship_type='REL',
            cypher_match='(source:A), (target:B)',
            cleanup_iterative=False,
        )

        materialize_computed_relationships(
            mock_session, [rel], {'UPDATE_TAG': 123},
        )

        # Exactly 2 calls: merge + non-iterative cleanup
        assert mock_session.run.call_count == 2


class TestMaterializeComputedProperties:
    """Tests for materialize_computed_properties."""

    def test_runs_property_queries(self):
        mock_session = MagicMock()

        props = [
            ComputedProperty(
                node_label='AWSAccount',
                property_name='foreign',
                cypher_expression='true',
                cypher_where='n.inscope IS NULL',
            ),
        ]

        materialize_computed_properties(
            mock_session, props, {'UPDATE_TAG': 123},
        )

        assert mock_session.run.call_count == 1
        query = mock_session.run.call_args[0][0]
        assert 'SET n.foreign = true' in query


class TestRunAnalysisJobFromSchema:
    """Tests for run_analysis_job_from_schema."""

    def test_runs_both_rels_and_props(self):
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_record = MagicMock()
        mock_record.__getitem__ = MagicMock(return_value=0)
        mock_result.single.return_value = mock_record
        mock_session.run.return_value = mock_result

        job = AnalysisJob(
            name='test job',
            computed_relationships=[
                ComputedRelationship(
                    name='rel', source_label='A', target_label='B',
                    relationship_type='REL', cypher_match='(source:A), (target:B)',
                ),
            ],
            computed_properties=[
                ComputedProperty(
                    node_label='A', property_name='computed', cypher_expression='true',
                ),
            ],
        )

        run_analysis_job_from_schema(mock_session, job, {'UPDATE_TAG': 123})

        # At least 3 calls: merge + cleanup + property
        assert mock_session.run.call_count >= 3

    def test_empty_job(self):
        mock_session = MagicMock()

        job = AnalysisJob(name='empty job')

        run_analysis_job_from_schema(mock_session, job, {'UPDATE_TAG': 123})

        assert mock_session.run.call_count == 0


class TestJsonEquivalence:
    """
    Verify that schema-declared computed relationships generate Cypher
    equivalent to the original JSON analysis jobs.
    """

    def test_gcp_instance_vpc_merge_equivalence(self):
        """
        Original JSON merge query:
            MATCH (i:GCPInstance)-[:NETWORK_INTERFACE]->(nic:GCPNetworkInterface)
            -[:PART_OF_SUBNET]->(sn:GCPSubnet)<-[:HAS]-(vpc:GCPVpc)
            MERGE (i)-[m:MEMBER_OF_GCP_VPC]->(vpc)
            ON CREATE SET m.firstseen = timestamp()
            SET m.lastupdated = $UPDATE_TAG
        """
        from cartography.models.computed_relationships.gcp_compute_instance_vpc import (
            GCP_INSTANCE_TO_VPC,
        )
        query = generate_merge_cypher(GCP_INSTANCE_TO_VPC)

        # Verify the MATCH pattern traverses the same path
        assert '(source:GCPInstance)-[:NETWORK_INTERFACE]->(nic:GCPNetworkInterface)' in query
        assert '-[:PART_OF_SUBNET]->(sn:GCPSubnet)<-[:HAS]-(target:GCPVpc)' in query
        # Verify MERGE creates the same relationship type
        assert 'MERGE (source)-[r:MEMBER_OF_GCP_VPC]->(target)' in query
        # Verify firstseen and lastupdated are set
        assert 'ON CREATE SET r.firstseen = timestamp()' in query
        assert 'SET r.lastupdated = $UPDATE_TAG' in query

    def test_gcp_instance_vpc_cleanup_equivalence(self):
        """
        Original JSON cleanup query:
            MATCH (i:GCPInstance)-[r:MEMBER_OF_GCP_VPC]->(vpc:GCPVpc)
            WHERE r.lastupdated <> $UPDATE_TAG
            WITH r LIMIT $LIMIT_SIZE DELETE r
            RETURN COUNT(*) as TotalCompleted
        """
        from cartography.models.computed_relationships.gcp_compute_instance_vpc import (
            GCP_INSTANCE_TO_VPC,
        )
        query = generate_cleanup_cypher(GCP_INSTANCE_TO_VPC)

        assert 'MATCH (source:GCPInstance)-[r:MEMBER_OF_GCP_VPC]->(target:GCPVpc)' in query
        assert 'WHERE r.lastupdated <> $UPDATE_TAG' in query
        assert 'WITH r LIMIT $LIMIT_SIZE' in query
        assert 'DELETE r' in query
        assert 'RETURN COUNT(*) as TotalCompleted' in query

    def test_aws_lambda_ecr_merge_equivalence(self):
        """
        Original JSON merge query:
            MATCH (l:AWSLambda)
            WITH COLLECT(l) as lmbda_list
            UNWIND lmbda_list as lmbda
            MATCH (e:ECRImage)
            WHERE e.digest = 'sha256:' + lmbda.codesha256
            MERGE (lmbda)-[r:HAS]->(e)
            SET r.lastupdated = $UPDATE_TAG

        The schema version generates a simpler but semantically equivalent query
        using a direct cross-match with WHERE clause instead of COLLECT/UNWIND.
        """
        from cartography.models.computed_relationships.aws_lambda_ecr import (
            AWS_LAMBDA_TO_ECR_IMAGE,
        )
        query = generate_merge_cypher(AWS_LAMBDA_TO_ECR_IMAGE)

        # Verify both source and target are matched
        assert 'MATCH (source:AWSLambda), (target:ECRImage)' in query
        # Verify the WHERE clause filters by digest
        assert "WHERE target.digest = 'sha256:' + source.codesha256" in query
        # Verify MERGE creates the same relationship
        assert 'MERGE (source)-[r:HAS]->(target)' in query
        assert 'SET r.lastupdated = $UPDATE_TAG' in query

    def test_aws_lambda_ecr_cleanup_equivalence(self):
        """
        Original JSON cleanup query:
            MATCH (:AWSLambda)-[r:HAS]->(:ECRImage) WHERE r.lastupdated <> $UPDATE_TAG DELETE (r)
        """
        from cartography.models.computed_relationships.aws_lambda_ecr import (
            AWS_LAMBDA_TO_ECR_IMAGE,
        )
        query = generate_cleanup_cypher(AWS_LAMBDA_TO_ECR_IMAGE)

        assert 'MATCH (source:AWSLambda)-[r:HAS]->(target:ECRImage)' in query
        assert 'WHERE r.lastupdated <> $UPDATE_TAG' in query
        assert 'DELETE r' in query
        # Non-iterative, so no LIMIT
        assert 'LIMIT' not in query

    def test_gsuite_human_link_merge_equivalence(self):
        """
        Original JSON merge query:
            MATCH (human:Human), (guser:GSuiteUser)
            WHERE human.email = guser.email
            MERGE (human)-[r:IDENTITY_GSUITE]->(guser)
            ON CREATE SET r.firstseen = $UPDATE_TAG
            SET r.lastupdated = $UPDATE_TAG
        """
        from cartography.models.computed_relationships.gsuite_human_link import (
            HUMAN_TO_GSUITE_USER,
        )
        query = generate_merge_cypher(HUMAN_TO_GSUITE_USER)

        assert 'MATCH (source:Human), (target:GSuiteUser)' in query
        assert 'WHERE source.email = target.email' in query
        assert 'MERGE (source)-[r:IDENTITY_GSUITE]->(target)' in query
        assert 'ON CREATE SET r.firstseen = timestamp()' in query
        assert 'SET r.lastupdated = $UPDATE_TAG' in query

    def test_gsuite_human_link_cleanup_equivalence(self):
        """
        Original JSON cleanup query:
            MATCH (:Human)-[r:IDENTITY_GSUITE]->(:GSuiteUser)
            WHERE r.lastupdated <> $UPDATE_TAG
            WITH r LIMIT $LIMIT_SIZE DELETE (r)
            return COUNT(*) as TotalCompleted
        """
        from cartography.models.computed_relationships.gsuite_human_link import (
            HUMAN_TO_GSUITE_USER,
        )
        query = generate_cleanup_cypher(HUMAN_TO_GSUITE_USER)

        assert 'MATCH (source:Human)-[r:IDENTITY_GSUITE]->(target:GSuiteUser)' in query
        assert 'WHERE r.lastupdated <> $UPDATE_TAG' in query
        assert 'With r LIMIT $LIMIT_SIZE' in query or 'WITH r LIMIT $LIMIT_SIZE' in query
        assert 'DELETE r' in query
        assert 'RETURN COUNT(*) as TotalCompleted' in query


class TestComputedRelationshipDefaults:
    """Test that optional fields have sensible defaults."""

    def test_defaults(self):
        rel = ComputedRelationship(
            name='test',
            source_label='A',
            target_label='B',
            relationship_type='REL',
            cypher_match='(source:A), (target:B)',
        )
        assert rel.cypher_where is None
        assert rel.properties is None
        assert rel.cleanup_iterative is True
        assert rel.cleanup_batch_size == 100

    def test_computed_property_defaults(self):
        prop = ComputedProperty(
            node_label='Node',
            property_name='val',
            cypher_expression='true',
        )
        assert prop.cypher_match is None
        assert prop.cypher_where is None

    def test_analysis_job_defaults(self):
        job = AnalysisJob(name='test')
        assert job.computed_relationships == []
        assert job.computed_properties == []


class TestFrozenDataclasses:
    """Verify that dataclasses are immutable."""

    def test_computed_relationship_frozen(self):
        rel = ComputedRelationship(
            name='test',
            source_label='A',
            target_label='B',
            relationship_type='REL',
            cypher_match='(source:A), (target:B)',
        )
        with pytest.raises(AttributeError):
            rel.name = 'changed'

    def test_computed_property_frozen(self):
        prop = ComputedProperty(
            node_label='Node',
            property_name='val',
            cypher_expression='true',
        )
        with pytest.raises(AttributeError):
            prop.node_label = 'changed'
