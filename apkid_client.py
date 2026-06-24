# APK-JTM — Copyright (C) 2026 f0dders
"""
APKiD integration — identifies how an APK was compiled, packed, or obfuscated.

APKiD is a separate pip install (apkid). If it is not installed or fails,
this module returns {"available": False} and the rest of the pipeline
continues unaffected — APKiD results are supplemental, never required.
"""

import json
import subprocess


# Packers with known malware associations
_MALWARE_PACKERS = {
    "bangcle", "secneo", "jiagu", "dexprotect", "ijiami",
    "nagapt", "qihoo", "360", "baiduprotect", "tencentprotect",
}

# Obfuscators that legitimate apps don't normally use
_SUSPICIOUS_OBFUSCATORS = {"dexguard", "allatori", "dasho"}


def run_apkid(apk_path: str, timeout: int = 60) -> dict:
    """
    Run APKiD on an APK file and return a structured summary dict.

    Returns {"available": False, "reason": "..."} if APKiD is not installed
    or the scan fails, so callers can proceed gracefully without it.
    """
    try:
        result = subprocess.run(
            ["apkid", "--json", "--timeout", "30", apk_path],
            capture_output=True, text=True, timeout=timeout,
        )
        # APKiD writes JSON to stdout even on partial failures
        if result.stdout.strip():
            raw = json.loads(result.stdout)
            return _parse(raw)
    except FileNotFoundError:
        return {"available": False, "reason": "APKiD not installed — run: pip install apkid"}
    except subprocess.TimeoutExpired:
        return {"available": False, "reason": "APKiD timed out"}
    except (json.JSONDecodeError, Exception) as e:
        return {"available": False, "reason": str(e)}
    return {"available": False, "reason": "No output from APKiD"}


def _parse(raw: dict) -> dict:
    """Flatten per-DEX APKiD results into a single risk-oriented summary."""
    files = raw.get("files", {})

    merged: dict[str, set] = {}
    for _dex_name, dex_data in files.items():
        # APKiD 2.x: findings at top level OR nested under "results"
        findings = dex_data if "compiler" in dex_data else dex_data.get("results", dex_data)
        for category, items in findings.items():
            if items:
                merged.setdefault(category, set()).update(items)

    packers     = sorted(merged.get("packer", []))
    obfuscators = sorted(merged.get("obfuscator", []))
    compilers   = sorted(merged.get("compiler", []))
    anti_vm     = sorted(merged.get("anti_vm", []))
    anti_debug  = sorted(merged.get("anti_debug", []))
    anti_disasm = sorted(merged.get("anti_disassembly", []))
    abnormal    = sorted(merged.get("abnormal", []))
    manipulator = sorted(merged.get("manipulator", []))

    known_malware_packer = any(
        any(mp in p.lower() for mp in _MALWARE_PACKERS)
        for p in packers
    )
    suspicious_obfuscator = any(
        any(so in o.lower() for so in _SUSPICIOUS_OBFUSCATORS)
        for o in obfuscators
    )
    # dex2jar = APK was built/repackaged from a JAR, unusual for legitimate apps
    repackaged = any("dex2jar" in c.lower() for c in compilers)

    return {
        "available":    True,
        "apkid_version": raw.get("apkid_version", ""),
        "packers":      packers,
        "obfuscators":  obfuscators,
        "compilers":    compilers,
        "anti_vm":      anti_vm,
        "anti_debug":   anti_debug,
        "anti_disassembly": anti_disasm,
        "abnormal":     abnormal,
        "manipulator":  manipulator,
        # Pre-computed risk flags used by prompt builder and report renderer
        "has_packer":            bool(packers),
        "has_anti_vm":           bool(anti_vm),
        "has_anti_debug":        bool(anti_debug or anti_disasm),
        "has_abnormal":          bool(abnormal or manipulator),
        "known_malware_packer":  known_malware_packer,
        "suspicious_obfuscator": suspicious_obfuscator,
        "repackaged":            repackaged,
    }
