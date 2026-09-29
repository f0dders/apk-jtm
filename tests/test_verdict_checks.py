"""
The model's verdict is checked in code, not trusted: a known malware packer
raises a low verdict, and a summary that disagrees with the final verdict is
flagged to the reader rather than hidden.
"""
import pytest

import reporter
import server

PACKER = {"known_malware_packer": True}


# ── _apply_verdict_floor ────────────────────────────────────────────────────

@pytest.mark.parametrize("verdict", ["LOW", "MEDIUM"])
def test_known_packer_raises_a_low_verdict_to_high(verdict):
    """Small models do not reliably obey the prompt's escalation rule."""
    assert server._apply_verdict_floor(verdict, PACKER) == ("HIGH", verdict)


@pytest.mark.parametrize("verdict", ["HIGH", "CRITICAL"])
def test_known_packer_leaves_high_and_critical_alone(verdict):
    """Nothing was raised, so the reader must not be told it was."""
    assert server._apply_verdict_floor(verdict, PACKER) == (verdict, None)


@pytest.mark.parametrize("verdict", ["LOW", "MEDIUM", "HIGH", "CRITICAL"])
def test_verdict_is_unchanged_without_the_packer_flag(verdict):
    """Only a known malware packer may override the model's own rating."""
    assert server._apply_verdict_floor(verdict, {}) == (verdict, None)
    assert server._apply_verdict_floor(verdict, {"known_malware_packer": False}) == (verdict, None)


def test_missing_verdict_stays_missing_even_with_a_packer():
    """Inventing a level would hide that the report is incomplete."""
    assert server._apply_verdict_floor(None, PACKER) == (None, None)


# ── _summary_verdict ────────────────────────────────────────────────────────

def test_summary_verdict_is_the_first_standalone_bold_level():
    """The Executive Summary comes first, so its level is the first one found."""
    assert server._summary_verdict("Verdict: **medium** overall. Later: **HIGH**") == "MEDIUM"


def test_summary_verdict_ignores_finding_badges():
    """Finding badges carry an emoji inside the bold run and are not the summary."""
    report = "**🔴 CRITICAL — Cleartext traffic**\n\nOverall: **LOW**"
    assert server._summary_verdict(report) == "LOW"


def test_summary_verdict_is_none_without_a_bold_level():
    """With nothing to compare, no mismatch can be claimed."""
    assert server._summary_verdict("**🔴 CRITICAL — Title** and plain HIGH") is None


# ── Report notices ──────────────────────────────────────────────────────────

def _html(**overrides):
    app_info = {"name": "Test App", "package": "com.test.app", "security_score": 80}
    app_info.update(overrides)
    return reporter._build_html(app_info, "Report body.", "20260101_120000")


def test_raised_verdict_notice_is_shown():
    """The badge says HIGH while the text may say LOW; the reader needs to know why."""
    html = _html(ai_verdict="HIGH", ai_verdict_raised_from="LOW")
    assert "raised to HIGH" in html


def test_self_contradiction_notice_is_shown():
    """A summary that disagrees with the final verdict must be surfaced."""
    html = _html(ai_verdict="HIGH", ai_summary_verdict_mismatch="LOW")
    assert "contradicted itself" in html


def test_no_notices_without_the_flags():
    """Notices on a consistent report would cry wolf."""
    html = _html(ai_verdict="HIGH")
    assert "raised to" not in html
    assert "contradicted itself" not in html
