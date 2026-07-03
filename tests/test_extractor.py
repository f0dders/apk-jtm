"""
extractor.py turns a raw MobSF JSON report into the structured dict the AI
prompt is built from. MobSF's own output shape has shifted across versions
(fields sometimes missing, sometimes the wrong type), so these tests focus
on that robustness as much as on the "happy path" extraction logic.
"""
import extractor


def test_extract_handles_empty_report():
    """A near-empty report shouldn't crash — MobSF fields are often absent
    entirely for very small or unusual APKs."""
    result = extractor.extract({})
    assert result["app"]["name"] == "Unknown"
    assert result["dangerous_permissions"] == []
    assert result["security_score"] == "N/A"


def test_dangerous_permission_detected_by_known_name():
    report = {
        "permissions": {
            "android.permission.CAMERA": {"description": "Uses camera", "status": "normal"},
            "android.permission.INTERNET": {"description": "Full network access", "status": "normal"},
        }
    }
    perms = extractor.extract(report)["dangerous_permissions"]
    names = [p["name"] for p in perms]
    assert "android.permission.CAMERA" in names
    assert "android.permission.INTERNET" not in names


def test_dangerous_permission_detected_by_mobsf_status_even_if_unlisted():
    """Trust MobSF's own 'dangerous' status even for permissions not in our
    static DANGEROUS_PERMISSIONS set — new Android permissions get added
    over time and shouldn't require a code change to be caught."""
    report = {
        "permissions": {
            "android.permission.SOME_FUTURE_PERM": {"description": "", "status": "dangerous"},
        }
    }
    perms = extractor.extract(report)["dangerous_permissions"]
    assert len(perms) == 1


def test_as_list_coerces_non_list_mobsf_quirks():
    """MobSF has, in practice, returned None/int/bool for fields that are
    normally lists — extraction must not crash on these."""
    report = {"activities": None, "services": 0, "receivers": False, "providers": ["a"]}
    result = extractor.extract(report)
    assert result["activities"] == []
    assert result["services"] == []
    assert result["receivers"] == []
    assert result["providers"] == ["a"]


def test_server_locations_grouped_by_country_sorted_by_domain_count():
    report = {
        "domains": {
            "a.example.com": {"geolocation": {"country_long": "United States"}},
            "b.example.com": {"geolocation": {"country_long": "United States"}},
            "c.example.ru": {"geolocation": {"country_long": "Russia"}},
            "no-geo.example.com": {},
        }
    }
    locations = extractor.extract(report)["network"]["server_locations"]
    assert list(locations.keys())[0] == "United States"  # most domains first
    assert locations["United States"] == ["a.example.com", "b.example.com"]
    assert locations["Russia"] == ["c.example.ru"]


def test_server_locations_ignores_unknown_or_missing_country():
    report = {
        "domains": {
            "x.example.com": {"geolocation": {"country_long": "Unknown"}},
            "y.example.com": {"geolocation": {"country_long": "N/A"}},
            "z.example.com": {},
        }
    }
    locations = extractor.extract(report)["network"]["server_locations"]
    assert locations == {}


def test_trackers_handles_dict_and_bare_list_shapes():
    """MobSF has returned trackers as both {'detected_trackers': [...]} and
    a bare list, depending on version."""
    assert extractor.extract(
        {"trackers": {"detected_trackers": ["Google Firebase"]}}
    )["trackers"] == ["Google Firebase"]
    assert extractor.extract({"trackers": ["Google Firebase"]})["trackers"] == ["Google Firebase"]
    assert extractor.extract({"trackers": {}})["trackers"] == []


def test_manifest_issues_dict_of_severities_shape():
    report = {
        "manifest_analysis": {
            "high": [{"title": "Debuggable", "description": "App is debuggable"}],
            "warning": [{"title": "Backup allowed", "description": ""}],
        }
    }
    issues = extractor.extract(report)["manifest_issues"]
    assert {"severity": "high", "title": "Debuggable", "description": "App is debuggable"} in issues
    assert len(issues) == 2


def test_manifest_issues_flat_list_shape():
    """Older/newer MobSF versions return manifest_analysis as a flat list
    with its own 'severity' and 'rule' keys instead of a dict-of-severities."""
    report = {
        "manifest_analysis": [
            {"severity": "high", "rule": "Debuggable", "description": "App is debuggable"},
        ]
    }
    issues = extractor.extract(report)["manifest_issues"]
    assert issues == [{"severity": "high", "title": "Debuggable", "description": "App is debuggable"}]


def test_exported_component_counts_only_true_strings():
    """MobSF encodes 'exported' as the string 'true'/'false', not a bool."""
    report = {
        "activities": [{"exported": "true"}, {"exported": "false"}],
        "services": [{"exported": "true"}],
    }
    counts = extractor.extract(report)["exported_count"]
    assert counts["activities"] == 1
    assert counts["services"] == 1
    assert counts["receivers"] == 0
    assert counts["providers"] == 0
