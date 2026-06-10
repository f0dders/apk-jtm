import json


def build_analysis_prompt(extracted: dict) -> str:
    app   = extracted["app"]
    score = extracted["security_score"]
    cvss  = extracted["average_cvss"]

    sections = []

    # ── Context block ────────────────────────────────────────────────────────
    sections.append(f"""You are an expert mobile application security analyst. Your job is to analyse the MobSF static analysis results below and produce a clear, plain-English security report for a non-technical reader — someone who needs to decide whether this app is safe to use or allow on their network.

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

Using the findings above, write a security report with exactly these six sections. Use `##` for section headings.

## Executive Summary
2–3 sentences only. State what this app appears to be and its purpose, then give a single overall risk verdict in bold: **CRITICAL**, **HIGH**, **MEDIUM**, or **LOW**. Base the verdict on the MobSF score and the severity of findings.

## Top Security Findings
List the most significant issues in descending priority. For each finding use this format:

**🔴 CRITICAL / 🟠 HIGH / 🟡 MEDIUM / 🟢 LOW — Finding title**
One or two sentences: what it is, why it matters to a non-technical reader.

Include up to 8 findings. Omit severity levels that have no findings.

## Privacy Concerns
What personal data can this app access, collect, or share? Cover permissions, trackers, and hardcoded endpoints. Use bullet points. 4–6 bullets max.

## Network & Data Activity
Where does the app send data? Flag advertising networks, analytics, suspicious geographies, or unexpected third-party servers. Note anything that looks like covert data collection. 4–6 bullets max.

## Red Flags
Direct, unambiguous list of anything that suggests malicious behaviour, spyware characteristics, or dangerously poor security practice. If nothing rises to this level, write a single sentence: "No significant red flags identified."

## Verdict & Recommendations
3–5 plain-English action items for someone deciding whether to install or permit this app. Start each with a strong verb (Install / Avoid / Remove / Monitor / Verify / Restrict).

---

**Writing rules — follow these strictly:**
- Do not open any section with "Based on", "Looking at the", or "It appears"
- Do not repeat findings across sections — each section adds new information
- Do not use "In conclusion", "Overall", or "To summarise" anywhere
- If a section genuinely has nothing to report, write one sentence saying so
- Use plain English — avoid jargon unless briefly explained
- Be direct: if something is dangerous, say it is dangerous
"""

    return prompt_body
