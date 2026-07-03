"""
quark_client._parse() reduces Quark-Engine's raw output (every one of
~277 rules it checked, matched or not, each with its own 0-100% confidence)
down to just the behaviours genuinely matched — verified against a real
scan of F-Droid's APK, which showed all 277 rules present in `crimes`
regardless of whether they actually fired.
"""
import subprocess

import quark_client


def _raw(crimes):
    return {
        "md5": "abc123", "apk_filename": "test.apk", "size_bytes": 1000,
        "threat_level": "Moderate Risk", "total_score": 5,
        "crimes": crimes,
    }


def test_parse_filters_out_low_confidence_non_matches():
    """Quark includes every checked rule in 'crimes', even 0% matches —
    these must not be treated as genuine findings."""
    raw = _raw([
        {"crime": "Use reflection", "label": ["reflection"], "confidence": "20%", "weight": 0.1},
        {"crime": "Send SMS silently", "label": ["sms"], "confidence": "100%", "weight": 2.5},
    ])
    result = quark_client._parse(raw)
    assert result["available"] is True
    assert result["matched_count"] == 1
    assert result["top_crimes"][0]["crime"] == "Send SMS silently"


def test_parse_sorts_matched_crimes_by_weight_descending():
    raw = _raw([
        {"crime": "Low weight match", "label": [], "confidence": "80%", "weight": 0.5},
        {"crime": "High weight match", "label": [], "confidence": "100%", "weight": 3.0},
    ])
    result = quark_client._parse(raw)
    assert [c["crime"] for c in result["top_crimes"]] == ["High weight match", "Low weight match"]


def test_parse_caps_at_max_crimes():
    raw = _raw([
        {"crime": f"Match {i}", "label": [], "confidence": "100%", "weight": i}
        for i in range(30)
    ])
    result = quark_client._parse(raw)
    assert result["matched_count"] == 30  # true count preserved
    assert len(result["top_crimes"]) == quark_client._MAX_CRIMES


def test_parse_passes_through_threat_level_and_total_score():
    raw = _raw([])
    result = quark_client._parse(raw)
    assert result["threat_level"] == "Moderate Risk"
    assert result["total_score"] == 5
    assert result["matched_count"] == 0


def test_confidence_pct_parses_percentage_strings():
    assert quark_client._confidence_pct("80%") == 80
    assert quark_client._confidence_pct("0%") == 0
    assert quark_client._confidence_pct("not-a-percent") == 0


def test_run_quark_missing_rules_dir_returns_unavailable(monkeypatch, tmp_path):
    monkeypatch.setattr(quark_client, "RULES_DIR", tmp_path / "does-not-exist")
    result = quark_client.run_quark("/fake/path.apk")
    assert result == {"available": False, "reason": "Quark-Engine rules not found — run: freshquark"}


def test_run_quark_missing_binary_returns_unavailable_not_an_exception(monkeypatch, tmp_path):
    """If quark isn't installed, callers must get {"available": False, ...},
    never an exception — Quark is always optional/best-effort."""
    rules_dir = tmp_path / "rules"
    rules_dir.mkdir()
    monkeypatch.setattr(quark_client, "RULES_DIR", rules_dir)

    def _raise(*a, **kw):
        raise FileNotFoundError()

    monkeypatch.setattr(subprocess, "run", _raise)
    result = quark_client.run_quark("/fake/path.apk")
    assert result == {"available": False, "reason": "Quark-Engine not installed — run: pip install quark-engine && freshquark"}


def test_run_quark_timeout_returns_unavailable(monkeypatch, tmp_path):
    rules_dir = tmp_path / "rules"
    rules_dir.mkdir()
    monkeypatch.setattr(quark_client, "RULES_DIR", rules_dir)

    def _raise(*a, **kw):
        raise subprocess.TimeoutExpired(cmd="quark", timeout=180)

    monkeypatch.setattr(subprocess, "run", _raise)
    result = quark_client.run_quark("/fake/path.apk")
    assert result == {"available": False, "reason": "Quark-Engine timed out"}
