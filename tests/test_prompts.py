"""
build_analysis_prompt's language injection uses an f-string over a long
literal block — a stray `{`/`}` in that block would silently break
formatting (or raise) the moment a real prompt is built, so this guards
against that regressing.
"""
import prompts

MINIMAL_EXTRACTED = {
    "app": {
        "name": "Test App", "package": "com.test.app", "version": "1.0",
        "version_code": "1", "min_sdk": "21", "target_sdk": "34",
    },
    "security_score": 80,
    "average_cvss": 0,
    "dangerous_permissions": [],
    "trackers": [],
    "secrets": [],
    "network": {
        "domains": {"all": [], "count": 0, "flagged": []},
        "urls": [],
        "network_security_issues": [],
        "certificate_issues": [],
        "server_locations": {},
    },
    "manifest_issues": [],
    "code_issues": [],
    "exported_count": {},
}


def test_defaults_to_british_english():
    prompt = prompts.build_analysis_prompt(MINIMAL_EXTRACTED)
    assert "Write the entire report in British English" in prompt


def test_language_override_is_injected():
    prompt = prompts.build_analysis_prompt(MINIMAL_EXTRACTED, language="French")
    assert "Write the entire report in French" in prompt
    assert "{language}" not in prompt
