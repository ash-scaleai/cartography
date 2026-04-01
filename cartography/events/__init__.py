# cartography.events - Event-driven incremental sync support
#
# This package provides optional event-driven sync capabilities for cartography.
# Instead of running full syncs, cloud events (e.g., from CloudTrail) can trigger
# targeted re-syncs of only the affected module/region.
#
# This is fully optional - missing configuration means no-op. Full sync remains
# the primary mode; events are supplementary.
