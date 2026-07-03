"""
Version comparison diffs two saved reports of the same app using only data
already captured in their .meta.json sidecars — no re-scanning involved.
Older reports (saved before the detailed *_list fields were added) must
degrade gracefully rather than showing a false 'everything was removed' diff.
"""
import server


def test_diff_list_added_and_removed():
    a = {"perms_list": ["CAMERA", "RECORD_AUDIO"]}
    b = {"perms_list": ["CAMERA", "READ_SMS"]}
    result = server._diff_list(a, b, "perms_list")
    assert result["available"] is True
    assert result["added"] == ["READ_SMS"]
    assert result["removed"] == ["RECORD_AUDIO"]


def test_diff_list_no_changes():
    a = {"perms_list": ["CAMERA"]}
    b = {"perms_list": ["CAMERA"]}
    result = server._diff_list(a, b, "perms_list")
    assert result == {"available": True, "added": [], "removed": []}


def test_diff_list_unavailable_when_key_missing_from_either_side():
    """A report saved before this feature existed has no perms_list key at
    all — that must be reported as 'can't compare', not as an empty list
    (which would look like every permission was removed)."""
    old_report = {}  # predates the *_list fields
    new_report = {"perms_list": ["CAMERA"]}
    result = server._diff_list(old_report, new_report, "perms_list")
    assert result == {"available": False, "added": [], "removed": []}


def test_diff_apkid_flags_changes_in_plain_english():
    a = {"apkid_available": True, "apkid_packer": False, "apkid_anti_vm": False, "apkid_malware_packer": False}
    b = {"apkid_available": True, "apkid_packer": True, "apkid_anti_vm": False, "apkid_malware_packer": False}
    result = server._diff_apkid(a, b)
    assert result["available"] is True
    assert result["changes"] == ["Packer/obfuscation now detected"]


def test_diff_apkid_flag_removed():
    a = {"apkid_available": True, "apkid_packer": True}
    b = {"apkid_available": True, "apkid_packer": False}
    result = server._diff_apkid(a, b)
    assert result["changes"] == ["Packer/obfuscation no longer detected"]


def test_diff_apkid_unavailable_if_either_side_lacks_apkid():
    a = {"apkid_available": False}
    b = {"apkid_available": True, "apkid_packer": True}
    result = server._diff_apkid(a, b)
    assert result == {"available": False, "changes": []}


def test_diff_quark_flags_threat_level_change():
    a = {"quark_available": True, "quark_threat_level": "Low Risk"}
    b = {"quark_available": True, "quark_threat_level": "High Risk"}
    result = server._diff_quark(a, b)
    assert result == {
        "available": True, "threat_level_changed": True,
        "older_level": "Low Risk", "newer_level": "High Risk",
    }


def test_diff_quark_no_change():
    a = {"quark_available": True, "quark_threat_level": "Low Risk"}
    b = {"quark_available": True, "quark_threat_level": "Low Risk"}
    result = server._diff_quark(a, b)
    assert result["threat_level_changed"] is False


def test_diff_quark_unavailable_if_either_side_lacks_quark():
    a = {"quark_available": False}
    b = {"quark_available": True, "quark_threat_level": "High Risk"}
    result = server._diff_quark(a, b)
    assert result["available"] is False


def test_compare_summary_pulls_expected_fields():
    meta = {
        "name": "report_x.html", "app_name": "Aurora Store", "version": "4.4.2",
        "timestamp": "20260610_170201", "score": 55,
        "ai_verdict_label": "✓ Safe to use", "ai_verdict_cls": "safe",
    }
    summary = server._compare_summary(meta)
    assert summary["app_name"] == "Aurora Store"
    assert summary["score"] == 55


def test_load_meta_rejects_path_traversal():
    import fastapi
    try:
        server._load_meta("../../etc/passwd")
        assert False, "should have raised"
    except fastapi.HTTPException as e:
        assert e.status_code == 400


async def test_compare_reports_orders_oldest_first_regardless_of_argument_order(tmp_path, monkeypatch):
    """Callers might pass the newer report as 'a' and the older as 'b' —
    the response must always read as 'older -> newer', not 'a -> b'."""
    monkeypatch.setattr(server, "REPORTS_DIR", tmp_path)

    older = {"app_name": "Aurora Store", "timestamp": "20260601_000000", "score": 50, "perms_list": ["CAMERA"]}
    newer = {"app_name": "Aurora Store", "timestamp": "20260701_000000", "score": 60, "perms_list": ["CAMERA", "READ_SMS"]}
    (tmp_path / "report_old.meta.json").write_text(__import__("json").dumps(older))
    (tmp_path / "report_new.meta.json").write_text(__import__("json").dumps(newer))

    # Pass the newer report as 'a' and older as 'b' — deliberately reversed.
    result = await server.compare_reports(a="report_new.html", b="report_old.html")

    assert result["older"]["timestamp"] == "20260601_000000"
    assert result["newer"]["timestamp"] == "20260701_000000"
    assert result["score_delta"] == 10
    assert result["sections"]["permissions"]["added"] == ["READ_SMS"]
