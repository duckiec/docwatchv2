import asyncio
from typing import List, Callable
from app.db import Incident

# List of async queues for SSE clients
_sse_queues: List[asyncio.Queue] = []

def register_sse_client() -> asyncio.Queue:
    q = asyncio.Queue()
    _sse_queues.append(q)
    return q

def unregister_sse_client(q: asyncio.Queue):
    if q in _sse_queues:
        _sse_queues.remove(q)

def publish_incident(incident: Incident):
    """
    Publish an incident to all connected SSE clients.
    """
    for q in _sse_queues:
        # Don't await on put, use put_nowait to not block
        try:
            q.put_nowait(incident)
        except asyncio.QueueFull:
            pass
