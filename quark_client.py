# APK-JTM — Copyright (C) 2026 f0dders
"""
Quark-Engine integration — behavioural malware-family scoring via API-call
pattern matching against a local rule database (~277 community rules
covering banking trojans, spyware, persistence/evasion techniques, etc).

Quark-Engine is a separate pip install (quark-engine). Its rule database is
fetched once via `freshquark` (a git clone to ~/.quark-engine/quark-rules/)
and every scan thereafter runs entirely offline against that local copy —
same shape as APKiD's bundled yara rules and MobSF's bundled tracker
signatures.

If Quark isn't installed, its rules haven't been fetched, or the scan
fails, this module returns {"available": False} and the rest of the
pipeline continues unaffected — Quark results are supplemental, never
required.
"""

import json
import subprocess
import tempfile
from pathlib import Path

# Quark's own `-o` JSON output includes every rule it checked (~277), even
# ones that didn't match at all (0% confidence) — without filtering this
# would flood the AI prompt with noise. Only surface genuine pattern
# matches.
_MIN_CONFIDENCE = 80

# Cap how many matched behaviours get passed on, sorted by weight
# (most significant first) — mirrors the capped lists in extractor.py.
_MAX_CRIMES = 15

RULES_DIR = Path.home() / ".quark-engine" / "quark-rules" / "rules"


def run_quark(apk_path: str, timeout: int = 180) -> dict:
    """
    Run Quark-Engine on an APK file and return a structured risk summary.

    Returns {"available": False, "reason": "..."} if Quark isn't installed,
    its rule database hasn't been fetched yet, or the scan fails, so
    callers can proceed gracefully without it.
    """
    if not RULES_DIR.is_dir():
        return {"available": False, "reason": "Quark-Engine rules not found — run: freshquark"}

    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
        out_path = Path(tmp.name)

    try:
        result = subprocess.run(
            ["quark", "-a", apk_path, "-o", str(out_path)],
            capture_output=True, text=True, timeout=timeout,
        )
        if not out_path.exists() or out_path.stat().st_size == 0:
            stderr_lines = (result.stderr or "").strip().splitlines()
            reason = stderr_lines[-1] if stderr_lines else "No output from Quark-Engine"
            return {"available": False, "reason": reason}
        raw = json.loads(out_path.read_text())
        return _parse(raw)
    except FileNotFoundError:
        return {"available": False, "reason": "Quark-Engine not installed — run: pip install quark-engine && freshquark"}
    except subprocess.TimeoutExpired:
        return {"available": False, "reason": "Quark-Engine timed out"}
    except Exception as e:
        return {"available": False, "reason": str(e)}
    finally:
        out_path.unlink(missing_ok=True)


def _confidence_pct(value) -> int:
    try:
        return int(str(value).rstrip("%"))
    except ValueError:
        return 0


def _parse(raw: dict) -> dict:
    """Reduce Quark's full rule-by-rule output (every rule checked, matched
    or not) down to the behaviours actually matched with meaningful
    confidence, sorted by weight."""
    crimes = raw.get("crimes", [])

    matched = [
        {
            "crime":      c.get("crime", ""),
            "label":      c.get("label", []),
            "confidence": c.get("confidence", "0%"),
            "weight":     c.get("weight", 0),
        }
        for c in crimes
        if isinstance(c, dict) and _confidence_pct(c.get("confidence")) >= _MIN_CONFIDENCE
    ]
    matched.sort(key=lambda c: c["weight"], reverse=True)

    return {
        "available":     True,
        "threat_level":  raw.get("threat_level", ""),
        "total_score":   raw.get("total_score", 0),
        "matched_count": len(matched),
        "top_crimes":    matched[:_MAX_CRIMES],
    }
