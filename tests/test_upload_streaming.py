"""
The APK/report-JSON upload handlers used to buffer the entire file in
memory (`await apk.read()`) before writing it back out again, with no size
limit anywhere. _stream_upload_to_file replaces that with chunked writes
and an enforced cap.
"""
import pytest
from fastapi import HTTPException

import server


class _FakeUpload:
    """Minimal async-read stand-in for FastAPI's UploadFile."""

    def __init__(self, data: bytes, chunk_size: int = 1024 * 1024):
        self._chunks = [data[i:i + chunk_size] for i in range(0, len(data), chunk_size)]
        self._chunks.append(b"")  # sentinel EOF, mirrors UploadFile.read() at EOF

    async def read(self, size=None):
        return self._chunks.pop(0) if self._chunks else b""


async def test_normal_upload_round_trips_to_disk(tmp_path):
    dest = tmp_path / "sample.apk"
    payload = b"dummy apk bytes" * 100

    await server._stream_upload_to_file(_FakeUpload(payload), dest, max_size=server.MAX_UPLOAD_SIZE)

    assert dest.read_bytes() == payload


async def test_oversized_upload_is_rejected_and_cleaned_up(tmp_path):
    dest = tmp_path / "huge.apk"
    payload = b"x" * 2048

    with pytest.raises(HTTPException) as exc_info:
        await server._stream_upload_to_file(_FakeUpload(payload, chunk_size=512), dest, max_size=1024)

    assert exc_info.value.status_code == 413
    assert not dest.exists()
