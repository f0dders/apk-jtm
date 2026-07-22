"""
OpenRouterProvider's 429-retry handler used to yield its diagnostic text
("Rate limited... retrying in Ns...") directly into the same stream as real
AI content. That text got appended to full_report_raw and could land
between the AI's content and the VERDICT:/SUMMARY: tag lines the extraction
regex expects as the literal last two lines — corrupting the persisted
report. providers.RETRY_NOTICE_PREFIX now tags such text so server.py can
route it to a live "retry" progress event instead of the saved report body.
"""
import asyncio
import json
import time

import server
from providers import RETRY_NOTICE_PREFIX


async def _run_and_drain(scan_id: str, **kwargs) -> list[dict]:
    queue = asyncio.Queue()
    server._scan_queues[scan_id] = (queue, time.time())
    await server.run_scan(scan_id=scan_id, **kwargs)
    await asyncio.sleep(0)
    events = []
    while not queue.empty():
        events.append(queue.get_nowait())
    return events


def _decode(data):
    return json.loads(data) if isinstance(data, str) else data


class _RetryThenSucceedsProvider:
    name = "fake"
    model = "fake-model"

    def stream(self, prompt, system=None):
        yield f"{RETRY_NOTICE_PREFIX}⏳ Rate limited by upstream provider — retrying in 1s (attempt 1/3)…"
        yield "Here is the analysis.\n"
        yield "VERDICT: LOW\n"
        yield "SUMMARY: Looks fine.\n"


async def test_retry_notice_excluded_from_saved_report_and_tags_still_parse(tmp_path, monkeypatch):
    monkeypatch.setattr(server, "load_dotenv", lambda *a, **kw: None)
    # This provider succeeds all the way through, so run_scan reaches the
    # report-saving step — keep its output out of the real reports dir.
    monkeypatch.setattr(server, "REPORTS_DIR", tmp_path / "reports")
    (tmp_path / "reports").mkdir()

    import providers
    monkeypatch.setattr(providers, "build_provider", lambda *a, **kw: _RetryThenSucceedsProvider())

    report_path = tmp_path / "scan_retry_report.json"
    report_path.write_text(json.dumps({"app_name": "TestApp"}))

    events = await _run_and_drain(
        "scan_retry",
        apk_path=None,
        report_path=str(report_path),
        provider_override="ollama",
        model_override=None,
    )

    retry_events = [
        e for e in events
        if e["event"] == "progress" and _decode(e["data"]).get("stage") == "retry"
    ]
    assert len(retry_events) == 1
    assert "Rate limited" in _decode(retry_events[0]["data"])["message"]

    analysis_chunks = [e["data"] for e in events if e["event"] == "analysis"]
    full_text = "".join(analysis_chunks)
    assert "Rate limited" not in full_text
    assert "VERDICT: LOW" in full_text
    assert "SUMMARY: Looks fine." in full_text
