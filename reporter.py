from datetime import datetime
from pathlib import Path


REPORT_CSS = """
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; max-width: 900px; margin: 40px auto; padding: 0 20px; color: #1a1a1a; line-height: 1.6; }
h1 { border-bottom: 3px solid #e63946; padding-bottom: 12px; }
h2 { color: #2b2d42; border-left: 4px solid #e63946; padding-left: 12px; margin-top: 32px; }
h3 { color: #2b2d42; }
.meta { background: #f8f9fa; border-radius: 8px; padding: 16px; margin: 20px 0; display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
.meta span { font-size: 0.9em; }
.meta strong { color: #555; }
.score { font-size: 2em; font-weight: bold; }
.score.high { color: #2dc653; }
.score.medium { color: #f4a261; }
.score.low { color: #e63946; }
.ai-report { background: #fff; border: 1px solid #e0e0e0; border-radius: 8px; padding: 24px; margin-top: 24px; }
.ai-report h3 { color: #e63946; }
pre { background: #f8f9fa; padding: 12px; border-radius: 4px; overflow-x: auto; font-size: 0.85em; }
code { background: #f8f9fa; padding: 2px 5px; border-radius: 3px; font-size: 0.9em; }
ul { padding-left: 20px; }
.timestamp { color: #888; font-size: 0.85em; }
"""


def save_report(app_info: dict, ai_report: str, output_dir: str = ".") -> str:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    package = app_info.get("package", "unknown").replace(".", "_")
    filename = f"report_{package}_{timestamp}"

    md_path = Path(output_dir) / f"{filename}.md"
    html_path = Path(output_dir) / f"{filename}.html"

    md_content = _build_markdown(app_info, ai_report, timestamp)
    md_path.write_text(md_content)

    html_content = _build_html(app_info, ai_report, timestamp)
    html_path.write_text(html_content)

    return str(html_path)


def _build_markdown(app_info: dict, ai_report: str, timestamp: str) -> str:
    return f"""# APK Security Analysis Report

**App:** {app_info.get('name', 'Unknown')}
**Package:** {app_info.get('package', '')}
**Version:** {app_info.get('version', '')}
**MobSF Score:** {app_info.get('security_score', 'N/A')}/100
**Generated:** {timestamp}

---

{ai_report}
"""


def _build_html(app_info: dict, ai_report: str, timestamp: str) -> str:
    score = _parse_score(app_info.get('security_score', 0))
    score_class = "high" if score >= 70 else "medium" if score >= 40 else "low"

    ai_html = _markdown_to_html(ai_report)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Security Report — {app_info.get('name', 'Unknown')}</title>
<style>{REPORT_CSS}</style>
</head>
<body>
<h1>APK Security Analysis Report</h1>
<div class="meta">
  <span><strong>App:</strong> {app_info.get('name', 'Unknown')}</span>
  <span><strong>Package:</strong> {app_info.get('package', '')}</span>
  <span><strong>Version:</strong> {app_info.get('version', '')} (code {app_info.get('version_code', '')})</span>
  <span><strong>Target SDK:</strong> {app_info.get('target_sdk', '')} / Min: {app_info.get('min_sdk', '')}</span>
  <span><strong>MobSF Score:</strong> <span class="score {score_class}">{score}/100</span></span>
  <span><strong>Avg CVSS:</strong> {app_info.get('average_cvss', 'N/A')}</span>
</div>
<p class="timestamp">Generated {timestamp}</p>

<div class="ai-report">
{ai_html}
</div>
</body>
</html>"""


def _parse_score(score) -> int:
    try:
        return int(score)
    except (ValueError, TypeError):
        return 0


def _markdown_to_html(text: str) -> str:
    """Minimal markdown → HTML conversion for the report body."""
    lines = text.split("\n")
    html_lines = []
    in_ul = False
    in_pre = False

    for line in lines:
        if line.startswith("```"):
            if in_pre:
                html_lines.append("</pre>")
                in_pre = False
            else:
                if in_ul:
                    html_lines.append("</ul>")
                    in_ul = False
                html_lines.append("<pre>")
                in_pre = True
            continue

        if in_pre:
            html_lines.append(_escape(line))
            continue

        if line.startswith("### "):
            if in_ul:
                html_lines.append("</ul>")
                in_ul = False
            html_lines.append(f"<h3>{_escape(line[4:])}</h3>")
        elif line.startswith("## "):
            if in_ul:
                html_lines.append("</ul>")
                in_ul = False
            html_lines.append(f"<h2>{_escape(line[3:])}</h2>")
        elif line.startswith("# "):
            if in_ul:
                html_lines.append("</ul>")
                in_ul = False
            html_lines.append(f"<h2>{_escape(line[2:])}</h2>")
        elif line.startswith("- ") or line.startswith("* "):
            if not in_ul:
                html_lines.append("<ul>")
                in_ul = True
            html_lines.append(f"<li>{_inline(_escape(line[2:]))}</li>")
        elif line.strip() == "":
            if in_ul:
                html_lines.append("</ul>")
                in_ul = False
            html_lines.append("")
        else:
            if in_ul:
                html_lines.append("</ul>")
                in_ul = False
            html_lines.append(f"<p>{_inline(_escape(line))}</p>")

    if in_ul:
        html_lines.append("</ul>")

    return "\n".join(html_lines)


def _escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _inline(text: str) -> str:
    import re
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"`(.+?)`", r"<code>\1</code>", text)
    return text
