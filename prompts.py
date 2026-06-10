import json


def build_analysis_prompt(extracted: dict) -> str:
    app   = extracted["app"]
    score = extracted["security_score"]
    cvss  = extracted["average_cvss"]

    sections = []

    # ── System role + context block ──────────────────────────────────────────
    sections.append(f"""You are an expert mobile application security analyst. Your job is to produce a clear, plain-English security report for a non-technical reader — someone who needs to decide whether this app is safe to use or allow on their network.

**Critically:** you must use your existing knowledge about this app when writing the report. Do not treat findings in isolation — a permission or behaviour that looks alarming in an unknown app may be completely normal and expected for a well-known, trusted application. Your job is to give an accurate picture, not to generate false alarm.

## App Under Analysis
- **Name:** {app['name']}
- **Package:** {app['package']}
- **Version:** {app['version']} (build {app['version_code']})
- **SDK:** Min {app['min_sdk']} / Target {app['target_sdk']}
- **MobSF Security Score:** {score}/100  *(higher = better; below 40 is critical)*
- **Average CVSS:** {cvss}
""")

    # ── Findings ─────────────────────────────────────────────────────────────
    if extracted["dangerous_permissions"]:
        perms = "\n".join(
            f"- `{p['name']}` — {p['description']}" for p in extracted["dangerous_permissions"]
        )
        sections.append(f"## Dangerous Permissions\n{perms}")

    if extracted["trackers"]:
        tracker_list = ", ".join(str(t) for t in extracted["trackers"][:20])
        sections.append(f"## Tracking SDKs Detected\n{tracker_list}")

    if extracted["secrets"]:
        secrets_text = "\n".join(f"- {s}" for s in extracted["secrets"][:20])
        sections.append(f"## Hardcoded Secrets / Sensitive Strings\n{secrets_text}")

    net = extracted["network"]
    if net["domains"]["all"]:
        domain_lines = "\n".join(f"- {d}" for d in net["domains"]["all"][:30])
        sections.append(f"## Network Domains ({net['domains']['count']} total)\n{domain_lines}")

    if net["domains"]["flagged"]:
        flagged = json.dumps(net["domains"]["flagged"], indent=2)
        sections.append(f"## Flagged / Geolocated Domains\n```json\n{flagged}\n```")

    if net["urls"]:
        url_lines = "\n".join(f"- {u.get('url', u)}" for u in net["urls"][:20])
        sections.append(f"## Hardcoded URLs\n{url_lines}")

    if extracted["manifest_issues"]:
        high  = [i for i in extracted["manifest_issues"] if i["severity"] == "high"]
        warns = [i for i in extracted["manifest_issues"] if i["severity"] == "warning"]
        lines = ""
        for i in high:
            lines += f"- **[HIGH]** {i['title']}: {i['description']}\n"
        for i in warns[:10]:
            lines += f"- **[WARN]** {i['title']}: {i['description']}\n"
        sections.append(f"## AndroidManifest Issues\n{lines.strip()}")

    if extracted["code_issues"]:
        lines = "\n".join(
            f"- **[{i['severity'].upper()}]** {i['title']}: {i['description']}"
            for i in extracted["code_issues"][:20]
        )
        sections.append(f"## Static Code Analysis Issues\n{lines}")

    exported = {k: v for k, v in extracted["exported_count"].items() if v > 0}
    if exported:
        exp_text = ", ".join(f"{k}: {v}" for k, v in exported.items())
        sections.append(f"## Exported Components (accessible to other apps)\n{exp_text}")

    if net["network_security_issues"]:
        ns_text = "\n".join(f"- {i}" for i in net["network_security_issues"][:10])
        sections.append(f"## Network Security Config Issues\n{ns_text}")

    if net["certificate_issues"]:
        cert_text = "\n".join(f"- {i}" for i in net["certificate_issues"])
        sections.append(f"## Certificate Issues\n{cert_text}")

    # ── Instructions ─────────────────────────────────────────────────────────
    prompt_body = "\n\n".join(sections)

    prompt_body += """

---

Write a security report with exactly these six sections. Use `##` for section headings.

## App Context & Reputation
Do you recognise this app? State clearly:
- What it is and what it's designed to do
- Who develops it and whether it is open-source, commercial, or unknown
- Its general reputation in the security and developer community (trusted, controversial, unknown, known malware, etc.)
- Whether the permissions and behaviours flagged below are **expected for this type of app** or genuinely suspicious

If you do not recognise the app at all, say so plainly. This section should give the reader crucial context before they see the findings.

## Executive Summary
2–3 sentences. State what the app does and give an overall risk verdict in bold: **CRITICAL**, **HIGH**, **MEDIUM**, or **LOW**. This verdict must account for both the static analysis findings AND the app's known reputation and purpose — a trusted open-source tool with expected system permissions should not be rated the same as an unknown app with the same permissions.

## Top Security Findings
The most significant issues in descending priority. For each, use this format:

**🔴 CRITICAL / 🟠 HIGH / 🟡 MEDIUM / 🟢 LOW — Finding title**
One or two sentences: what it is, why it matters, and — importantly — whether it is concerning given this app's known purpose or whether it is expected behaviour.

Include up to 8 findings. For any finding that is a known false positive or expected behaviour for this app type, mark it explicitly: add *(expected for this app type)* or *(likely false positive)* after the severity label.

## Privacy Concerns
What personal data can this app access, collect, or share? Be specific about permissions and which ones are justified by the app's purpose vs which are unexplained. 4–6 bullet points.

## Network & Data Activity
Where does the app send data? Flag anything unexpected. Note if connections are consistent with the app's stated purpose. 4–6 bullet points.

## Red Flags
Unambiguous list of anything that suggests malicious behaviour, spyware, or dangerously poor security practice — **after accounting for the app's known purpose**. If nothing rises to this level, write one sentence: "No significant red flags identified."

## Verdict & Recommendations
3–5 plain-English action items for someone deciding whether to install or allow this app. Factor in reputation. Start each with a strong verb (Install / Avoid / Remove / Monitor / Verify / Restrict).

---

**Rules — follow strictly:**
- The "Hardcoded Secrets" findings often contain false positives: translation strings, UI label keys, or resource identifiers that look like credentials but are not. Identify and call these out rather than treating them as real leaked secrets
- Do not open any section with "Based on", "Looking at the", or "It appears"
- Do not repeat the same finding across multiple sections
- Do not use "In conclusion", "Overall", or "To summarise"
- If a section has nothing meaningful to add, write one sentence saying so
- Be direct: if something is genuinely dangerous, say it is; if it is not, say that too
- Use plain English throughout — briefly explain any technical terms
"""

    return prompt_body
