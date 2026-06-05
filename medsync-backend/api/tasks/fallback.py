"""
Synchronous task execution wrapper.

Celery has been removed; all background tasks run synchronously.
execute_task_sync_or_async is kept as the call-site API so no other code changes.
can_use_celery always returns False (no broker).
"""
import logging
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


def can_use_celery() -> bool:
    """Always False — Celery is not used in this deployment."""
    return False


def execute_task_sync_or_async(
    task_func: Callable,
    *args: Any,
    timeout: Optional[int] = None,
    **kwargs: Any,
) -> Any:
    """
    Execute task synchronously.

    The timeout parameter is accepted for call-site compatibility but not enforced;
    all tasks run synchronously and should complete quickly.
    """
    kwargs.pop("_retry_count", None)
    task_name = getattr(task_func, '__name__', str(task_func))
    logger.info("Executing %s synchronously", task_name)
    return task_func(*args, **kwargs)
