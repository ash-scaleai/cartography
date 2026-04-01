import logging
from typing import Any
from typing import Callable
from typing import Dict
from typing import List

import neo4j

from cartography.sync.checksum import compute_checksum
from cartography.sync.checksum import ChecksumStore
from cartography.sync.checksum import filter_unchanged
from cartography.sync.checksum import update_checksums

logger = logging.getLogger(__name__)


class DifferentialSyncManager:
    """
    Coordinates checksum-based differential sync for a single module.

    Instead of loading every record on every run, it compares checksums to
    detect changes and only hands *changed* records to the load function.

    Usage::

        dsm = DifferentialSyncManager(neo4j_session, "ec2:instance", id_field="InstanceId")
        dsm.sync_with_diff(records, load_func, lastupdated=update_tag)

    The ``load_func`` callable receives ``(changed_records)`` plus any extra
    ``**kwargs`` forwarded from :meth:`sync_with_diff`.
    """

    def __init__(
        self,
        neo4j_session: neo4j.Session,
        module_name: str,
        id_field: str = "id",
    ) -> None:
        self._session = neo4j_session
        self._module_name = module_name
        self._id_field = id_field
        self._store = ChecksumStore(neo4j_session)

    @property
    def module_name(self) -> str:
        return self._module_name

    def sync_with_diff(
        self,
        records: List[Dict[str, Any]],
        load_func: Callable[..., Any],
        lastupdated: int = 0,
        **kwargs: Any,
    ) -> Dict[str, int]:
        """
        Run a differential sync cycle.

        1. Compute checksums for incoming records.
        2. Compare against stored checksums to find changed/new records.
        3. Call *load_func* with only the changed records.
        4. Update stored checksums for those records.
        5. Log statistics.

        :param records: All records fetched from the upstream source.
        :param load_func: A callable that ingests data, e.g.
            ``lambda recs, **kw: load(session, schema, recs, **kw)``.
            It will be called as ``load_func(changed_records, **kwargs)``.
        :param lastupdated: The update tag / timestamp for this sync run.
        :param kwargs: Extra keyword arguments forwarded to *load_func*.
        :return: A dict with keys ``fetched``, ``changed``, ``skipped``.
        """
        total = len(records)

        changed = filter_unchanged(
            records,
            self._module_name,
            self._session,
            id_field=self._id_field,
        )
        changed_count = len(changed)
        skipped_count = total - changed_count

        stats = {
            "fetched": total,
            "changed": changed_count,
            "skipped": skipped_count,
        }

        logger.info(
            "Module %s: %d records fetched, %d changed, %d skipped",
            self._module_name,
            total,
            changed_count,
            skipped_count,
        )

        if changed:
            load_func(changed, **kwargs)

        # Update checksums for ingested records so the next run can skip them.
        update_checksums(
            changed,
            self._module_name,
            self._session,
            id_field=self._id_field,
            lastupdated=lastupdated,
        )

        return stats


def sync_with_diff(
    records: List[Dict[str, Any]],
    module_name: str,
    neo4j_session: neo4j.Session,
    load_func: Callable[..., Any],
    id_field: str = "id",
    lastupdated: int = 0,
    **kwargs: Any,
) -> Dict[str, int]:
    """
    Module-level convenience function for one-shot differential sync.

    See :class:`DifferentialSyncManager.sync_with_diff` for full docs.
    """
    manager = DifferentialSyncManager(neo4j_session, module_name, id_field=id_field)
    return manager.sync_with_diff(records, load_func, lastupdated=lastupdated, **kwargs)
