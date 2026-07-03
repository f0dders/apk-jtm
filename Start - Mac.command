#!/bin/bash
# APK-JTM — Mac launcher
# Double-click this file to start the app.
# On first run: right-click → Open (required once due to macOS security).

cd "$(dirname "$0")"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; RESET='\033[0m'

echo ""
echo -e "${BOLD}  APK-JTM — Just tell me if it's dodgy!${RESET}"
echo -e "  ─────────────────────────────────────"
echo ""

# ── Helper: yes/no prompt ─────────────────────────────────────────────────────
confirm() {
  local msg="$1"
  while true; do
    read -rp "  $msg [y/n] " ans
    case "$ans" in
      [Yy]*) return 0 ;;
      [Nn]*) return 1 ;;
    esac
  done
}

# ── Homebrew ──────────────────────────────────────────────────────────────────
BREW=""
for candidate in /opt/homebrew/bin/brew /usr/local/bin/brew; do
  if [ -x "$candidate" ]; then BREW="$candidate"; break; fi
done

if [ -z "$BREW" ]; then
  echo -e "  ${YELLOW}Homebrew not found.${RESET}"
  echo "  Homebrew is the recommended way to install Python 3.12 and manage"
  echo "  dependencies on macOS. The app can still run without it, but packer"
  echo "  analysis (APKiD) requires Python 3.12 which Homebrew makes easy."
  echo ""
  if confirm "Install Homebrew now? (visits brew.sh — safe, open source)"; then
    echo ""
    echo -e "  ${CYAN}Installing Homebrew...${RESET}"
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/homebrew/install/HEAD/install.sh)"
    # Re-check after install
    for candidate in /opt/homebrew/bin/brew /usr/local/bin/brew; do
      if [ -x "$candidate" ]; then BREW="$candidate"; break; fi
    done
    if [ -n "$BREW" ]; then
      echo -e "  ${GREEN}✓${RESET} Homebrew installed"
    else
      echo -e "  ${YELLOW}Homebrew install may need a terminal restart to take effect.${RESET}"
    fi
  else
    echo -e "  ${YELLOW}Skipping Homebrew — continuing without it.${RESET}"
  fi
  echo ""
fi

# ── Python — prefer 3.12 for APKiD compatibility ─────────────────────────────
PYTHON=""
for candidate in python3.12 python3.13 python3.11 python3.10 python3; do
  if command -v "$candidate" &>/dev/null; then
    VER=$("$candidate" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
    MAJOR=${VER%%.*}; MINOR=${VER##*.}
    if [ "$MAJOR" -ge 3 ] && [ "$MINOR" -ge 10 ]; then
      PYTHON="$candidate"; break
    fi
  fi
done

# If no suitable Python, try to install 3.12 via Homebrew
if [ -z "$PYTHON" ]; then
  if [ -n "$BREW" ]; then
    echo -e "  ${YELLOW}No compatible Python found. Python 3.10+ is required.${RESET}"
    echo ""
    if confirm "Install Python 3.12 via Homebrew?"; then
      echo -e "  ${CYAN}Installing Python 3.12...${RESET}"
      "$BREW" install python@3.12
      if command -v python3.12 &>/dev/null; then
        PYTHON=python3.12
        echo -e "  ${GREEN}✓${RESET} Python 3.12 installed"
      fi
    fi
  fi
  if [ -z "$PYTHON" ]; then
    echo -e "${RED}  [ERROR] No compatible Python found (3.10+ required).${RESET}"
    echo ""
    echo "  Install Python 3.12 from: https://www.python.org/downloads/"
    echo "  Or with Homebrew:  brew install python@3.12"
    echo ""
    read -rp "  Press Enter to close..."
    exit 1
  fi
fi

PY_VER=$("$PYTHON" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
MINOR_ONLY=$("$PYTHON" -c 'import sys; print(sys.version_info.minor)')

echo -e "  ${GREEN}✓${RESET} Python $PY_VER ($PYTHON)"

# Suggest upgrading to 3.12 for APKiD if on a newer/older version
if [ "$MINOR_ONLY" -ge 14 ] || { [ "$MINOR_ONLY" -lt 12 ] && [ "$MINOR_ONLY" -ge 10 ]; }; then
  if [ -n "$BREW" ] && ! command -v python3.12 &>/dev/null; then
    echo -e "  ${YELLOW}Note:${RESET} Python $PY_VER may not support packer analysis (APKiD requires 3.12)."
    echo ""
    if confirm "Install Python 3.12 alongside your current version for full functionality?"; then
      echo -e "  ${CYAN}Installing Python 3.12...${RESET}"
      "$BREW" install python@3.12 && PYTHON=python3.12
      echo -e "  ${GREEN}✓${RESET} Python 3.12 installed — using it for this app"
    fi
    echo ""
  fi
fi

# ── Virtual environment ───────────────────────────────────────────────────────
# Rebuild venv if it was created with a different Python
VENV_PYTHON=""
[ -f ".venv/bin/python3" ] && VENV_PYTHON=$(.venv/bin/python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")' 2>/dev/null)
WANT_PYTHON=$("$PYTHON" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')

if [ -d ".venv" ] && [ "$VENV_PYTHON" != "$WANT_PYTHON" ]; then
  echo -e "  ${CYAN}Updating virtual environment to Python $WANT_PYTHON...${RESET}"
  rm -rf .venv
fi

if [ ! -d ".venv" ]; then
  echo -e "  ${CYAN}Creating virtual environment (first run only)...${RESET}"
  if ! "$PYTHON" -m venv .venv; then
    echo -e "${RED}  [ERROR] Failed to create virtual environment.${RESET}"
    read -rp "  Press Enter to close..."
    exit 1
  fi
fi

source .venv/bin/activate

# ── Core dependencies ─────────────────────────────────────────────────────────
echo -e "  ${CYAN}Checking dependencies...${RESET}"
if ! pip install -r requirements.txt --upgrade -q; then
  echo -e "${RED}  [ERROR] Failed to install dependencies.${RESET}"
  echo "  Check your internet connection and try again."
  read -rp "  Press Enter to close..."
  exit 1
fi
echo -e "  ${GREEN}✓${RESET} Dependencies ready"

# ── APKiD (optional — requires Python 3.12, native build tools) ───────────────
if pip install apkid -q 2>/dev/null; then
  echo -e "  ${GREEN}✓${RESET} APKiD ready (packer analysis enabled)"
else
  echo -e "  ${YELLOW}Note:${RESET} APKiD unavailable on Python $PY_VER — packer analysis skipped"
  if [ "$MINOR_ONLY" -ge 14 ] && [ -n "$BREW" ]; then
    echo "        To enable: brew install python@3.12  (then re-run this launcher)"
  fi
fi

# ── Quark-Engine (pure Python — no native build tools needed) ─────────────────
if pip install quark-engine -q 2>/dev/null; then
  if [ ! -d "$HOME/.quark-engine/quark-rules/rules" ]; then
    echo -e "  ${CYAN}Fetching Quark-Engine rule database (one-time, needs internet)...${RESET}"
    freshquark &>/dev/null || true
  fi
  if [ -d "$HOME/.quark-engine/quark-rules/rules" ]; then
    echo -e "  ${GREEN}✓${RESET} Quark-Engine ready (behavioural pattern analysis enabled)"
  else
    echo -e "  ${YELLOW}Note:${RESET} Quark-Engine rule database unavailable (no internet on first run?) — run 'freshquark' manually later"
  fi
else
  echo -e "  ${YELLOW}Note:${RESET} Quark-Engine install failed — behavioural analysis skipped"
fi
echo ""

# ── Docker ────────────────────────────────────────────────────────────────────
if ! command -v docker &>/dev/null; then
  echo -e "  ${YELLOW}Docker not found.${RESET}"
  echo "  Docker is required to run MobSF for APK scanning."
  echo "  You can still load an existing MobSF JSON report without Docker."
  echo ""
  echo "  Install Docker Desktop: https://www.docker.com/products/docker-desktop"
  echo "  (Docker Desktop must be installed manually — it cannot be auto-installed.)"
  echo ""
else
  if ! curl -s --max-time 3 http://localhost:8000 &>/dev/null; then
    echo -e "  ${CYAN}Starting MobSF (Docker)...${RESET}"
    mkdir -p "$HOME/.mobsf"
    docker run -d --name mobsf -p 8000:8000 \
      -v "$HOME/.mobsf:/home/mobsf/.MobSF" \
      opensecurity/mobile-security-framework-mobsf 2>/dev/null \
      || docker start mobsf 2>/dev/null \
      || true
    echo -e "  ${GREEN}✓${RESET} MobSF starting at http://localhost:8000"
  else
    echo -e "  ${GREEN}✓${RESET} MobSF already running"
  fi
  echo ""
fi

# ── Launch ────────────────────────────────────────────────────────────────────
echo -e "  ${GREEN}${BOLD}Starting APK Analyser...${RESET}"
echo "  Your browser will open automatically."
echo ""
echo "  ── Server output ─────────────────────────"
echo ""

python3 launch.py

echo ""
echo "  Server stopped. Close this window."
read -rp ""
