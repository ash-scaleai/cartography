"""
Event handler for event-driven incremental sync.

The EventHandler accepts CloudEvents, routes them through an EventRouter,
and triggers targeted re-syncs of only the affected cartography modules
scoped to the event's region.
"""
import logging
import time
from typing import Any
from typing import Callable
from typing import Optional

import neo4j

from cartography.events.models import CloudEvent
from cartography.events.router import EventRouter

logger = logging.getLogger(__name__)


class EventHandler:
    """
    Stateless handler that routes CloudEvents and triggers targeted re-syncs.

    The handler is designed to be callable from any context: a Lambda function,
    a queue consumer, or a CLI command. It does not manage its own state.

    Each targeted sync gets its own update_tag so that cleanup operations
    only affect the re-synced scope (module + region), not data from other
    regions or modules.

    Args:
        router: The EventRouter used to determine which modules to sync.
        sync_fn_provider: A callable that, given a module name string,
            returns the sync function to call (or None if not found).
            This decouples the handler from the RESOURCE_FUNCTIONS registry.
        neo4j_session: An active Neo4j session for database operations.
        common_job_parameters: Base parameters dict (will be copied and
            scoped per event).
        boto3_session_factory: Optional callable that creates a boto3 session
            for the given account_id. If None, targeted syncs that need
            AWS credentials will not be attempted.
    """

    def __init__(
        self,
        router: EventRouter,
        sync_fn_provider: Callable[[str], Optional[Callable[..., None]]],
        neo4j_session: neo4j.Session,
        common_job_parameters: dict[str, Any],
        boto3_session_factory: Optional[Callable[[str], Any]] = None,
    ) -> None:
        self._router = router
        self._sync_fn_provider = sync_fn_provider
        self._neo4j_session = neo4j_session
        self._common_job_parameters = common_job_parameters
        self._boto3_session_factory = boto3_session_factory

    def handle(self, event: CloudEvent) -> list[str]:
        """
        Route the event and trigger targeted re-syncs for matched modules.

        Each module sync is scoped to:
        - The event's region only (if the route's use_event_region is True)
        - Its own update_tag derived from the current time

        Args:
            event: The CloudEvent to handle.

        Returns:
            A list of module names that were successfully synced.

        Note:
            Modules that fail to sync are logged but do not prevent other
            matched modules from being synced.
        """
        module_names = self._router.route(event)
        if not module_names:
            logger.info(
                "No modules matched for event type '%s' from '%s'. Nothing to sync.",
                event.event_type,
                event.source,
            )
            return []

        logger.info(
            "Event '%s' (account=%s, region=%s) routed to modules: %s",
            event.event_type,
            event.account_id,
            event.region,
            module_names,
        )

        synced_modules: list[str] = []
        for module_name in module_names:
            sync_fn = self._sync_fn_provider(module_name)
            if sync_fn is None:
                logger.warning(
                    "No sync function found for module '%s'. Skipping.",
                    module_name,
                )
                continue

            # Each targeted sync gets its own update_tag so cleanup is scoped
            update_tag = int(time.time())
            scoped_params = dict(self._common_job_parameters)
            scoped_params["UPDATE_TAG"] = update_tag
            scoped_params["AWS_ID"] = event.account_id

            try:
                self._run_targeted_sync(
                    sync_fn=sync_fn,
                    module_name=module_name,
                    event=event,
                    update_tag=update_tag,
                    scoped_params=scoped_params,
                )
                synced_modules.append(module_name)
            except Exception:
                logger.exception(
                    "Failed to sync module '%s' for event '%s' (account=%s, region=%s)",
                    module_name,
                    event.event_type,
                    event.account_id,
                    event.region,
                )

        return synced_modules

    def _run_targeted_sync(
        self,
        sync_fn: Callable[..., None],
        module_name: str,
        event: CloudEvent,
        update_tag: int,
        scoped_params: dict[str, Any],
    ) -> None:
        """
        Execute a single module's sync function scoped to the event's region.
        """
        logger.info(
            "Running targeted sync for module '%s' in region '%s' "
            "(account=%s, update_tag=%d)",
            module_name,
            event.region,
            event.account_id,
            update_tag,
        )

        # Build kwargs matching the signature used by _sync_one_account
        # in cartography.intel.aws.__init__
        boto3_session = None
        if self._boto3_session_factory:
            boto3_session = self._boto3_session_factory(event.account_id)

        kwargs = {
            "neo4j_session": self._neo4j_session,
            "boto3_session": boto3_session,
            "regions": [event.region],
            "current_aws_account_id": event.account_id,
            "update_tag": update_tag,
            "common_job_parameters": scoped_params,
        }

        sync_fn(**kwargs)

        logger.info(
            "Completed targeted sync for module '%s' in region '%s' "
            "(account=%s, update_tag=%d)",
            module_name,
            event.region,
            event.account_id,
            update_tag,
        )
