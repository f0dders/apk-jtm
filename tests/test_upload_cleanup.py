"""
Regression coverage for the upload leak fixed in commit 917fd15: every
uploaded APK/JSON file used to be left behind in uploads/ forever, since
nothing ever deleted it after the scan finished — including on failure.
uploads/ had silently grown to 482MB before this was caught.

These tests drive server.run_scan() directly down its fastest error paths
(no real MobSF/AI calls) and assert the file is gone afterward regardless
of *why* the scan stopped.
"""
import asyncio
import os
import time

import server


async def _run_and_drain(scan_id: str, **kwargs) -> list[dict]:
    """Call run_scan and give the event loop one tick so its
    call_soon_threadsafe-scheduled queue events are actually delivered,
    then return every event that was sent, in order."""
    queue = asyncio.Queue()
    server._scan_queues[scan_id] = queue
    await server.run_scan(scan_id=scan_id, **kwargs)
    await asyncio.sleep(0)
    events = []
    while not queue.empty():
        events.append(queue.get_nowait())
    return events


async def test_apk_deleted_when_mobsf_key_missing(tmp_path, monkeypatch):
    """Original bug scenario: an APK was uploaded, but the scan can't reach
    MobSF because no API key is configured. The file must still be deleted."""
    monkeypatch.setattr(server, "load_dotenv", lambda *a, **kw: None)
    monkeypatch.delenv("MOBSF_API_KEY", raising=False)

    apk_path = tmp_path / "scan1_sample.apk"
    apk_path.write_bytes(b"dummy apk bytes")

    events = await _run_and_drain(
        "scan1",
        apk_path=str(apk_path),
        report_path=None,
        provider_override="ollama",
        model_override=None,
    )

    assert not apk_path.exists(), "uploaded APK should be deleted after the scan exits"
    errors = [e for e in events if e["event"] == "error"]
    assert len(errors) == 1
    assert "MOBSF_API_KEY" in errors[0]["data"]


async def test_apk_deleted_when_provider_build_fails_before_any_file_read(tmp_path, monkeypatch):
    """Cleanup must also happen when the very first step (building the AI
    provider) fails — before run_scan ever touches the uploaded file."""
    monkeypatch.setattr(server, "load_dotenv", lambda *a, **kw: None)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    apk_path = tmp_path / "scan2_sample.apk"
    apk_path.write_bytes(b"dummy apk bytes")

    events = await _run_and_drain(
        "scan2",
        apk_path=str(apk_path),
        report_path=None,
        provider_override="claude",
        model_override=None,
    )

    assert not apk_path.exists()
    errors = [e for e in events if e["event"] == "error"]
    assert len(errors) == 1
    assert "ANTHROPIC_API_KEY" in errors[0]["data"]


async def test_json_report_deleted_alongside_apk(tmp_path, monkeypatch):
    """Loading an existing MobSF JSON report (no APK involved) still writes
    a temp file to uploads/ — it must be cleaned up too."""
    monkeypatch.setattr(server, "load_dotenv", lambda *a, **kw: None)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    report_path = tmp_path / "scan3_report.json"
    report_path.write_text("{}")

    events = await _run_and_drain(
        "scan3",
        apk_path=None,
        report_path=str(report_path),
        provider_override="claude",
        model_override=None,
    )

    assert not report_path.exists()
    errors = [e for e in events if e["event"] == "error"]
    assert len(errors) == 1


def test_sweep_stale_uploads_removes_only_old_files(tmp_path):
    """Safety net for crashes: a file orphaned by a hard process kill (so
    run_scan's finally block never ran) should be swept up on next startup
    once it's older than the cutoff — but untouched while still fresh."""
    old_file = tmp_path / "orphaned-from-a-crash.apk"
    new_file = tmp_path / "just-uploaded.apk"
    old_file.write_bytes(b"x")
    new_file.write_bytes(b"x")

    two_hours_ago = time.time() - 7200
    os.utime(old_file, (two_hours_ago, two_hours_ago))

    removed = server._sweep_stale_uploads(directory=tmp_path, max_age_seconds=3600)

    assert removed == 1
    assert not old_file.exists()
    assert new_file.exists()
