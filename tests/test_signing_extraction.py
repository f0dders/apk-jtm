"""
Unsigned and debug-signed APKs used to reach the AI with no positive signal at
all — only the absence of a finding, which a model cannot reason about. These
guard the explicit signing facts, including the MobSF shapes that vary by
version.
"""
import extractor

SIGNED_INFO = (
    "Binary is signed\n"
    "v1 signature: True\n"
    "v2 signature: True\n"
    "v3 signature: False\n"
    "X.509 Subject: CN=Example Corp, O=Example, C=GB\n"
    "Signature Algorithm: rsassa_pkcs1v15\n"
    "Issuer: CN=Example Corp, O=Example, C=GB\n"
)


def _signing(report):
    return extractor.extract(report)["signing"]


def test_absent_certificate_analysis_degrades_gracefully():
    result = _signing({})
    assert result["available"] is False
    assert "reason" in result


def test_signed_release_build():
    result = _signing({"certificate_analysis": {"certificate_info": SIGNED_INFO}})
    assert result["available"] is True
    assert result["is_signed"] is True
    assert result["signature_versions"] == ["v1", "v2"]
    assert result["subject"] == "CN=Example Corp, O=Example, C=GB"
    assert result["algorithm"] == "rsassa_pkcs1v15"


def test_self_signed_is_detected_from_matching_subject_and_issuer():
    assert _signing({"certificate_analysis": {"certificate_info": SIGNED_INFO}})["is_self_signed"]


def test_unsigned_binary_is_flagged():
    result = _signing({"certificate_analysis": {"certificate_info": "Binary is not signed\n"}})
    assert result["is_signed"] is False


def test_debug_certificate_detected_from_list_style_findings():
    """Newer MobSF emits findings as [severity, title, description] lists."""
    result = _signing({"certificate_analysis": {
        "certificate_info": SIGNED_INFO,
        "certificate_findings": [
            ["warning", "Application signed with a debug certificate",
             "The application is signed with a debug certificate."],
        ],
    }})
    assert result["is_debug_signed"] is True


def test_debug_certificate_detected_from_dict_style_findings():
    """Older MobSF emits findings as dicts."""
    result = _signing({"certificate_analysis": {
        "certificate_info": SIGNED_INFO,
        "certificate_findings": [
            {"severity": "warning", "title": "Application signed with a debug certificate"},
        ],
    }})
    assert result["is_debug_signed"] is True


def test_debug_key_detected_from_certificate_info_alone():
    result = _signing({"certificate_analysis": {
        "certificate_info": "Binary is signed\nX.509 Subject: CN=Android Debug, O=AndroidDebugKey\n",
    }})
    assert result["is_debug_signed"] is True


def test_malformed_certificate_analysis_does_not_raise():
    for shape in ([], "a string", 42, {"certificate_info": None}):
        assert isinstance(_signing({"certificate_analysis": shape}), dict)
