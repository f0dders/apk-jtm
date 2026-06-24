import math
from datetime import datetime
from pathlib import Path

import markdown as md
from model_tier import TIER_META


# ---------------------------------------------------------------------------
# Scoring helpers
# ---------------------------------------------------------------------------

def _parse_score(score) -> int:
    try:
        return max(0, min(100, int(score)))
    except (ValueError, TypeError):
        return 0


def _risk(score: int) -> tuple[str, str, str]:
    """Returns (label, css-class, hex-colour) based on MobSF score (higher = safer)."""
    if score >= 80: return "Low Risk",      "low",      "#10b981"
    if score >= 60: return "Medium Risk",   "medium",   "#f59e0b"
    if score >= 40: return "High Risk",     "high",     "#ef4444"
    return              "Critical Risk", "critical", "#be123c"


def _score_ring_svg(score: int, colour: str) -> str:
    r = 52
    cx = cy = 64
    circ = 2 * math.pi * r
    filled = (score / 100) * circ
    gap = circ - filled
    # offset by circ/4 so the arc starts at 12 o'clock
    offset = circ / 4
    return f"""<svg width="128" height="128" viewBox="0 0 128 128" xmlns="http://www.w3.org/2000/svg">
  <circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="#e5e7eb" stroke-width="12"/>
  <circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{colour}" stroke-width="12"
    stroke-dasharray="{filled:.2f} {gap:.2f}" stroke-dashoffset="{offset:.2f}"
    stroke-linecap="round"/>
  <text x="{cx}" y="{cy - 6}" text-anchor="middle" dominant-baseline="central"
    font-size="26" font-weight="700" fill="{colour}"
    font-family="-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif">{score}</text>
  <text x="{cx}" y="{cy + 16}" text-anchor="middle" dominant-baseline="central"
    font-size="11" fill="#9ca3af"
    font-family="-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif">out of 100</text>
</svg>"""


def _verdict_display(verdict: str | None) -> tuple[str, str]:
    """Returns (action_label, css_class) for the AI contextual verdict."""
    mapping = {
        "LOW":      ("✓ Safe to use",      "safe"),
        "MEDIUM":   ("⚠ Use with caution", "caution"),
        "HIGH":     ("⚠ Review carefully", "review"),
        "CRITICAL": ("✗ Avoid",            "avoid"),
    }
    if verdict and verdict.upper() in mapping:
        return mapping[verdict.upper()]
    return ("Unrated", "unknown")


def _chip(icon: str, label: str, items: list, level: str = "") -> str:
    """Renders a stat chip. If items are provided, wraps in <details> for expand/collapse."""
    cls = f"chip {level}".strip()
    if not items:
        return f'<span class="{cls}"><span class="chip-icon">{icon}</span>{label}</span>'
    items_html = "".join(f"<li>{_esc(str(item))}</li>" for item in items)
    return (
        f'<details class="{cls}">'
        f'<summary><span class="chip-icon">{icon}</span>{label}</summary>'
        f'<ul class="chip-list">{items_html}</ul>'
        f'</details>'
    )


# ---------------------------------------------------------------------------
# CSS
# ---------------------------------------------------------------------------

REPORT_CSS = """
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;
  max-width: 980px; margin: 0 auto; padding: 28px 20px 64px;
  color: #111827; line-height: 1.65; background: #f3f4f6;
}

/* ── Header card ── */
.report-header {
  background: #fff; border-radius: 16px; padding: 28px 32px;
  margin-bottom: 16px; display: flex; align-items: center; gap: 28px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.08), 0 4px 16px rgba(0,0,0,0.05);
}
.score-ring { flex-shrink: 0; }
.app-icon-wrap { flex-shrink: 0; }
.app-icon {
  width: 72px; height: 72px; border-radius: 16px; object-fit: cover;
  box-shadow: 0 2px 8px rgba(0,0,0,0.12);
}
.app-icon-placeholder {
  width: 72px; height: 72px; border-radius: 16px;
  background: #f3f4f6; border: 1px solid #e5e7eb;
  display: flex; align-items: center; justify-content: center;
  font-size: 2em;
}
.header-body { flex: 1; min-width: 0; }
.app-name {
  font-size: 1.55em; font-weight: 800; color: #111827;
  margin-bottom: 3px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.app-package {
  font-size: 0.88em; color: #6b7280; margin-bottom: 2px;
  font-family: 'SF Mono', 'Fira Code', monospace;
}
.app-meta-line { font-size: 0.82em; color: #9ca3af; margin-bottom: 14px; }
.risk-badge {
  display: inline-block; padding: 5px 16px; border-radius: 99px;
  font-size: 0.78em; font-weight: 700; letter-spacing: 0.06em;
  text-transform: uppercase;
}
.risk-low      { background: #d1fae5; color: #065f46; }
.risk-medium   { background: #fef3c7; color: #92400e; }
.risk-high     { background: #fee2e2; color: #991b1b; }
.risk-critical { background: #ffe4e6; color: #881337; }

/* ── Stat chips ── */
.stat-chips { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 16px; align-items: flex-start; }

/* Plain span chip */
span.chip {
  display: inline-flex; align-items: center; gap: 5px;
  padding: 5px 11px; border-radius: 8px;
  background: #f9fafb; border: 1px solid #e5e7eb;
  font-size: 0.82em; font-weight: 500; color: #374151;
  white-space: nowrap;
}
span.chip.warn    { background: #fff7ed; border-color: #fed7aa; color: #c2410c; }
span.chip.danger  { background: #fef2f2; border-color: #fecaca; color: #dc2626; }

/* Expandable details chip */
details.chip {
  border-radius: 8px; border: 1px solid #e5e7eb;
  background: #f9fafb; font-size: 0.82em; font-weight: 500; color: #374151;
}
details.chip.warn   { background: #fff7ed; border-color: #fed7aa; color: #c2410c; }
details.chip.danger { background: #fef2f2; border-color: #fecaca; color: #dc2626; }
details.chip > summary {
  display: inline-flex; align-items: center; gap: 5px;
  padding: 5px 11px; white-space: nowrap;
  list-style: none; cursor: pointer; user-select: none;
}
details.chip > summary::-webkit-details-marker { display: none; }
details.chip > summary::after { content: " ▾"; font-size: 0.8em; opacity: 0.6; }
details.chip[open] > summary::after { content: " ▴"; }
details.chip[open] {
  width: 100%;
  padding-bottom: 10px;
}
details.chip[open] > summary { font-weight: 600; }
.chip-list {
  list-style: none; padding: 0 12px; margin: 4px 0 0;
  display: flex; flex-wrap: wrap; gap: 4px;
}
.chip-list li {
  background: rgba(0,0,0,0.06); padding: 2px 8px; border-radius: 4px;
  font-size: 0.88em; font-weight: 400;
  font-family: 'SF Mono','Fira Code',monospace;
}
details.chip.warn   .chip-list li { background: rgba(194,65,12,0.08); }
details.chip.danger .chip-list li { background: rgba(220,38,38,0.08); }

.chip-icon { font-size: 1em; line-height: 1; }

/* ── Meta strip ── */
.meta-strip {
  background: #fff; border-radius: 12px; padding: 13px 24px;
  margin-bottom: 16px; display: flex; flex-wrap: wrap; gap: 20px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.06);
  font-size: 0.83em; color: #6b7280;
}
.meta-strip span strong { color: #111827; font-weight: 600; }

/* ── Report body ── */
.report-body {
  background: #fff; border-radius: 16px; padding: 36px 40px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.08), 0 4px 16px rgba(0,0,0,0.05);
}
.report-body h1 {
  font-size: 1.2em; font-weight: 700; color: #111827;
  border-left: 4px solid #dc2626; padding-left: 12px;
  margin: 32px 0 12px;
}
.report-body h1:first-child { margin-top: 0; }
.report-body h2 {
  font-size: 1.1em; font-weight: 700; color: #111827;
  border-left: 4px solid #dc2626; padding-left: 12px;
  margin: 32px 0 12px;
}
.report-body h2:first-child { margin-top: 0; }
.report-body h3 {
  font-size: 0.97em; font-weight: 600; color: #374151;
  margin: 20px 0 8px;
}
.report-body p  { margin-bottom: 12px; color: #374151; }
.report-body ul, .report-body ol { padding-left: 22px; margin-bottom: 12px; }
.report-body li { margin-bottom: 6px; color: #374151; }
.report-body strong { color: #111827; }
.report-body em { color: #6b7280; }
.report-body code {
  background: #f3f4f6; padding: 2px 6px; border-radius: 4px;
  font-size: 0.84em; font-family: 'SF Mono','Fira Code',monospace; color: #1f2937;
}
.report-body pre {
  background: #1f2937; color: #f9fafb; padding: 16px 20px;
  border-radius: 10px; overflow-x: auto; margin-bottom: 16px; font-size: 0.84em;
}
.report-body pre code { background: none; padding: 0; color: inherit; }
.report-body table {
  width: 100%; border-collapse: collapse; margin-bottom: 16px; font-size: 0.88em;
}
.report-body th {
  background: #f3f4f6; text-align: left; padding: 8px 12px;
  border: 1px solid #e5e7eb; font-weight: 600;
}
.report-body td { padding: 8px 12px; border: 1px solid #e5e7eb; }
.report-body tr:nth-child(even) td { background: #f9fafb; }
.report-body blockquote {
  border-left: 3px solid #d1d5db; padding-left: 14px;
  margin: 0 0 12px; color: #6b7280;
}
.report-body hr { border: none; border-top: 1px solid #e5e7eb; margin: 24px 0; }

/* ── Action verdict ── */
.verdict-action {
  display: inline-block; padding: 6px 18px; border-radius: 99px;
  font-size: 0.82em; font-weight: 700; letter-spacing: 0.03em;
  margin-top: 10px;
}
.verdict-safe     { background: #d1fae5; color: #065f46; }
.verdict-caution  { background: #fef3c7; color: #92400e; }
.verdict-review   { background: #ffedd5; color: #9a3412; }
.verdict-avoid    { background: #fee2e2; color: #991b1b; }
.verdict-unknown  { background: #f3f4f6; color: #6b7280; }
.verdict-summary {
  font-size: 0.83em; color: #374151; margin-top: 8px; line-height: 1.5;
}
.verdict-note {
  font-size: 0.72em; color: #9ca3af; margin-top: 4px; font-style: italic;
}
.static-score-note {
  font-size: 0.72em; color: #9ca3af; margin-top: 6px;
}

/* ── Model tier badge ── */
.model-info {
  display: flex; align-items: center; gap: 8px;
  margin-top: 14px; flex-wrap: wrap;
}
.model-label {
  font-size: 0.78em; color: #6b7280;
}
.model-name {
  font-size: 0.78em; font-weight: 600; color: #374151;
  font-family: 'SF Mono','Fira Code',monospace;
}
.tier-badge {
  display: inline-flex; align-items: center; gap: 4px;
  padding: 2px 10px; border-radius: 99px;
  font-size: 0.72em; font-weight: 700; letter-spacing: 0.05em;
  text-transform: uppercase; color: #fff;
}
.model-disclaimer {
  background: #fffbeb; border: 1px solid #fde68a; border-radius: 10px;
  padding: 10px 16px; margin-bottom: 16px;
  font-size: 0.83em; color: #92400e; display: flex; gap: 8px; align-items: flex-start;
}
.model-disclaimer-icon { flex-shrink: 0; font-size: 1.1em; }

/* ── Footer ── */
.report-footer {
  text-align: center; margin-top: 20px;
  font-size: 0.78em; color: #9ca3af;
}
"""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def save_report(app_info: dict, ai_report: str, output_dir: str = ".") -> str:
    import json as _json

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    package = app_info.get("package", "unknown").replace(".", "_")
    filename = f"report_{package}_{timestamp}"

    md_path   = Path(output_dir) / f"{filename}.md"
    html_path = Path(output_dir) / f"{filename}.html"
    meta_path = Path(output_dir) / f"{filename}.meta.json"

    md_path.write_text(_build_markdown(app_info, ai_report, timestamp))
    html_path.write_text(_build_html(app_info, ai_report, timestamp))

    score = _parse_score(app_info.get("security_score", 0))
    risk_label, risk_cls, _ = _risk(score)
    tier = app_info.get("ai_model_tier", "unknown")
    tier_label, _, _ = TIER_META[tier]
    ai_verdict_raw = app_info.get("ai_verdict")
    ai_verdict_label, ai_verdict_cls = _verdict_display(ai_verdict_raw)
    meta_path.write_text(_json.dumps({
        "app_name":       app_info.get("name", "Unknown"),
        "package":        app_info.get("package", ""),
        "version":        app_info.get("version", ""),
        "md5":            app_info.get("md5", ""),
        "score":          score,
        "risk_label":     risk_label,
        "risk_cls":       risk_cls,
        "timestamp":      timestamp,
        "perms":          app_info.get("dangerous_perms_count", 0),
        "trackers":       app_info.get("trackers_count", 0),
        "ai_provider":    app_info.get("ai_provider", ""),
        "ai_model":       app_info.get("ai_model", ""),
        "ai_model_tier":  tier,
        "ai_tier_label":  tier_label,
        "ai_verdict":       ai_verdict_raw,
        "ai_verdict_label": ai_verdict_label,
        "ai_verdict_cls":   ai_verdict_cls,
        "ai_summary":       app_info.get("ai_summary", ""),
        "perms_summary":    app_info.get("perms_summary", ""),
        "apkid_available":  app_info.get("apkid", {}).get("available", False),
        "apkid_packer":     app_info.get("apkid", {}).get("has_packer", False),
        "apkid_anti_vm":    app_info.get("apkid", {}).get("has_anti_vm", False),
        "apkid_malware_packer": app_info.get("apkid", {}).get("known_malware_packer", False),
    }, indent=2))

    return str(html_path)


# ---------------------------------------------------------------------------
# Builders
# ---------------------------------------------------------------------------

def _build_markdown(app_info: dict, ai_report: str, timestamp: str) -> str:
    score = _parse_score(app_info.get("security_score", 0))
    risk_label, _, _ = _risk(score)
    return f"""# APK Security Analysis — {app_info.get('name', 'Unknown')}

| Field | Value |
|---|---|
| **App** | {app_info.get('name', 'Unknown')} |
| **Package** | {app_info.get('package', '')} |
| **Version** | {app_info.get('version', '')} |
| **MobSF Score** | {score}/100 |
| **Risk Level** | {risk_label} |
| **Avg CVSS** | {app_info.get('average_cvss', 'N/A')} |
| **Generated** | {timestamp} |

---

{ai_report}
"""


def _build_html(app_info: dict, ai_report: str, timestamp: str) -> str:
    score       = _parse_score(app_info.get("security_score", 0))
    risk_label, risk_cls, risk_colour = _risk(score)
    ring_svg    = _score_ring_svg(score, risk_colour)
    ai_html     = _render_markdown(ai_report)
    chips       = _build_chips(app_info)
    dt          = datetime.strptime(timestamp, "%Y%m%d_%H%M%S").strftime("%d %b %Y, %H:%M")

    icon_b64 = app_info.get("icon_b64")
    icon_html = (
        f'<img src="data:image/png;base64,{icon_b64}" alt="App icon" class="app-icon">'
        if icon_b64 else
        '<div class="app-icon-placeholder">📱</div>'
    )

    ai_model    = app_info.get("ai_model", "")
    ai_provider = app_info.get("ai_provider", "")
    tier        = app_info.get("ai_model_tier", "unknown")
    tier_label, tier_colour, tier_disclaimer = TIER_META[tier]

    ai_verdict_raw              = app_info.get("ai_verdict")
    ai_verdict_label, ai_verdict_cls = _verdict_display(ai_verdict_raw)
    ai_summary   = app_info.get("ai_summary", "")
    perms_summary = app_info.get("perms_summary", "")

    model_info_html = ""
    if ai_model:
        model_info_html = (
            f'<div class="model-info">'
            f'<span class="model-label">Analysed by</span>'
            f'<span class="model-name">{_esc(ai_model)}</span>'
            f'<span class="tier-badge" style="background:{tier_colour}">{tier_label}</span>'
            f'</div>'
        )

    disclaimer_html = ""
    if tier_disclaimer:
        disclaimer_html = (
            f'<div class="model-disclaimer">'
            f'<span class="model-disclaimer-icon">⚠️</span>'
            f'<span>{tier_disclaimer}</span>'
            f'</div>'
        )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Security Report — {_esc(app_info.get('name', 'Unknown'))}</title>
<style>{REPORT_CSS}</style>
</head>
<body>

<div class="report-header">
  <div class="score-ring">{ring_svg}</div>
  <div class="app-icon-wrap">{icon_html}</div>
  <div class="header-body">
    <div class="app-name">{_esc(app_info.get('name', 'Unknown'))}</div>
    <div class="app-package">{_esc(app_info.get('package', ''))}</div>
    <div class="app-meta-line">
      v{_esc(str(app_info.get('version', '')))}
      &nbsp;·&nbsp; Target SDK {_esc(str(app_info.get('target_sdk', '?')))}
      &nbsp;·&nbsp; Min SDK {_esc(str(app_info.get('min_sdk', '?')))}
    </div>
    <span class="verdict-action verdict-{ai_verdict_cls}">{ai_verdict_label}</span>
    {f'<div class="verdict-summary">{_esc(ai_summary)}</div>' if ai_summary else ''}
    <div class="static-score-note">MobSF static score: {score}/100 · {risk_label}</div>
    <div class="stat-chips">{chips}</div>
    {model_info_html}
  </div>
</div>

{disclaimer_html}<div class="meta-strip">
  <span><strong>File:</strong> {_esc(app_info.get('file_name', 'N/A'))}</span>
  <span><strong>Size:</strong> {_esc(str(app_info.get('size', 'N/A')))}</span>
  <span><strong>MD5:</strong> {_esc(app_info.get('md5', 'N/A'))}</span>
  {f'<span><strong>Avg CVSS:</strong> {_esc(str(cvss))}</span>' if (cvss := app_info.get('average_cvss')) and str(cvss).lower() not in ('none', 'n/a', '0', '0.0', '') else ''}
  <span><strong>Generated:</strong> {dt}</span>
</div>

<div class="report-body">
{ai_html}
</div>

<div class="report-footer">
  Generated by APK-JTM &nbsp;·&nbsp; Powered by MobSF + AI
</div>

</body>
</html>"""


def _build_chips(app_info: dict) -> str:
    chips = []

    perms = app_info.get("dangerous_perms_count", 0)
    level = "danger" if perms > 8 else "warn" if perms > 3 else ""
    chips.append(_chip("🔒", f"{perms} Dangerous Perms", app_info.get("dangerous_perms_list", []), level))

    trackers = app_info.get("trackers_count", 0)
    level = "danger" if trackers > 5 else "warn" if trackers > 2 else ""
    chips.append(_chip("📡", f"{trackers} Trackers", app_info.get("trackers_list", []), level))

    domains = app_info.get("domains_count", 0)
    level = "warn" if domains > 30 else ""
    chips.append(_chip("🌐", f"{domains} Domains", app_info.get("domains_list", []), level))

    secrets = app_info.get("secrets_count", 0)
    level = "danger" if secrets > 5 else "warn" if secrets > 0 else ""
    chips.append(_chip("🔑", f"{secrets} Secrets", app_info.get("secrets_list", []), level))

    issues = app_info.get("code_issues_count", 0)
    level = "danger" if issues > 10 else "warn" if issues > 3 else ""
    chips.append(_chip("⚠️", f"{issues} Code Issues", app_info.get("code_issues_list", []), level))

    cvss = app_info.get("average_cvss")
    if cvss and str(cvss).lower() not in ("none", "n/a", "0", "0.0", ""):
        try:
            cvss_f = float(cvss)
            level = "danger" if cvss_f >= 7 else "warn" if cvss_f >= 4 else ""
        except (ValueError, TypeError):
            level = ""
        chips.append(_chip("📊", f"CVSS {cvss}", [], level))

    apkid = app_info.get("apkid", {})
    if apkid.get("available"):
        packer_names = apkid.get("packers", [])
        obfs_names   = apkid.get("obfuscators", [])
        if apkid.get("known_malware_packer"):
            chips.append(_chip("🚨", f"Malware packer: {', '.join(packer_names)}", [], "danger"))
        elif packer_names:
            chips.append(_chip("📦", f"Packed: {', '.join(packer_names)}", [], "warn"))
        if apkid.get("has_anti_vm"):
            chips.append(_chip("🕵️", "Anti-VM detected", apkid.get("anti_vm", []), "danger"))
        if apkid.get("has_anti_debug"):
            items = apkid.get("anti_debug", []) + apkid.get("anti_disassembly", [])
            chips.append(_chip("🛡️", "Anti-debug detected", items, "warn"))
        if apkid.get("repackaged"):
            chips.append(_chip("♻️", "Repackaged (dex2jar)", [], "warn"))
        if not any([packer_names, apkid.get("has_anti_vm"), apkid.get("has_anti_debug"), apkid.get("repackaged")]):
            compiler = ", ".join(apkid.get("compilers", [])) or "standard"
            chips.append(_chip("✅", f"No packers — {compiler}", [], ""))

    return "\n".join(chips)


def _render_markdown(text: str) -> str:
    return md.markdown(
        text,
        extensions=["extra", "sane_lists"],
        output_format="html",
    )


def _esc(text: str) -> str:
    return (text
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;"))
