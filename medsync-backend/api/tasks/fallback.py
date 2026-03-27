"""
Celery fallback to synchronous execution when task queue is unavailable.

Provides utilities to gracefully handle Celery broker unavailability by falling
back to synchronous task execution.
"""

import logging
from typing import Any, Callable, Dict, Optional

try:
    from celery import current_app as celery_app
    from celery.exceptions import OperationalError, CeleryError
except ImportError:
    celery_app = None
    OperationalError = Exception
    CeleryError = Exception

logger = logging.getLogger(__name__)


def can_use_celery() -> bool:
    """
    Check if Celery is available and the broker is accessible.
    
    Attempts to connect to the broker to verify it's available. If connection
    fails, returns False to trigger fallback to synchronous execution.
    
    Returns:
        bool: True if Celery broker is accessible, False otherwise
    """
    if not celery_app:
        logger.warning("Celery not available, falling back to synchronous execution")
        return False
    
    try:
        # Attempt to connect to the broker to verify availability
        # This uses a lightweight ping operation
        with celery_app.connection() as conn:
            conn.connect()
            logger.debug("Celery broker connection successful")
            return True
    
    except (OperationalError, CeleryError, Exception) as exc:
        logger.warning(
            f"Celery broker unavailable: {type(exc).__name__}: {str(exc)}. "
            "Falling back to synchronous task execution."
        )
        return False


def execute_task_sync_or_async(
    task_func: Callable,
    *args: Any,
    timeout: Optional[int] = None,
    **kwargs: Any
) -> Any:
    """
    Execute a task asynchronously if possible, otherwise fall back to synchronous execution.
    
    If Celery is available and the broker is accessible, the task is executed
    asynchronously via apply_async. If the broker is unavailable, the task is
    executed synchronously (blocking).
    
    Args:
        task_func: The Celery task function to execute
        *args: Positional arguments to pass to the task
        timeout: Optional timeout in seconds for async task execution
        **kwargs: Keyword arguments to pass to the task
    
    Returns:
        Any: The result of the task execution (dict or other return value)
        
    Examples:
        >>> from api.tasks import export_patient_pdf_task
        >>> result = execute_task_sync_or_async(
        ...     export_patient_pdf_task,
        ...     patient_id='123-456',
        ...     format_type='summary',
        ...     timeout=30
        ... )
    """
    retry_count = kwargs.pop("_retry_count", 0)
    max_retries = 1
    
    # Get task name safely
    task_name = getattr(task_func, 'name', str(task_func))
    
    if can_use_celery():
        try:
            logger.info(
                f"Executing task {task_name} asynchronously with args: {args}, kwargs: {kwargs}"
            )
            
            # Build apply_async kwargs
            async_kwargs = {}
            if timeout:
                async_kwargs["timeout"] = timeout
            
            # Execute asynchronously and wait for result
            result = task_func.apply_async(args=args, **async_kwargs)
            
            # Get the result (blocking until completion or timeout)
            try:
                return result.get(timeout=timeout or 300)  # Default 5 min timeout
            except Exception as exc:
                logger.error(
                    f"Error getting async task result for {task_name}: {exc}. "
                    "Attempting synchronous fallback."
                )
                # Fall through to sync execution
                return task_func(*args, **kwargs)
        
        except Exception as exc:
            logger.warning(
                f"Async task execution failed for {task_name}: {type(exc).__name__}: {exc}. "
                "Falling back to synchronous execution."
            )
            # Fall through to sync execution
            return task_func(*args, **kwargs)
    
    else:
        # Celery not available, execute synchronously
        logger.info(
            f"Executing task {task_name} synchronously (Celery unavailable) "
            f"with args: {args}, kwargs: {kwargs}"
        )
        return task_func(*args, **kwargs)
