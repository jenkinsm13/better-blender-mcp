"""Thread-safe execution queue for running tasks on Blender's main thread.

FastMCP receives HTTP requests on a background thread, but bpy operations
must run on the main thread. This queue bridges the gap:

1. Background thread calls submit(callable) -> gets a Future
2. Main thread calls drain() periodically (via bpy.app.timers)
3. Each queued callable runs on the main thread, result set on Future
"""

from __future__ import annotations

import queue
import concurrent.futures
from typing import Any, Callable


class ExecutionQueue:
    """FIFO queue that decouples submission (any thread) from execution (main thread)."""

    def __init__(self) -> None:
        self._queue: queue.Queue[
            tuple[Callable[[], Any], concurrent.futures.Future]
        ] = queue.Queue()

    def submit(self, fn: Callable[[], Any]) -> concurrent.futures.Future:
        """Submit a callable for main-thread execution. Returns a Future."""
        future: concurrent.futures.Future = concurrent.futures.Future()
        self._queue.put((fn, future))
        return future

    def drain(self) -> None:
        """Execute all pending tasks. Call this on the main thread."""
        while True:
            try:
                fn, future = self._queue.get_nowait()
            except queue.Empty:
                break
            try:
                result = fn()
                future.set_result(result)
            except Exception as e:
                future.set_exception(e)
