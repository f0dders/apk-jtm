"""
Regression coverage for the JSON-upload/report_path scan branch, which used
to skip _merge_scorecard() entirely. MobSF's report_json export always
carries a bare "security_score": 0 (the real score only lives behind the
scorecard API), so uploading such a report used to render as 0/100 ->
"Critical Risk" regardless of the app's actual score.
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


def _extracted_score(events: list[dict]) -> object:
    for e in events:
        data = e["data"]
        if isinstance(data, str):
            data = json.loads(data)
        if data.get("stage") == "extracted":
            return data["score"]
    raise AssertionError("expected an 'extracted' progress event before the scan moved on")


async def test_json_upload_with_md5_fetches_real_scorecard(tmp_path, monkeypatch):
    monkeypatch.setattr(server, "load_dotenv", lambda *a, **kw: None)
    monkeypatch.setenv("MOBSF_API_KEY", "test-key")

    report_path = tmp_path / "scan1_report.json"
    report_path.write_text(json.dumps({
        "md5": "deadbeef",
        "security_score": 0,
        "app_name": "TestApp",
    }))

    import mobsf_client

    class FakeMobSFClient:
        def __init__(self, url, api_key):
            pass

        def _merge_scorecard(self, report, hash):
            report["security_score"] = 87
            return report

    monkeypatch.setattr(mobsf_client, "MobSFClient", FakeMobSFClient)

    events = await _run_and_drain(
        "scan1",
        apk_path=None,
        report_path=str(report_path),
        provider_override="ollama",
        model_override=None,
    )

    assert _extracted_score(events) == 87


async def test_json_upload_without_md5_shows_na_not_zero(tmp_path, monkeypatch):
    monkeypatch.setattr(server, "load_dotenv", lambda *a, **kw: None)
    monkeypatch.setenv("MOBSF_API_KEY", "test-key")

    report_path = tmp_path / "scan2_report.json"
    report_path.write_text(json.dumps({
        "security_score": 0,
        "app_name": "TestApp",
    }))

    events = await _run_and_drain(
        "scan2",
        apk_path=None,
        report_path=str(report_path),
        provider_override="ollama",
        model_override=None,
    )

    assert _extracted_score(events) == "N/A"
