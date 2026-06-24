"""
User data directory resolution — platform standard locations.

  macOS   ~/Library/Application Support/APK-JTM/
  Windows %APPDATA%\APK-JTM\
  Linux   $XDG_DATA_HOME/apk-jtm/   (default ~/.local/share/apk-jtm/)
"""

import os
import sys
from pathlib import Path

_APP_NAME_MAC_WIN = "APK-JTM"
_APP_NAME_LINUX   = "apk-jtm"


def _user_data_dir() -> Path:
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / _APP_NAME_MAC_WIN
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA") or (Path.home() / "AppData" / "Roaming"))
        return base / _APP_NAME_MAC_WIN
    # Linux / other — XDG Base Directory spec
    xdg = os.environ.get("XDG_DATA_HOME") or (Path.home() / ".local" / "share")
    return Path(xdg) / _APP_NAME_LINUX


DATA_DIR    = _user_data_dir()
ENV_PATH    = DATA_DIR / ".env"
REPORTS_DIR = DATA_DIR / "reports"
