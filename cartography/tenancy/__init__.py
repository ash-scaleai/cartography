# cartography.tenancy - Multi-tenancy support for cartography.
#
# This module provides first-class multi-tenancy so that a single cartography
# instance can serve multiple organisations (MSP use-case).
#
# Two isolation modes are supported:
#   * database  - each tenant gets its own Neo4j database (strongest, requires Neo4j Enterprise)
#   * label     - every node receives an extra ``Tenant_<id>`` label and queries are filtered
#                 accordingly (works with Neo4j Community)
#
# When no tenant configuration is supplied cartography runs in legacy
# single-tenant mode -- fully backward compatible.
