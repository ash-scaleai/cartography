"""
Pagination helpers that yield pages as generators.

These helpers allow callers to consume API results lazily so that cartography
can stream pages straight to Neo4j without buffering the full result set.
"""

import logging
from typing import Any
from typing import Callable
from typing import Dict
from typing import Generator
from typing import List
from typing import Optional

logger = logging.getLogger(__name__)


def paginated_get_aws(
    client_paginator: Any,
    result_key: str,
    **paginate_kwargs: Any,
) -> Generator[List[Dict[str, Any]], None, None]:
    """
    Yield pages from an AWS paginator one at a time.

    This wraps ``boto3``'s built-in paginator so that each page is yielded
    individually as a list of records, instead of being accumulated into one
    big list.

    :param client_paginator: A ``boto3`` paginator object, e.g.
        ``client.get_paginator('describe_instances')``.
    :param result_key: The top-level key in the API response that contains the
        list of records (e.g. ``'Reservations'``, ``'Buckets'``).
    :param paginate_kwargs: Extra keyword arguments forwarded to
        ``paginator.paginate()``.
    :yields: One ``List[Dict]`` per API page.
    """
    for page in client_paginator.paginate(**paginate_kwargs):
        records = page.get(result_key, [])
        if records:
            yield records


def paginated_get(
    fetch_page: Callable[..., Dict[str, Any]],
    result_key: str,
    token_request_key: str = "NextToken",
    token_response_key: str = "NextToken",
    **initial_kwargs: Any,
) -> Generator[List[Dict[str, Any]], None, None]:
    """
    Generic cursor/token-based paginator that yields one page of records at a time.

    Works with any API that uses a request-token / response-token pattern (which
    covers most AWS APIs that lack a boto3 paginator, as well as many non-AWS APIs).

    :param fetch_page: A callable that accepts keyword arguments and returns a
        dict-like API response.  Typically ``client.list_things``.
    :param result_key: The key in the response dict that holds the list of records.
    :param token_request_key: The kwarg name used to pass the pagination token to
        *fetch_page* (default ``"NextToken"``).
    :param token_response_key: The key in the response that contains the next
        pagination token (default ``"NextToken"``).
    :param initial_kwargs: Any extra keyword arguments for the first call to
        *fetch_page* (e.g. ``MaxResults=100``).
    :yields: One ``List[Dict]`` per API page.
    """
    kwargs: Dict[str, Any] = dict(initial_kwargs)
    page_number = 0

    while True:
        page_number += 1
        response = fetch_page(**kwargs)

        records = response.get(result_key, [])
        if records:
            yield records

        next_token: Optional[str] = response.get(token_response_key)
        if not next_token:
            break

        kwargs[token_request_key] = next_token


def rebatch(
    pages: Generator[List[Dict[str, Any]], None, None],
    batch_size: int,
) -> Generator[List[Dict[str, Any]], None, None]:
    """
    Re-chunk an iterable of variable-size pages into uniform batches.

    API pages are often not a consistent size.  This helper consumes them and
    yields lists of exactly *batch_size* records (the last batch may be
    smaller).

    :param pages: A generator that yields ``List[Dict]`` pages.
    :param batch_size: The desired number of records per output batch.
    :yields: Uniformly-sized ``List[Dict]`` batches.
    """
    if batch_size <= 0:
        raise ValueError(f"batch_size must be greater than 0, got {batch_size}")

    buffer: List[Dict[str, Any]] = []

    for page in pages:
        buffer.extend(page)
        while len(buffer) >= batch_size:
            yield buffer[:batch_size]
            buffer = buffer[batch_size:]

    if buffer:
        yield buffer
