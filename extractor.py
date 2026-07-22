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
        "signing": _extract_signing(report),
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


def _finding_text(item) -> str:
    """Flatten one MobSF finding to plain text.

    MobSF has shipped these as dicts, as [severity, title, description] lists,
    and as bare strings depending on version.
    """
    if isinstance(item, dict):
        return " ".join(str(v) for v in item.values())
    if isinstance(item, (list, tuple)):
        return " ".join(str(v) for v in item)
    return str(item)


def _extract_signing(report: dict) -> dict:
    """Pull explicit signing facts out of MobSF's certificate analysis.

    MobSF describes signing as free text plus a findings list, so an unsigned or
    debug-signed APK previously reached the AI with no positive signal at all —
    only the absence of a finding, which is not something a model can reason
    about. Freshly built and unpublished APKs are exactly the case this matters
    for, so the facts are surfaced explicitly instead.
    """
    cert = _as_dict(report.get("certificate_analysis"))
    info = cert.get("certificate_info")
    info_text = info if isinstance(info, str) else ""
    findings_text = " ".join(
        _finding_text(f) for f in _as_list(cert.get("certificate_findings"))
    ).lower()

    if not info_text and not findings_text:
        return {"available": False, "reason": "No certificate analysis in the MobSF report"}

    fields: dict[str, str] = {}
    for line in info_text.splitlines():
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        fields[key.strip().lower()] = value.strip()

    lowered = info_text.lower()
    if "binary is not signed" in lowered or "not signed" in findings_text:
        is_signed = False
    elif "binary is signed" in lowered or fields.get("x.509 subject"):
        is_signed = True
    else:
        is_signed = None

    versions = [
        label for label, key in (("v1", "v1 signature"), ("v2", "v2 signature"),
                                 ("v3", "v3 signature"), ("v4", "v4 signature"))
        if fields.get(key, "").lower() == "true"
    ]

    subject = fields.get("x.509 subject", "")
    issuer = fields.get("issuer", "")

    return {
        "available": True,
        "is_signed": is_signed,
        # MobSF flags the well-known Android debug key by name; a debug-signed
        # build is a strong hint the APK was never meant for distribution.
        "is_debug_signed": "debug certificate" in findings_text
                           or "androiddebugkey" in lowered,
        "is_self_signed": bool(subject and issuer and subject == issuer),
        "signature_versions": versions,
        "subject": subject,
        "issuer": issuer,
        "algorithm": fields.get("signature algorithm", ""),
    }


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
