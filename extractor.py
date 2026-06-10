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


def _as_list(value, default=None) -> list:
    """Safely coerce a MobSF field to a list regardless of what version returned."""
    if isinstance(value, list):
        return value
    if value is None or isinstance(value, (int, float, bool)):
        return default if default is not None else []
    return default if default is not None else []


def _as_dict(value, default=None) -> dict:
    """Safely coerce a MobSF field to a dict."""
    if isinstance(value, dict):
        return value
    return default if default is not None else {}


def extract(report: dict) -> dict:
    permissions = _as_dict(report.get("permissions"))
    dangerous_perms = [
        {"name": k, "description": v.get("description", ""), "status": v.get("status", "")}
        for k, v in permissions.items()
        if isinstance(v, dict) and (k in DANGEROUS_PERMISSIONS or v.get("status") == "dangerous")
    ]

    manifest_issues = _extract_manifest_issues(report)
    code_issues = _extract_code_issues(report)
    network_findings = _extract_network(report)
    trackers = _extract_trackers(report)
    secrets = _as_list(report.get("secrets"))[:30]

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
        "activities": _as_list(report.get("activities")),
        "services": _as_list(report.get("services")),
        "receivers": _as_list(report.get("receivers")),
        "providers": _as_list(report.get("providers")),
        "exported_count": _count_exported(report),
    }


def _extract_manifest_issues(report: dict) -> list:
    issues = []
    manifest = report.get("manifest_analysis", {})

    if isinstance(manifest, dict):
        for severity in ("high", "warning", "info"):
            for item in _as_list(manifest.get(severity)):
                if isinstance(item, dict):
                    issues.append({
                        "severity": severity,
                        "title": item.get("title", ""),
                        "description": item.get("description", ""),
                    })
    elif isinstance(manifest, list):
        for item in manifest:
            if isinstance(item, dict):
                issues.append({
                    "severity": item.get("severity", "info"),
                    "title": item.get("title", item.get("rule", "")),
                    "description": item.get("description", ""),
                })

    return issues


def _extract_code_issues(report: dict) -> list:
    issues = []
    code = _as_dict(report.get("code_analysis"))

    findings = _as_dict(code.get("findings", code))
    for key, value in findings.items():
        if not isinstance(value, dict):
            continue
        severity = _as_dict(value.get("metadata")).get("severity", "").lower()
        if severity not in ("high", "warning", "good"):
            severity = value.get("severity", "info").lower()
        if severity in ("high", "warning"):
            issues.append({
                "severity": severity,
                "title": key,
                "description": _as_dict(value.get("metadata")).get("description", value.get("description", "")),
                "files": list(_as_dict(value.get("files")).keys())[:5],
            })

    return issues[:40]


def _extract_network(report: dict) -> dict:
    domains = _as_dict(report.get("domains"))
    urls = _as_list(report.get("urls"))
    emails = _as_list(report.get("emails"))
    network_security = report.get("network_security", {})

    flagged_domains = {
        domain: info for domain, info in domains.items()
        if isinstance(info, dict) and (info.get("bad") == "yes" or info.get("geolocation"))
    }

    cert_analysis = _as_dict(report.get("certificate_analysis"))
    cert_issues = _as_list(cert_analysis.get("certificate_findings"))[:10]

    server_locations = _extract_server_locations(domains)

    return {
        "domains": {
            "all": list(domains.keys())[:50],
            "flagged": flagged_domains,
            "count": len(domains),
        },
        "server_locations": server_locations,
        "urls": urls[:30],
        "emails": emails[:20],
        "network_security_issues": network_security if isinstance(network_security, list) else [],
        "certificate_issues": cert_issues,
    }


def _extract_server_locations(domains: dict) -> dict:
    """Build a country → [domains] mapping from MobSF geolocation data."""
    countries: dict[str, list[str]] = {}
    for domain, info in domains.items():
        if not isinstance(info, dict):
            continue
        geo = info.get("geolocation")
        if not isinstance(geo, dict):
            continue
        country = (
            geo.get("country_long")
            or geo.get("country")
            or geo.get("country_short", "")
        ).strip()
        if country and country.upper() not in ("", "N/A", "UNKNOWN"):
            countries.setdefault(country, []).append(domain)
    # Sort by number of domains descending
    return dict(sorted(countries.items(), key=lambda kv: -len(kv[1])))


def _extract_trackers(report: dict) -> list:
    trackers = report.get("trackers", {})
    if isinstance(trackers, dict):
        # MobSF may return detected_trackers as a list of names or as an int count
        detected = trackers.get("detected_trackers", [])
        return _as_list(detected)
    return _as_list(trackers)


def _count_exported(report: dict) -> dict:
    counts = {}
    for component in ("activities", "services", "receivers", "providers"):
        items = _as_list(report.get(component))
        counts[component] = sum(
            1 for item in items
            if isinstance(item, dict) and item.get("exported") == "true"
        )
    return counts
