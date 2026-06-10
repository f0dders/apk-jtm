import json


def build_analysis_prompt(extracted: dict) -> str:
    app = extracted["app"]
    score = extracted["security_score"]
    cvss = extracted["average_cvss"]

    sections = []

    sections.append(f"""You are a mobile application security analyst. Analyse the following MobSF security scan results for an Android APK and produce a clear, plain-English report suitable for someone without a pentesting background.

## App Details
- Name: {app['name']}
- Package: {app['package']}
- Version: {app['version']} (code: {app['version_code']})
- Min SDK: {app['min_sdk']}, Target SDK: {app['target_sdk']}
- MobSF Security Score: {score}/100
- Average CVSS: {cvss}
""")

    if extracted["dangerous_permissions"]:
        perms = "\n".join(
            f"  - {p['name']}: {p['description']}" for p in extracted["dangerous_permissions"]
        )
        sections.append(f"## Dangerous Permissions Requested\n{perms}")

    if extracted["trackers"]:
        tracker_list = ", ".join(str(t) for t in extracted["trackers"][:20])
        sections.append(f"## Tracking SDKs Detected\n{tracker_list}")

    if extracted["secrets"]:
        secrets_text = "\n".join(f"  - {s}" for s in extracted["secrets"][:20])
        sections.append(f"## Hardcoded Secrets / Sensitive Strings\n{secrets_text}")

    net = extracted["network"]
    if net["domains"]["all"]:
        domain_lines = "\n".join(f"  - {d}" for d in net["domains"]["all"][:30])
        sections.append(f"## Network Domains ({net['domains']['count']} total, showing up to 30)\n{domain_lines}")

    if net["domains"]["flagged"]:
        flagged = json.dumps(net["domains"]["flagged"], indent=2)
        sections.append(f"## Flagged / Geolocated Domains\n```json\n{flagged}\n```")

    if net["urls"]:
        url_lines = "\n".join(f"  - {u.get('url', u)}" for u in net["urls"][:20])
        sections.append(f"## Hardcoded URLs\n{url_lines}")

    if extracted["manifest_issues"]:
        high = [i for i in extracted["manifest_issues"] if i["severity"] == "high"]
        warnings = [i for i in extracted["manifest_issues"] if i["severity"] == "warning"]
        manifest_text = ""
        for item in high:
            manifest_text += f"  [HIGH] {item['title']}: {item['description']}\n"
        for item in warnings[:10]:
            manifest_text += f"  [WARN] {item['title']}: {item['description']}\n"
        sections.append(f"## AndroidManifest.xml Issues\n{manifest_text}")

    if extracted["code_issues"]:
        code_text = ""
        for item in extracted["code_issues"][:20]:
            code_text += f"  [{item['severity'].upper()}] {item['title']}: {item['description']}\n"
        sections.append(f"## Static Code Analysis Issues\n{code_text}")

    exported = extracted["exported_count"]
    exported_text = ", ".join(f"{k}: {v}" for k, v in exported.items() if v > 0)
    if exported_text:
        sections.append(f"## Exported Components (accessible to other apps)\n  {exported_text}")

    if net["network_security_issues"]:
        ns_text = "\n".join(f"  - {i}" for i in net["network_security_issues"][:10])
        sections.append(f"## Network Security Config Issues\n{ns_text}")

    if net["certificate_issues"]:
        cert_text = "\n".join(f"  - {i}" for i in net["certificate_issues"])
        sections.append(f"## Certificate Issues\n{cert_text}")

    prompt_body = "\n\n".join(sections)

    prompt_body += """

---

Based on all findings above, produce a structured security report with these sections:

### 1. Executive Summary
2–3 sentences. What is this app, what does it appear to do, and what is the overall risk level (Low / Medium / High / Critical)?

### 2. Top Security Findings
List the most important issues in priority order. For each: what the issue is, why it matters, and how severe it is.

### 3. Privacy Concerns
What user data could this app access, collect, or share? Be specific about which permissions and SDKs are involved.

### 4. Data & Network Activity
Where does this app send data? List domains and servers of concern. Flag anything that looks like analytics, advertising, or unexpected data collection. Note any geographic concerns.

### 5. Red Flags
Anything that strongly suggests malicious intent, spyware behaviour, excessive data harvesting, or poor security practice. Be direct.

### 6. Recommendations
If someone needs to decide whether to allow this app on a device or network, what should they do? Plain-English action items.

Be direct and avoid unnecessary jargon. If something is genuinely not a concern, say so — don't pad the report.
"""

    return prompt_body
