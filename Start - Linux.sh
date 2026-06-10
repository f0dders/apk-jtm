#!/bin/bash
# APK Analyser — Linux launcher
# Make executable once: chmod +x "Start - Linux.sh"
# Then double-click in your file manager, or run: ./"Start - Linux.sh"

set -e
cd "$(dirname "$0")"

# ── Colours ──────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; RESET='\033[0m'

echo ""
echo -e "${BOLD}  APK-JTM — Just tell me if it's dodgy!${RESET}"
echo -e "  ${CYAN}Starting up...${RESET}"
echo ""

# ── Check Python ─────────────────────────────────────────────────────────────
if ! command -v python3 &>/dev/null; then
  echo -e "${RED}  Python 3 is not installed.${RESET}"
  echo ""
  echo "  Install it with your package manager:"
  echo "    Ubuntu/Debian:  sudo apt install python3 python3-venv python3-pip"
  echo "    Fedora:         sudo dnf install python3"
  echo "    Arch:           sudo pacman -S python"
  echo ""
  read -p "  Press Enter to close..."
  exit 1
fi

PY_VER=$(python3 -c 'import sys; print(sys.version_info.minor)')
if [ "$PY_VER" -lt 10 ]; then
  echo -e "${RED}  Python 3.10 or newer is required (you have $(python3 --version)).${RESET}"
  echo "  Install a newer version via your package manager or https://www.python.org/downloads/"
  read -p "  Press Enter to close..."
  exit 1
fi

# Check python3-venv is available (common issue on Debian/Ubuntu)
if ! python3 -m venv --help &>/dev/null; then
  echo -e "${RED}  python3-venv is missing.${RESET}"
  echo "  Install it with: sudo apt install python3-venv"
  read -p "  Press Enter to close..."
  exit 1
fi

echo -e "  ${GREEN}✓${RESET} Python $(python3 --version | cut -d' ' -f2)"

# ── Virtual environment ───────────────────────────────────────────────────────
if [ ! -d ".venv" ]; then
  echo -e "  ${CYAN}Creating virtual environment (first run only)...${RESET}"
  python3 -m venv .venv
fi

source .venv/bin/activate

# ── Install / update dependencies ────────────────────────────────────────────
echo -e "  ${CYAN}Checking dependencies...${RESET}"
pip install -q -r requirements.txt --upgrade

echo -e "  ${GREEN}✓${RESET} Dependencies ready"
echo ""

# ── Check Docker / MobSF hint ────────────────────────────────────────────────
if ! command -v docker &>/dev/null; then
  echo -e "  ${YELLOW}Note:${RESET} Docker is not installed."
  echo "  MobSF requires Docker: https://docs.docker.com/engine/install/"
  echo "  You can still use the app with an existing MobSF JSON report."
  echo ""
else
  if ! curl -s --max-time 3 http://localhost:8000 &>/dev/null; then
    echo -e "  ${CYAN}Starting MobSF (Docker)...${RESET}"
    docker start mobsf 2>/dev/null \
      || docker run -d --name mobsf -p 8000:8000 \
           opensecurity/mobile-security-framework-mobsf 2>/dev/null \
      || true
    echo -e "  ${GREEN}✓${RESET} MobSF starting at http://localhost:8000"
  else
    echo -e "  ${GREEN}✓${RESET} MobSF already running"
  fi
  echo ""
fi

# ── Launch ────────────────────────────────────────────────────────────────────
echo -e "  ${GREEN}${BOLD}Launching APK Analyser...${RESET}"
echo -e "  Opening ${CYAN}http://localhost:7842${RESET} in your browser"
echo ""
echo "  Close this window to stop the app."
echo ""

python3 launch.py
