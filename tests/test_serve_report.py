"""
serve_report (GET /reports/{filename}) used to be the only report-serving
endpoint without a filename validation guard — delete_report and
rerun_report both already reject ".."/"/" in the filename, but serve_report
built REPORTS_DIR / filename straight from the path parameter.
"""
import pytest
from fastapi import HTTPException

import server


async def test_serve_report_rejects_path_traversal():
    with pytest.raises(HTTPException) as exc_info:
        await server.serve_report("../secrets.txt")
    assert exc_info.value.status_code == 400


async def test_serve_report_rejects_embedded_slash():
    with pytest.raises(HTTPException) as exc_info:
        await server.serve_report("sub/dir.html")
    assert exc_info.value.status_code == 400


async def test_serve_report_still_serves_valid_filename(tmp_path, monkeypatch):
    monkeypatch.setattr(server, "REPORTS_DIR", tmp_path)
    report = tmp_path / "report_abc.html"
    report.write_text("<html></html>")

    response = await server.serve_report("report_abc.html")
    assert response.status_code == 200
