from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
from threading import Lock
from typing import Callable, TypeVar

T = TypeVar("T")

_executor: ThreadPoolExecutor | None = None
_executor_lock = Lock()


def _get_executor() -> ThreadPoolExecutor:
    global _executor
    with _executor_lock:
        if _executor is None:
            _executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="momo-jobs")
        return _executor


def submit_background_job(fn: Callable[..., T], *args, **kwargs) -> Future[T]:
    return _get_executor().submit(fn, *args, **kwargs)


def shutdown_background_jobs(wait: bool = True) -> None:
    global _executor
    with _executor_lock:
        executor = _executor
        _executor = None
    if executor is not None:
        executor.shutdown(wait=wait, cancel_futures=False)
