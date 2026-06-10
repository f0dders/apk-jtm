#!/usr/bin/env python3
"""Single entry point: starts the server and opens the browser."""

import os
import sys
import time
import threading
import webbrowser

HOST = "127.0.0.1"
PORT = int(os.getenv("PORT", 7842))
URL = f"http://{HOST}:{PORT}"


def open_browser():
    """Poll until the server is accepting requests, then open the browser."""
    import urllib.request
    print(f"  Waiting for server on port {PORT}...")
    for i in range(40):          # up to 20 seconds
        time.sleep(0.5)
        try:
            urllib.request.urlopen(f"http://{HOST}:{PORT}/api/config", timeout=1)
            print(f"  Server ready. Opening {URL}\n")
            webbrowser.open(URL)
            return
        except Exception:
            pass
    print(f"\n  [ERROR] Server did not start within 20 seconds.")
    print(f"  Check the error output above for details.")


def check_imports():
    """Verify all server dependencies are importable before handing off to uvicorn."""
    missing = []
    for pkg, imp in [
        ("fastapi",          "fastapi"),
        ("uvicorn",          "uvicorn"),
        ("sse-starlette",    "sse_starlette"),
        ("python-multipart", "multipart"),
        ("python-dotenv",    "dotenv"),
        ("requests",         "requests"),
        ("rich",             "rich"),
    ]:
        try:
            __import__(imp)
        except ImportError:
            missing.append(pkg)
    return missing


if __name__ == "__main__":
    print(f"\n  APK-JTM — Just tell me if it's dodgy!")
    print(f"  ─────────────────────────────────────")

    missing = check_imports()
    if missing:
        print(f"\n  [ERROR] Missing dependencies: {', '.join(missing)}")
        print(f"  Run:  pip install -r requirements.txt")
        print(f"  Or re-run the launcher script.\n")
        sys.exit(1)

    import uvicorn
    print(f"  Starting server at {URL}")

    threading.Thread(target=open_browser, daemon=True).start()

    uvicorn.run(
        "server:app",
        host=HOST,
        port=PORT,
        reload=False,
        log_level="error",   # shows import errors and crashes, not routine access logs
    )
