"""Shared parallel execution helpers."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
import logging
from typing import Any, Callable, Optional, Sequence, TypeVar

from .errors import TinyDataParameterError, TinyDataRateLimitError
from .progress import _create_progress_tracker


ResultT = TypeVar("ResultT")


def _normalize_max_workers(max_workers: Optional[int], *, batch_count: int) -> int:
    if max_workers is None:
        return 1
    workers = int(max_workers)
    if workers < 1:
        raise TinyDataParameterError("max_workers must be >= 1.")
    if batch_count <= 0:
        return workers
    return min(workers, batch_count)


def _reduced_max_workers(worker_count: int) -> int:
    if worker_count <= 1:
        return 1
    reduced = max(1, worker_count // 2)
    if reduced == worker_count:
        reduced = worker_count - 1
    return reduced


def run_parallel_code_queries(
    codes: Sequence[str],
    *,
    fetch_one: Callable[[str], ResultT],
    max_workers: Optional[int] = None,
    progress: Optional[bool] = None,
    description: str,
    logger: Optional[logging.Logger] = None,
    rate_limit_scope: Optional[str] = None,
) -> list[ResultT]:
    worker_count = _normalize_max_workers(max_workers, batch_count=len(codes))
    results: list[Optional[ResultT]] = [None] * len(codes)
    pending_codes = list(enumerate(codes))
    current_workers = worker_count
    use_logger = logger or logging.getLogger(__name__)
    scope = rate_limit_scope or description

    with _create_progress_tracker(
        enabled=progress,
        total=len(codes),
        description=description,
    ) as progress_tracker:
        while pending_codes:
            if current_workers > 1 and len(pending_codes) > 1:
                rate_limited: list[tuple[int, str]] = []
                with ThreadPoolExecutor(max_workers=current_workers) as executor:
                    future_map = {executor.submit(fetch_one, code): (idx, code) for idx, code in pending_codes}
                    for future in as_completed(future_map):
                        idx, code = future_map[future]
                        try:
                            results[idx] = future.result()
                            progress_tracker.update()
                        except TinyDataRateLimitError:
                            rate_limited.append((idx, code))
                        except Exception:
                            raise

                if rate_limited:
                    next_workers = _reduced_max_workers(current_workers)
                    if next_workers >= current_workers:
                        raise TinyDataRateLimitError("Tinysoft OPI HTTP 429: unable to reduce code-query concurrency further.")
                    use_logger.warning(
                        "Tinysoft OPI returned HTTP 429 during %s; retrying %s failed code request(s) with max_workers=%s.",
                        scope,
                        len(rate_limited),
                        next_workers,
                    )
                    pending_codes = rate_limited
                    current_workers = next_workers
                    continue

                break

            for idx, code in pending_codes:
                results[idx] = fetch_one(code)
                progress_tracker.update()
            break

    return [result for result in results if result is not None]