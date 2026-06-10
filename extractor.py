"""
Extracts and structures the most security-relevant fields from a raw MobSF JSON report.
MobSF reports can be very large; this keeps LLM prompts focused and within context limits.
"""

DANGEROUS_PERMISSIONS = {
    "android.permission.READ_CONTACTS",
    "android.permission.WRITE_CONTACTS",
    "android.permission.READ_CALL_LOG",
    "android.permission.WRITE_CALL_LOG",
    "android.permission.PROCESS_OUTGOING_CALLS",
    "android.permission.READ_SMS",
    "android.permission.RECEIVE_SMS",
    "android.permission.SEND_SMS",
    "android.permission.READ_EXTERNAL_STORAGE",
    "android.permission.WRITE_EXTERNAL_STORAGE",
    "android.permission.ACCESS_FINE_LOCATION",
    "android.permission.ACCESS_COARSE_LOCATION",
    "android.permission.ACCESS_BACKGROUND_LOCATION",
    "android.permission.CAMERA",
    "android.permission.RECORD_AUDIO",
    "android.permission.READ_PHONE_STATE",
    "android.permission.CALL_PHONE",
    "android.permission.USE_BIOMETRIC",
    "android.permission.USE_FINGERPRINT",
    "android.permission.BODY_SENSORS",
    "android.permission.ACTIVITY_RECOGNITION",
    "android.permission.GET_ACCOUNTS",
    "android.permission.READ_MEDIA_IMAGES",
    "android.permission.READ_MEDIA_VIDEO",
    "android.permission.READ_MEDIA_AUDIO",
    "android.permission.MANAGE_EXTERNAL_STORAGE",
    "android.permission.REQUEST_INSTALL_PACKAGES",
    "android.permission.SYSTEM_ALERT_WINDOW",
    "android.permission.BIND_ACCESSIBILITY_SERVICE",
    "android.permission.BIND_DEVICE_ADMIN",
}


def extract(report: dict) -> dict:
    permissions = report.get("permissions", {})
    dangerous_perms = [
        {"name": k, "description": v.get("description", ""), "status": v.get("status", "")}
        for k, v in permissions.items()
        if k in DANGEROUS_PERMISSIONS or v.get("status") == "dangerous"
    ]

    manifest_issues = _extract_manifest_issues(report)
    code_issues = _extract_code_issues(report)
    network_findings = _extract_network(report)
    trackers = _extract_trackers(report)
    secrets = report.get("secrets", [])[:30]

    return {
        "app": {
            "name": report.get("app_name", "Unknown"),
            "package": report.get("package_name", ""),
            "version": report.get("version_name", ""),
            "version_code": report.get("version_code", ""),
            "min_sdk": report.get("min_sdk", ""),
            "target_sdk": report.get("target_sdk", ""),
            "file_name": report.get("file_name", ""),
            "size": report.get("size", ""),
            "md5": report.get("md5", ""),
        },
        "security_score": report.get("security_score", "N/A"),
        "average_cvss": report.get("average_cvss", "N/A"),
        "dangerous_permissions": dangerous_perms,
        "all_permissions": list(permissions.keys()),
        "manifest_issues": manifest_issues,
        "code_issues": code_issues,
        "network": network_findings,
        "trackers": trackers,
        "secrets": secrets,
        "activities": report.get("activities", []),
        "services": report.get("services", []),
        "receivers": report.get("receivers", []),
        "providers": report.get("providers", []),
        "exported_count": _count_exported(report),
    }


def _extract_manifest_issues(report: dict) -> list:
    issues = []
    manifest = report.get("manifest_analysis", {})

    if isinstance(manifest, dict):
        for severity in ("high", "warning", "info"):
            for item in manifest.get(severity, []):
                issues.append({
                    "severity": severity,
                    "title": item.get("title", ""),
                    "description": item.get("description", ""),
                })
    elif isinstance(manifest, list):
        for item in manifest:
            issues.append({
                "severity": item.get("severity", "info"),
                "title": item.get("title", item.get("rule", "")),
                "description": item.get("description", ""),
            })

    return issues


def _extract_code_issues(report: dict) -> list:
    issues = []
    code = report.get("code_analysis", {})

    if isinstance(code, dict):
        findings = code.get("findings", code)
        for key, value in findings.items():
            if not isinstance(value, dict):
                continue
            severity = value.get("metadata", {}).get("severity", "").lower()
            if severity not in ("high", "warning", "good"):
                severity = value.get("severity", "info").lower()
            if severity in ("high", "warning"):
                issues.append({
                    "severity": severity,
                    "title": key,
                    "description": value.get("metadata", {}).get("description", value.get("description", "")),
                    "files": list(value.get("files", {}).keys())[:5],
                })

    return issues[:40]


def _extract_network(report: dict) -> dict:
    domains = report.get("domains", {})
    urls = report.get("urls", [])
    emails = report.get("emails", [])
    network_security = report.get("network_security", {})

    flagged_domains = {
        domain: info for domain, info in domains.items()
        if info.get("bad") == "yes" or info.get("geolocation")
    }

    return {
        "domains": {
            "all": list(domains.keys())[:50],
            "flagged": flagged_domains,
            "count": len(domains),
        },
        "urls": urls[:30],
        "emails": emails[:20],
        "network_security_issues": network_security if isinstance(network_security, list) else [],
        "certificate_issues": report.get("certificate_analysis", {}).get("certificate_findings", [])[:10],
    }


def _extract_trackers(report: dict) -> list:
    trackers = report.get("trackers", {})
    if isinstance(trackers, dict):
        return trackers.get("detected_trackers", [])
    return trackers if isinstance(trackers, list) else []


def _count_exported(report: dict) -> dict:
    counts = {}
    for component in ("activities", "services", "receivers", "providers"):
        items = report.get(component, [])
        counts[component] = sum(
            1 for item in items
            if isinstance(item, dict) and item.get("exported") == "true"
        )
    return counts
