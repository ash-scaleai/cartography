"""
Schema-declared computed relationships for GSuite Human identity linking.

This replaces the JSON analysis job at:
    cartography/data/jobs/analysis/gsuite_human_link.json
"""
from cartography.models.core.computed import AnalysisJob
from cartography.models.core.computed import ComputedRelationship


HUMAN_TO_GSUITE_USER = ComputedRelationship(
    name='GSuite user map to Human',
    source_label='Human',
    target_label='GSuiteUser',
    relationship_type='IDENTITY_GSUITE',
    cypher_match='(source:Human), (target:GSuiteUser)',
    cypher_where='source.email = target.email',
)

GSUITE_HUMAN_LINK_ANALYSIS = AnalysisJob(
    name='GSuite user map to Human',
    computed_relationships=[HUMAN_TO_GSUITE_USER],
)
