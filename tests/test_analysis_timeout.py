"""
The AI-analysis stream used to have a single 120s per-chunk timeout that
killed the whole scan on any stall, even though the UI told users large
models could take 2-5 minutes to warm up. This replaces it with two tiers:
a generous first-chunk allowance (cold-start/model-load) and a much
shorter inter-chunk stall timeout once streaming has actually begun.

These tests drive run_scan with FIRST_CHUNK_TIMEOUT/INTER_CHUNK_TIMEOUT
monkeypatched down to fractions of a second so they run fast, and a fake
provider whose stream() is a slow generator instead of a real AI call.
"""
import asyncio
import json
import time

import server


async def _run_and_drain(scan_id: str, **kwargs) -> list[dict]:
    queue = asyncio.Queue()
    server._scan_queues[scan_id] = (queue, time.time())
    await server.run_scan(scan_id=scan_id, **kwargs)
    await asyncio.sleep(0)
    events = []
    while not queue.empty():
        events.append(queue.get_nowait())
    return events


def _error_message(events: list[dict]) -> str:
    for e in events:
        if e["event"] == "error":
            data = e["data"]
            if isinstance(data, str):
                data = json.loads(data)
            return data["message"]
    raise AssertionError("expected an error event")


class _SlowFirstChunkProvider:
    name = "fake"
    model = "fake-model"

    def stream(self, prompt):
        time.sleep(0.2)  # exceeds the monkeypatched FIRST_CHUNK_TIMEOUT
        yield "should never get here"


class _StallsMidStreamProvider:
    name = "fake"
    model = "fake-model"

    def stream(self, prompt):
        yield "first chunk arrives fine"
        time.sleep(0.2)  # exceeds the monkeypatched INTER_CHUNK_TIMEOUT
        yield "should never get here"


async def test_first_chunk_timeout_fires_before_any_content(tmp_path, monkeypatch):
    monkeypatch.setattr(server, "load_dotenv", lambda *a, **kw: None)
    monkeypatch.setattr(server, "FIRST_CHUNK_TIMEOUT", 0.05)
    monkeypatch.setattr(server, "INTER_CHUNK_TIMEOUT", 0.05)

    import providers
    monkeypatch.setattr(providers, "build_provider", lambda *a, **kw: _SlowFirstChunkProvider())

    report_path = tmp_path / "scan_first_report.json"
    report_path.write_text(json.dumps({"app_name": "TestApp"}))

    events = await _run_and_drain(
        "scan_first",
        apk_path=None,
        report_path=str(report_path),
        provider_override="ollama",
        model_override=None,
    )

    message = _error_message(events)
    assert "first response" in message


async def test_inter_chunk_timeout_fires_after_first_chunk_received(tmp_path, monkeypatch):
    monkeypatch.setattr(server, "load_dotenv", lambda *a, **kw: None)
    monkeypatch.setattr(server, "FIRST_CHUNK_TIMEOUT", 5)
    monkeypatch.setattr(server, "INTER_CHUNK_TIMEOUT", 0.05)

    import providers
    monkeypatch.setattr(providers, "build_provider", lambda *a, **kw: _StallsMidStreamProvider())

    report_path = tmp_path / "scan_mid_report.json"
    report_path.write_text(json.dumps({"app_name": "TestApp"}))

    events = await _run_and_drain(
        "scan_mid",
        apk_path=None,
        report_path=str(report_path),
        provider_override="ollama",
        model_override=None,
    )

    message = _error_message(events)
    assert "stalled mid-response" in message
