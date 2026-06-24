# APK-JTM — Copyright (C) 2026 f0dders
# This program is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License v3 as published by the
# Free Software Foundation. See the LICENSE file for details.
"""
FastAPI web server. Handles:
  - Static file serving
  - Config wizard (read/write .env)
  - APK upload + MobSF scanning
  - AI analysis with SSE streaming
  - Report listing and serving
"""

from __future__ import annotations

import asyncio
import json
import os
import uuid
from pathlib import Path
from typing import AsyncIterator

from dotenv import dotenv_values, load_dotenv
from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sse_starlette.sse import EventSourceResponse

load_dotenv()

from version import VERSION  # noqa: E402

app = FastAPI(title="APK Security Analyser")

REPORTS_DIR = Path("reports")
REPORTS_DIR.mkdir(exist_ok=True)

UPLOADS_DIR = Path("uploads")
UPLOADS_DIR.mkdir(exist_ok=True)

# In-memory store: scan_id → asyncio.Queue of SSE events
_scan_queues: dict[str, asyncio.Queue] = {}

ENV_PATH = Path(".env")

PROVIDERS = ["ollama", "lmstudio", "claude", "openai", "gemini", "groq", "mistral", "openrouter"]


# ---------------------------------------------------------------------------
# Static files + SPA
# ---------------------------------------------------------------------------

app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/", response_class=HTMLResponse)
async def index():
    return FileResponse("static/index.html")


@app.get("/reports/{filename}")
async def serve_report(filename: str):
    path = REPORTS_DIR / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail="Report not found")
    media = "text/html" if filename.endswith(".html") else "text/markdown"
    return FileResponse(path, media_type=media)


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

@app.get("/api/config")
async def get_config():
    env = dotenv_values(ENV_PATH) if ENV_PATH.exists() else {}
    return {
        "configured": bool(env.get("MOBSF_API_KEY") and env.get("PROVIDER")),
        "mobsf_url": env.get("MOBSF_URL", "http://localhost:8000"),
        "mobsf_key_set": bool(env.get("MOBSF_API_KEY")),
        "provider": env.get("PROVIDER", "ollama"),
        "ollama_url": env.get("OLLAMA_URL", "http://localhost:11434"),
        "ollama_model": env.get("OLLAMA_MODEL", "qwen2.5-coder:32b"),
        "lmstudio_url": env.get("LM_STUDIO_URL", "http://localhost:1234"),
        "lmstudio_model": env.get("LM_STUDIO_MODEL", ""),
        "claude_key_set": bool(env.get("ANTHROPIC_API_KEY")),
        "claude_model": env.get("CLAUDE_MODEL", "claude-sonnet-4-6"),
        "openai_key_set": bool(env.get("OPENAI_API_KEY")),
        "openai_model": env.get("OPENAI_MODEL", "gpt-4o"),
        "gemini_key_set": bool(env.get("GEMINI_API_KEY")),
        "gemini_model": env.get("GEMINI_MODEL", "gemini-1.5-pro"),
        "groq_key_set": bool(env.get("GROQ_API_KEY")),
        "groq_model": env.get("GROQ_MODEL", "llama-3.3-70b-versatile"),
        "mistral_key_set": bool(env.get("MISTRAL_API_KEY")),
        "mistral_model": env.get("MISTRAL_MODEL", "mistral-large-latest"),
        "openrouter_key_set": bool(env.get("OPENROUTER_API_KEY")),
        "openrouter_model": env.get("OPENROUTER_MODEL", "anthropic/claude-sonnet-4-6"),
    }


@app.post("/api/config")
async def save_config(payload: dict):
    existing = dotenv_values(ENV_PATH) if ENV_PATH.exists() else {}
    merged = {**existing, **{k: v for k, v in payload.items() if v is not None and v != ""}}

    lines = [f'{k}={v}' for k, v in merged.items()]
    ENV_PATH.write_text("\n".join(lines) + "\n")
    load_dotenv(override=True)
    return {"ok": True}


@app.get("/api/providers")
async def list_providers():
    return {"providers": PROVIDERS}


@app.get("/api/version")
async def get_version():
    return {"version": VERSION}


@app.get("/api/ollama/models")
async def list_ollama_models():
    """Fetch available models from Ollama."""
    import requests
    env = dotenv_values(ENV_PATH) if ENV_PATH.exists() else {}
    base = env.get("OLLAMA_URL", "http://localhost:11434")
    try:
        r = requests.get(f"{base}/api/tags", timeout=3)
        r.raise_for_status()
        models = [m["name"] for m in r.json().get("models", [])]
        return {"models": models}
    except Exception:
        return {"models": [], "error": "Ollama not reachable"}


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------

@app.get("/api/reports")
async def list_reports():
    reports = []
    for path in sorted(REPORTS_DIR.glob("report_*.html"), key=lambda p: p.stat().st_mtime, reverse=True):
        meta = {}
        meta_path = path.with_suffix("").with_suffix(".meta.json")
        if meta_path.exists():
            try:
                meta = json.loads(meta_path.read_text())
            except Exception:
                pass
        reports.append({
            "name":      path.name,
            "size":      path.stat().st_size,
            "modified":  path.stat().st_mtime,
            "url":       f"/reports/{path.name}",
            **meta,
        })
    return {"reports": reports}


@app.delete("/api/reports/{filename}")
async def delete_report(filename: str):
    if ".." in filename or "/" in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")
    deleted = []
    for ext in (".html", ".md", ".meta.json"):
        stem = filename.removesuffix(".html")
        p = REPORTS_DIR / f"{stem}{ext}"
        if p.exists():
            p.unlink()
            deleted.append(p.name)
    if not deleted:
        raise HTTPException(status_code=404, detail="Report not found")
    return {"deleted": deleted}


@app.post("/api/reports/{filename}/rerun")
async def rerun_report(filename: str, payload: dict, background_tasks: BackgroundTasks):
    """Re-analyse an existing report with a different AI provider/model."""
    if ".." in filename or "/" in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")

    stem = filename.removesuffix(".html")
    meta_path = REPORTS_DIR / f"{stem}.meta.json"
    if not meta_path.exists():
        raise HTTPException(status_code=404, detail="Report metadata not found")

    try:
        meta = json.loads(meta_path.read_text())
    except Exception:
        raise HTTPException(status_code=500, detail="Could not read report metadata")

    md5 = meta.get("md5")
    if not md5:
        raise HTTPException(status_code=400, detail="No MobSF hash stored for this report — cannot re-run without the original APK")

    scan_id = str(uuid.uuid4())
    queue: asyncio.Queue = asyncio.Queue()
    _scan_queues[scan_id] = queue

    background_tasks.add_task(
        run_scan,
        scan_id=scan_id,
        apk_path=None,
        report_path=None,
        provider_override=payload.get("provider"),
        model_override=payload.get("model"),
        mobsf_hash=md5,
        prior_apkid=meta.get("apkid_full"),
    )

    return {"scan_id": scan_id}


# ---------------------------------------------------------------------------
# Scanning
# ---------------------------------------------------------------------------

@app.post("/api/scan/upload")
async def start_scan(
    background_tasks: BackgroundTasks,
    apk: UploadFile = File(None),
    report_json: UploadFile = File(None),
    provider_override: str = Form(None),
    model_override: str = Form(None),
):
    scan_id = str(uuid.uuid4())
    queue: asyncio.Queue = asyncio.Queue()
    _scan_queues[scan_id] = queue

    apk_path = None
    report_path = None

    if apk and apk.filename:
        apk_path = UPLOADS_DIR / f"{scan_id}_{apk.filename}"
        content = await apk.read()
        apk_path.write_bytes(content)

    if report_json and report_json.filename:
        report_path = UPLOADS_DIR / f"{scan_id}_{report_json.filename}"
        content = await report_json.read()
        report_path.write_bytes(content)

    if not apk_path and not report_path:
        raise HTTPException(status_code=400, detail="Provide an APK or MobSF JSON report")

    background_tasks.add_task(
        run_scan,
        scan_id=scan_id,
        apk_path=str(apk_path) if apk_path else None,
        report_path=str(report_path) if report_path else None,
        provider_override=provider_override,
        model_override=model_override,
    )

    return {"scan_id": scan_id}


@app.get("/api/scan/{scan_id}/stream")
async def scan_stream(scan_id: str):
    if scan_id not in _scan_queues:
        raise HTTPException(status_code=404, detail="Scan not found")

    async def event_generator() -> AsyncIterator[dict]:
        queue = _scan_queues[scan_id]
        while True:
            event = await queue.get()
            yield event
            if event.get("event") in ("complete", "error"):
                _scan_queues.pop(scan_id, None)
                break

    return EventSourceResponse(event_generator())


# ---------------------------------------------------------------------------
# Background scan worker
# ---------------------------------------------------------------------------

def _send(queue: asyncio.Queue, event: str, data: dict | str):
    payload = data if isinstance(data, str) else json.dumps(data)
    asyncio.get_event_loop().call_soon_threadsafe(
        queue.put_nowait, {"event": event, "data": payload}
    )


async def run_scan(
    scan_id: str,
    apk_path: str | None,
    report_path: str | None,
    provider_override: str | None,
    model_override: str | None,
    mobsf_hash: str | None = None,
    prior_apkid: dict | None = None,
):
    queue = _scan_queues.get(scan_id)
    if not queue:
        return

    def send(event: str, data: dict | str):
        _send(queue, event, data)

    try:
        load_dotenv(override=True)
        env = dict(os.environ)

        # Build provider
        from providers import build_provider
        provider_name = provider_override or env.get("PROVIDER", "ollama")
        try:
            provider = build_provider(provider_name, model_override, env)
        except ValueError as e:
            send("error", {"message": str(e)})
            return

        send("progress", {"stage": "provider", "message": f"Using {provider.name} / {provider.model}"})

        # Load or scan
        raw_report = None
        # Re-runs reuse APKiD results from the original scan (APK unchanged)
        apkid_results: dict = prior_apkid if prior_apkid else {"available": False, "reason": "APKiD only runs on direct APK scans"}

        if report_path:
            send("progress", {"stage": "loading", "message": "Loading MobSF report..."})
            raw_report = json.loads(Path(report_path).read_text())
            send("progress", {"stage": "loading", "message": "Report loaded."})
        elif mobsf_hash:
            mobsf_url = env.get("MOBSF_URL", "http://localhost:8000")
            mobsf_key = env.get("MOBSF_API_KEY", "")
            if not mobsf_key:
                send("error", {"message": "MOBSF_API_KEY not configured. Open Settings to add it."})
                return
            send("progress", {"stage": "loading", "message": "Fetching scan data from MobSF..."})
            from mobsf_client import MobSFClient
            client = MobSFClient(mobsf_url, mobsf_key)
            try:
                raw_report = await asyncio.to_thread(client.get_report, mobsf_hash)
                raw_report = await asyncio.to_thread(client._merge_scorecard, raw_report, mobsf_hash)
            except Exception as e:
                send("error", {"message": f"MobSF error fetching cached scan: {e}"})
                return
            send("progress", {"stage": "loading", "message": "Scan data loaded from MobSF ⚡"})
            # Surface APKiD stage for re-runs — reuse results from original scan
            if apkid_results.get("available"):
                flags = []
                if apkid_results.get("known_malware_packer"): flags.append("⚠ malware packer detected")
                elif apkid_results.get("has_packer"):          flags.append("packer detected")
                if apkid_results.get("has_anti_vm"):           flags.append("anti-emulator")
                if apkid_results.get("has_anti_debug"):        flags.append("anti-debug")
                msg = "Reusing APKiD results from original scan" + (f" — {', '.join(flags)}" if flags else " — no packers detected")
                send("progress", {"stage": "apkid", "message": msg})
            else:
                send("progress", {"stage": "apkid", "message": "No APKiD data from original scan (APK needed to run APKiD)"})
        else:
            mobsf_url = env.get("MOBSF_URL", "http://localhost:8000")
            mobsf_key = env.get("MOBSF_API_KEY", "")
            if not mobsf_key:
                send("error", {"message": "MOBSF_API_KEY not configured. Open Settings to add it."})
                return

            send("progress", {"stage": "upload", "message": f"Uploading {Path(apk_path).name} to MobSF..."})

            from mobsf_client import MobSFClient
            client = MobSFClient(mobsf_url, mobsf_key)

            # Run MobSF scan and APKiD in parallel
            from apkid_client import run_apkid

            send("progress", {"stage": "apkid", "message": "Running packer/obfuscation analysis (APKiD)..."})

            try:
                raw_report, apkid_results = await asyncio.gather(
                    asyncio.to_thread(client.upload_and_scan, apk_path),
                    asyncio.to_thread(run_apkid, apk_path),
                )
            except Exception as e:
                send("error", {"message": f"MobSF error: {e}"})
                return

            if apkid_results.get("available"):
                flags = []
                if apkid_results.get("known_malware_packer"): flags.append("⚠ malware packer detected")
                elif apkid_results.get("has_packer"):          flags.append("packer detected")
                if apkid_results.get("has_anti_vm"):           flags.append("anti-VM")
                if apkid_results.get("has_anti_debug"):        flags.append("anti-debug")
                msg = "APKiD complete" + (f" — {', '.join(flags)}" if flags else " — no packers detected")
                send("progress", {"stage": "apkid", "message": msg})
            else:
                send("progress", {"stage": "apkid", "message": apkid_results.get("reason", "APKiD skipped")})

            if raw_report.get("_cached"):
                send("progress", {"stage": "scan", "message": "Already scanned — using cached MobSF results ⚡"})
            else:
                send("progress", {"stage": "scan", "message": "Scan complete."})

        send("progress", {"stage": "extract", "message": "Extracting key findings..."})
        import extractor
        extracted = extractor.extract(raw_report)
        extracted["apkid"] = apkid_results

        app_info = extracted["app"]
        send("progress", {
            "stage": "extracted",
            "message": "Findings extracted.",
            "app_name": app_info["name"],
            "package": app_info["package"],
            "version": app_info["version"],
            "score": extracted["security_score"],
            "dangerous_perms": len(extracted["dangerous_permissions"]),
            "trackers": len(extracted["trackers"]),
            "domains": extracted["network"]["domains"]["count"],
            "secrets": len(extracted["secrets"]),
        })

        send("progress", {"stage": "analysis", "message": f"Sending to {provider.name}..."})

        from prompts import build_analysis_prompt
        prompt = build_analysis_prompt(extracted)

        ai_chunks = []
        chunk_queue: asyncio.Queue = asyncio.Queue()

        async def _feed_queue():
            """Run the synchronous provider stream in a thread, putting chunks on the queue."""
            loop = asyncio.get_event_loop()
            try:
                def _run():
                    try:
                        for chunk in provider.stream(prompt):
                            loop.call_soon_threadsafe(chunk_queue.put_nowait, ("chunk", chunk))
                    except Exception as exc:
                        loop.call_soon_threadsafe(chunk_queue.put_nowait, ("error", str(exc)))
                    finally:
                        loop.call_soon_threadsafe(chunk_queue.put_nowait, ("done", None))
                await asyncio.to_thread(_run)
            except Exception as exc:
                chunk_queue.put_nowait(("error", str(exc)))

        feed_task = asyncio.create_task(_feed_queue())

        try:
            while True:
                kind, value = await asyncio.wait_for(chunk_queue.get(), timeout=120)
                if kind == "error":
                    is_rate_limit = "rate limit" in value.lower() or "rate limited" in value.lower() or "429" in value
                    send("error", {
                        "message": f"AI analysis failed: {value}",
                        "type": "rate_limit" if is_rate_limit else "error",
                        "provider": provider_name,
                    })
                    feed_task.cancel()
                    return
                if kind == "done":
                    break
                send("analysis", value)
                ai_chunks.append(value)
        except asyncio.TimeoutError:
            send("error", {
                "message": "AI analysis timed out after 2 minutes — the model may be busy or the model name is wrong.",
                "type": "timeout",
                "provider": provider_name,
            })
            feed_task.cancel()
            return

        import re as _re
        full_report_raw = "".join(ai_chunks)

        # Extract machine-readable verdict from last line before rendering
        verdict_match = _re.search(
            r'^VERDICT:\s*(LOW|MEDIUM|HIGH|CRITICAL)\s*$',
            full_report_raw, _re.IGNORECASE | _re.MULTILINE
        )
        ai_verdict = verdict_match.group(1).upper() if verdict_match else None

        summary_match = _re.search(
            r'^SUMMARY:\s*(.+)$',
            full_report_raw, _re.IGNORECASE | _re.MULTILINE
        )
        ai_summary = summary_match.group(1).strip() if summary_match else None

        # Strip both tag lines from the rendered report
        full_report = _re.sub(
            r'\n*^(VERDICT:\s*(LOW|MEDIUM|HIGH|CRITICAL)|SUMMARY:\s*.+)\s*$\n*',
            '', full_report_raw, flags=_re.IGNORECASE | _re.MULTILINE
        ).strip()

        import reporter
        from model_tier import classify as _classify_model

        # Fetch app icon from MobSF (best-effort; works for APK scans and re-runs)
        icon_b64 = None
        if not report_path and app_info.get("md5"):
            try:
                from mobsf_client import MobSFClient
                icon_client = MobSFClient(
                    env.get("MOBSF_URL", "http://localhost:8000"),
                    env.get("MOBSF_API_KEY", ""),
                )
                icon_b64 = icon_client.fetch_icon_b64(app_info["md5"])
            except Exception:
                pass

        def _label(item) -> str:
            if isinstance(item, dict):
                return (item.get("title") or item.get("name") or item.get("description") or str(item))[:80]
            return str(item)[:80]

        app_meta = {
            **app_info,
            "security_score": extracted["security_score"],
            "average_cvss": extracted["average_cvss"],
            "dangerous_perms_count": len(extracted["dangerous_permissions"]),
            "dangerous_perms_list": [
                p["name"].replace("android.permission.", "")
                for p in extracted["dangerous_permissions"]
            ],
            "trackers_count": len(extracted["trackers"]),
            "trackers_list": [_label(t) for t in extracted["trackers"]],
            "domains_count": extracted["network"]["domains"]["count"],
            "domains_list": extracted["network"]["domains"]["all"][:20],
            "secrets_count": len(extracted["secrets"]),
            "secrets_list": [_label(s) for s in extracted["secrets"][:15]],
            "code_issues_count": len(extracted["code_issues"]),
            "code_issues_list": [i.get("title", "")[:60] for i in extracted["code_issues"][:15]],
            "manifest_issues_count": len(extracted["manifest_issues"]),
            "icon_b64": icon_b64,
            "apkid": extracted.get("apkid", {}),
            "ai_provider":  provider_name,
            "ai_model":     provider.model,
            "ai_model_tier": _classify_model(provider.model),
            "ai_verdict":   ai_verdict,
            "ai_summary":   ai_summary,
            "perms_summary": _perms_plain(extracted["dangerous_permissions"]),
        }
        report_html_path = reporter.save_report(app_meta, full_report, str(REPORTS_DIR))

        send("analysis_done", {})
        send("complete", {
            "message": "Analysis complete.",
            "report_url": f"/reports/{Path(report_html_path).name}",
            "report_name": Path(report_html_path).name,
        })

    except Exception as e:
        send("error", {"message": f"Unexpected error: {e}"})


_PERM_PLAIN = {
    # Severe / alarming
    "BIND_DEVICE_ADMIN":           "full device administration",
    "BIND_ACCESSIBILITY_SERVICE":  "full device control via accessibility",
    "SYSTEM_ALERT_WINDOW":         "overlays other apps",
    # High power
    "REQUEST_INSTALL_PACKAGES":    "installs other apps",
    "MANAGE_EXTERNAL_STORAGE":     "manages all your files",
    # Privacy-sensitive comms
    "READ_SMS":                    "reads your messages",
    "SEND_SMS":                    "sends messages",
    "PROCESS_OUTGOING_CALLS":      "monitors your calls",
    "CALL_PHONE":                  "makes phone calls",
    "READ_CALL_LOG":               "reads call history",
    # Identity / accounts
    "READ_CONTACTS":               "reads your contacts",
    "WRITE_CONTACTS":              "edits your contacts",
    "GET_ACCOUNTS":                "accesses your accounts",
    "READ_PHONE_STATE":            "reads phone identity",
    # Location
    "ACCESS_BACKGROUND_LOCATION":  "tracks location in background",
    "ACCESS_FINE_LOCATION":        "tracks your precise location",
    "ACCESS_COARSE_LOCATION":      "tracks your location",
    # Sensors / media
    "CAMERA":                      "uses your camera",
    "RECORD_AUDIO":                "uses your microphone",
    "USE_BIOMETRIC":               "uses fingerprint/face ID",
    "USE_FINGERPRINT":             "uses fingerprint",
    "BODY_SENSORS":                "reads body sensors",
    "ACTIVITY_RECOGNITION":        "tracks physical activity",
    # Storage / media
    "READ_MEDIA_IMAGES":           "reads your photos",
    "READ_MEDIA_VIDEO":            "reads your videos",
    "READ_MEDIA_AUDIO":            "reads your audio",
    "READ_EXTERNAL_STORAGE":       "reads your files",
    "WRITE_EXTERNAL_STORAGE":      "writes to your files",
}


def _perms_plain(dangerous_perms: list) -> str:
    """Return a short plain-English summary of the most significant permissions."""
    seen = []
    for p in dangerous_perms:
        name = p.get("name", "").replace("android.permission.", "")
        label = _PERM_PLAIN.get(name)
        if label and label not in seen:
            seen.append(label)
        if len(seen) >= 3:
            break
    return ", ".join(seen) if seen else ""


def _poll_report(client, hash: str):
    import time
    import requests
    for _ in range(60):
        try:
            report = client.get_report(hash)
            if report.get("app_name"):
                return report
        except requests.HTTPError:
            pass
        time.sleep(3)
    raise TimeoutError("MobSF scan timed out after 3 minutes.")


def _stream_sync(provider, prompt: str) -> list[str]:
    """Collect streamed chunks in a thread (providers are synchronous)."""
    return list(provider.stream(prompt))
