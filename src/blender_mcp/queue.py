"""Thread-safe execution queue for running tasks on Blender's main thread.

FastMCP receives HTTP requests on a background thread, but bpy operations
must run on the main thread. This queue bridges the gap:

1. Background thread calls submit(callable) -> gets a Future
2. Main thread calls drain() periodically (via bpy.app.timers)
3. Each queued callable runs on the main thread, result set on Future

For tools that require a GPU draw context (e.g. viewport capture), a tool
may return a PendingResult instead of a plain dict.  drain() detects this
and hands the Future to the setup function so the draw-handler can resolve
it later — without ever blocking the main thread.
"""

from __future__ import annotations

import queue
import concurrent.futures
from typing import Any, Callable


class PendingResult:
    """Sentinel returned by tools that complete asynchronously via a draw handler.

    setup_fn(future) is called by drain() on the main thread immediately after
    the tool returns.  It should register a bpy draw handler that will call
    future.set_result() (or future.set_exception()) when it fires, then remove
    itself.  The HTTP-thread is already blocking on future.result() so it wakes
    up automatically once the draw handler sets the value.
    """

    def __init__(self, setup_fn: Callable[[concurrent.futures.Future], None]) -> None:
        self.setup_fn = setup_fn


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
                if isinstance(result, PendingResult):
                    # Tool needs a GPU draw context — hand future to setup_fn.
                    # The draw handler registered by setup_fn will resolve it.
                    result.setup_fn(future)
                else:
                    future.set_result(result)
            except Exception as e:
                future.set_exception(e)
