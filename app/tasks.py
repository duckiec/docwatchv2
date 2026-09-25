import asyncio
from typing import Coroutine, Set

from app.config import logger

# Set to store references to background tasks to prevent garbage collection
_bg_tasks: Set[asyncio.Task] = set()

def create_background_task(coro: Coroutine, name: str = None) -> asyncio.Task:
    """
    Creates an asyncio task, adding it to a global set to prevent
    the event loop from prematurely garbage collecting it.
    """
    task = asyncio.create_task(coro, name=name)
    _bg_tasks.add(task)

    # Callback to remove the task from the set when it's done
    def _on_completion(t: asyncio.Task):
        try:
            if not t.cancelled():
                # check if there was an exception
                exc = t.exception()
                if exc:
                    logger.error(f"Background task {name or t.get_name()} failed: {exc}")
        except Exception as e:
            logger.error(f"Error checking task completion: {e}")
        finally:
            _bg_tasks.discard(t)

    task.add_done_callback(_on_completion)
    return task

def cancel_all_tasks():
    """Cancels all active background tasks."""
    for task in list(_bg_tasks):
        task.cancel()
