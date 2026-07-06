"""
_scan_queues used to have no equivalent of _sweep_stale_uploads: a queue was
only ever popped inside event_generator() once a client actually opened the
SSE stream and consumed a complete/error event. A client that starts a scan
and disconnects before opening the stream leaked its queue for the life of
the process.
"""
import asyncio
import time

import server


def test_sweep_removes_only_stale_entries():
    fresh_id = "fresh-scan"
    stale_id = "stale-scan"
    server._scan_queues[fresh_id] = (asyncio.Queue(), time.time())
    server._scan_queues[stale_id] = (asyncio.Queue(), time.time() - 7200)

    try:
        removed = server._sweep_stale_scan_queues(max_age_seconds=3600)

        assert removed == 1
        assert stale_id not in server._scan_queues
        assert fresh_id in server._scan_queues
    finally:
        server._scan_queues.pop(fresh_id, None)
        server._scan_queues.pop(stale_id, None)
