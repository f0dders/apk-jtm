import json


def build_analysis_prompt(extracted: dict, language: str = "British English") -> str:
    app   = extracted["app"]
    score = extracted["security_score"]
    cvss  = extracted["average_cvss"]

    sections = []

    # ── System role + context block ──────────────────────────────────────────
    sections.append(f"""You are an expert mobile application security analyst. Your job is to produce a clear, plain-{language} security report for a non-technical reader — someone who needs to decide whether this app is safe to use or allow on their network.

**Write the entire report in {language}.** This applies to spelling, phrasing, and idiom throughout — including section headings you generate content for, findings, and the summary.

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

    apkid = extracted.get("apkid", {})
    if apkid.get("available"):
        lines = []
        if apkid.get("compilers"):
            lines.append(f"- **Compiler(s):** {', '.join(apkid['compilers'])}")
        if apkid.get("packers"):
            flag = " ⚠ KNOWN MALWARE PACKER" if apkid.get("known_malware_packer") else ""
            lines.append(f"- **Packer(s) detected:** {', '.join(apkid['packers'])}{flag}")
        if apkid.get("obfuscators"):
            flag = " ⚠ SUSPICIOUS" if apkid.get("suspicious_obfuscator") else " (normal)"
            lines.append(f"- **Obfuscator(s):** {', '.join(apkid['obfuscators'])}{flag}")
        if apkid.get("anti_vm"):
            lines.append(f"- **Anti-emulator techniques:** {', '.join(apkid['anti_vm'])} — app detects virtual environments (may refuse to run on emulators/test devices)")
        if apkid.get("anti_debug"):
            lines.append(f"- **Anti-debug/disassembly:** {', '.join(apkid['anti_debug'] + apkid.get('anti_disassembly', []))}")
        if apkid.get("abnormal"):
            lines.append(f"- **Abnormal DEX features:** {', '.join(apkid['abnormal'])}")
        if apkid.get("repackaged"):
            lines.append("- **Repackaging detected:** compiled via dex2jar, suggesting this APK was rebuilt from a JAR ⚠")
        if lines:
            sections.append("## Packer & Obfuscation Analysis (APKiD)\n" + "\n".join(lines))
        else:
            compiler = ", ".join(apkid.get("compilers", [])) or "standard toolchain"
            sections.append(f"## Packer & Obfuscation Analysis (APKiD)\n- **Clean:** No packers, obfuscators, anti-VM, or anti-debug techniques detected. Compiler: {compiler}.")
    elif apkid.get("available") is False and not apkid.get("reason", "").startswith("APKiD not installed"):
        sections.append(f"## Packer & Obfuscation Analysis (APKiD)\n- APKiD scan failed: {apkid.get('reason', 'unknown error')}")

    quark = extracted.get("quark", {})
    if quark.get("available"):
        if quark.get("top_crimes"):
            lines = [f"- **Quark-Engine threat level:** {quark.get('threat_level', 'Unknown')} ({quark.get('matched_count', 0)} behaviour patterns matched at ≥80% confidence)"]
            for c in quark["top_crimes"]:
                labels = f" _(tags: {', '.join(c['label'])})_" if c.get("label") else ""
                lines.append(f"- {c['crime']} — confidence {c['confidence']}{labels}")
            sections.append("## Behavioural Analysis (Quark-Engine)\n" + "\n".join(lines))
        else:
            sections.append(f"## Behavioural Analysis (Quark-Engine)\n- **Clean:** No malware-associated behaviour patterns matched. Threat level: {quark.get('threat_level', 'Low Risk')}.")
    elif quark.get("available") is False and not quark.get("reason", "").startswith(("Quark-Engine not installed", "Quark-Engine rules not found")):
        sections.append(f"## Behavioural Analysis (Quark-Engine)\n- Quark-Engine scan failed: {quark.get('reason', 'unknown error')}")

    locations = net.get("server_locations", {})
    if locations:
        loc_lines = "\n".join(
            f"- **{country}**: {', '.join(domains[:6])}{', …' if len(domains) > 6 else ''}"
            for country, domains in locations.items()
        )
        sections.append(f"## Server Locations (MobSF geolocation data)\n{loc_lines}")

    # ── Instructions ─────────────────────────────────────────────────────────
    prompt_body = "\n\n".join(sections)

    prompt_body += f"""

---

**CRITICAL OUTPUT REQUIREMENT — read this first, before writing anything else:**
Your response MUST end with exactly these two lines as the very last lines, with nothing after them:
VERDICT: <LOW|MEDIUM|HIGH|CRITICAL>
SUMMARY: <one plain-English sentence — no jargon, no permission names>

Example of correct ending:
VERDICT: HIGH
SUMMARY: This app requests access to your location, contacts, and microphone but its purpose does not explain why, which is a serious privacy concern.

Do not add any text, punctuation, or blank lines after the SUMMARY line. This is a machine-readable tag and must be exact.

---

**Unknown app rule:** If you do not recognise this app from your training data — no public record, no known developer, no verifiable open-source repository — treat it as potentially malicious by default. An unknown app with sensitive permissions should be rated **HIGH** or **CRITICAL** unless the static analysis findings are extremely clean. The burden of proof is on the app to appear trustworthy, not on the analyst to find evidence of harm.

---

Write a security report with exactly these seven sections. Use `##` for section headings.

## App Context & Reputation
Do you recognise this app? State clearly:
- What it is and what it's designed to do
- Who develops it and whether it is open-source, commercial, or unknown
- Its general reputation in the security and developer community (trusted, controversial, unknown, known malware, etc.)
- Whether the permissions and behaviours flagged below are **expected for this type of app** or genuinely suspicious

If you do not recognise the app at all, say so plainly and note that this alone increases the risk rating. This section should give the reader crucial context before they see the findings.

## Executive Summary
2–3 sentences. State what the app does (or appears to do) and give an overall risk verdict in bold: **CRITICAL**, **HIGH**, **MEDIUM**, or **LOW**. This verdict must account for both the static analysis findings AND the app's known reputation and purpose — a trusted open-source tool with expected system permissions should not be rated the same as an unknown app with the same permissions. If your contextual verdict differs from the raw MobSF score, explicitly note this and explain why in one sentence.

## Top Security Findings
The most significant issues in descending priority. For each, use this format:

**🔴 CRITICAL / 🟠 HIGH / 🟡 MEDIUM / 🟢 LOW — Finding title**
One or two sentences: what it is, why it matters, and — importantly — whether it is concerning given this app's known purpose or whether it is expected behaviour.

Include up to 8 findings. For any finding that is a known false positive or expected behaviour for this app type, mark it explicitly: add *(expected for this app type)* or *(likely false positive)* after the severity label.

## Privacy Concerns
What personal data can this app access, collect, or share? Be specific about permissions and which ones are justified by the app's purpose vs which are unexplained. 4–6 bullet points.

## Network & Data Activity
Where does the app send data? Flag anything unexpected. Note if connections are consistent with the app's stated purpose. 4–6 bullet points.

## Geographic & Server Analysis
Where are this app's servers hosted, and what does that mean for user privacy? Use the Server Locations data above. Cover:
- Which countries host the majority of the app's network infrastructure, and name them explicitly
- Whether those countries have strong data protection laws (e.g. EU/GDPR, UK/DPA, Canada/PIPEDA) or weak/absent protections
- Flag any servers in countries with mandatory government data access laws or known state surveillance programmes (e.g. China, Russia, Iran) — explain what that means in practice for the user's data
- Whether the developer's apparent country of origin matches the server locations or raises questions
- Note if the jurisdiction is unclear (no geolocation data available)
- Conclude with a geographic risk rating: **Low** (GDPR/Five Eyes jurisdictions with strong privacy laws), **Medium** (mixed or unclear jurisdictions), or **High** (countries with poor data protection or active state surveillance)
3–5 bullet points.

## Packer & Obfuscation Analysis
Only include this section if APKiD data is present above. Explain in plain English what the findings mean.

**Verdict escalation rule (mandatory):** If APKiD detected a **known malware packer** (e.g. Bangcle, SecNeo, Jiagu, DexProtect), the overall verdict MUST be HIGH or CRITICAL regardless of other findings — these packers are used almost exclusively to hide malicious behaviour.

Cover:
- Whether a packer was found, what it is, and whether it is associated with malware or is a standard commercial code protector. Most legitimate consumer apps are NOT packed.
- Anti-emulator/anti-VM techniques: note clearly that this means **the app may refuse to run on emulators or virtual devices** (e.g. during testing or security research). For banking or DRM apps this is normal; for unknown apps it warrants scrutiny.
- Anti-debug techniques if present: the app resists reverse engineering, which is common in paid apps protecting IP but unusual in open-source or free apps.
- Whether the compiler fingerprint is normal for this type of app.
- If everything is clean: say so plainly — "No packers, obfuscators, or evasion techniques detected; standard compiler toolchain."

Keep this section to 2–4 bullet points. If APKiD data is not present, omit this section entirely.

## Behavioural Analysis
Only include this section if Quark-Engine data is present above. Quark-Engine matches API-call patterns against a database of behaviours associated with known malware families (banking trojans, spyware, persistence/evasion techniques, etc).

**Important — do not blindly trust the threat level:** Quark-Engine's "threat level" is a mechanical score based on how many behaviour patterns matched, with no awareness of what the app actually is. Many completely legitimate apps — especially system tools, package managers, and apps with broad permissions for a good reason — trigger a "High Risk" or "Moderate Risk" threat level purely because they use APIs (reflection, content resolvers, background services) that are also used by malware. Unlike the APKiD malware-packer rule, **there is no mandatory verdict escalation tied to Quark's threat level** — you must reason about each matched behaviour in context, exactly as you do for permissions and code findings elsewhere in this report.

Cover:
- List the matched behaviours that are genuinely noteworthy given what this app is — mark any that are expected/benign for this app type as *(expected for this app type)*
- If a matched behaviour combination looks like a real red flag (e.g. reading SMS + sending network requests + hiding the app icon, in an app with no legitimate reason to do so), call it out clearly and factor it into your verdict
- If everything matched is explainable by the app's normal function, say so plainly — do not manufacture concern from mechanical pattern matches
- If no behaviours matched (clean): say so plainly — "No malware-associated behaviour patterns detected."

Keep this section to 2–4 bullet points. If Quark-Engine data is not present, omit this section entirely.

## Red Flags
Unambiguous list of anything that suggests malicious behaviour, spyware, or dangerously poor security practice — **after accounting for the app's known purpose**. If the app is unknown or unverifiable, list that explicitly as a red flag. If nothing rises to this level, write one sentence: "No significant red flags identified."

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
- Write the entire report in {language}, plain and jargon-light — briefly explain any technical terms

**Reminder — your response MUST end with exactly these two lines, nothing after them:**
VERDICT: <LOW|MEDIUM|HIGH|CRITICAL>
SUMMARY: <one plain-English sentence>
"""

    return prompt_body
