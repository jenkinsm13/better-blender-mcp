import threading
from blender_mcp.queue import ExecutionQueue


def test_submit_and_drain():
    """Submitting a task and draining returns the result."""
    q = ExecutionQueue()
    future = q.submit(lambda: 42)
    q.drain()
    assert future.result(timeout=1) == 42


def test_drain_preserves_order():
    """Multiple submissions drain in FIFO order."""
    q = ExecutionQueue()
    results = []
    q.submit(lambda: results.append(1))
    q.submit(lambda: results.append(2))
    q.submit(lambda: results.append(3))
    q.drain()
    assert results == [1, 2, 3]


def test_submit_from_background_thread():
    """Submit from bg thread, drain on main thread."""
    q = ExecutionQueue()
    future = None

    def bg():
        nonlocal future
        future = q.submit(lambda: threading.current_thread().name)

    t = threading.Thread(target=bg)
    t.start()
    t.join()
    q.drain()
    assert future.result(timeout=1) == threading.current_thread().name


def test_exception_propagates():
    """Exceptions in tasks propagate through the Future."""
    q = ExecutionQueue()
    future = q.submit(lambda: 1 / 0)
    q.drain()
    try:
        future.result(timeout=1)
        assert False, "Should have raised"
    except ZeroDivisionError:
        pass


def test_drain_empty_is_noop():
    """Draining an empty queue does nothing."""
    q = ExecutionQueue()
    q.drain()
