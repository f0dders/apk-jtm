"""
apkid_client._parse() flattens APKiD's raw JSON into the risk-flag summary
the rest of the app relies on. APKiD 2.1.x changed 'files' from a dict keyed
by filename to a list of {filename, results} objects, which broke the parser
in production (commit 4adffea) — several tests here exist specifically to
stop that regression from coming back in either shape.
"""
import subprocess

import apkid_client


def _raw_dict_shape(**findings):
    """Older APKiD output: 'files' is a dict keyed by filename."""
    return {"apkid_version": "2.0.0", "files": {"classes.dex": findings}}


def _raw_list_shape(**findings):
    """APKiD 2.1.x output: 'files' is a list of {filename, results}."""
    return {
        "apkid_version": "2.1.3",
        "files": [{"filename": "classes.dex", "results": findings}],
    }


def test_parse_handles_dict_shaped_files():
    result = apkid_client._parse(_raw_dict_shape(packer=["ASProtect"]))
    assert result["available"] is True
    assert result["packers"] == ["ASProtect"]


def test_parse_handles_list_shaped_files():
    """Regression test for the 'list' object has no attribute 'items' bug."""
    result = apkid_client._parse(_raw_list_shape(packer=["ASProtect"]))
    assert result["available"] is True
    assert result["packers"] == ["ASProtect"]


def test_parse_merges_findings_across_multiple_dex_files():
    raw = {
        "files": [
            {"filename": "classes.dex", "results": {"packer": ["A"]}},
            {"filename": "classes2.dex", "results": {"packer": ["B"], "anti_vm": ["Some anti-VM check"]}},
        ]
    }
    result = apkid_client._parse(raw)
    assert result["packers"] == ["A", "B"]
    assert result["has_anti_vm"] is True


def test_known_malware_packer_flagged():
    result = apkid_client._parse(_raw_list_shape(packer=["Bangcle/SecShell"]))
    assert result["known_malware_packer"] is True


def test_unknown_packer_not_flagged_as_malware():
    result = apkid_client._parse(_raw_list_shape(packer=["Some Legit Packer"]))
    assert result["known_malware_packer"] is False


def test_suspicious_obfuscator_flagged():
    result = apkid_client._parse(_raw_list_shape(obfuscator=["DexGuard"]))
    assert result["suspicious_obfuscator"] is True


def test_repackaged_detected_from_dex2jar_compiler():
    result = apkid_client._parse(_raw_list_shape(compiler=["dex2jar"]))
    assert result["repackaged"] is True


def test_no_findings_returns_all_clear():
    result = apkid_client._parse(_raw_list_shape())
    assert result["has_packer"] is False
    assert result["has_anti_vm"] is False
    assert result["known_malware_packer"] is False


def test_run_apkid_missing_binary_returns_unavailable_not_an_exception(monkeypatch):
    """If apkid isn't installed, callers must get {"available": False, ...},
    never an exception — APKiD is always optional/best-effort."""
    def _raise(*a, **kw):
        raise FileNotFoundError()

    monkeypatch.setattr(subprocess, "run", _raise)
    result = apkid_client.run_apkid("/fake/path.apk")
    assert result == {"available": False, "reason": "APKiD not installed — run: pip install apkid"}


def test_run_apkid_timeout_returns_unavailable(monkeypatch):
    def _raise(*a, **kw):
        raise subprocess.TimeoutExpired(cmd="apkid", timeout=30)

    monkeypatch.setattr(subprocess, "run", _raise)
    result = apkid_client.run_apkid("/fake/path.apk")
    assert result == {"available": False, "reason": "APKiD timed out"}
