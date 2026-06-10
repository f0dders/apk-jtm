#!/bin/bash
# APK Analyser — Mac launcher
# Double-click this file to start the app.
# On first run: right-click → Open (required once due to macOS security).

cd "$(dirname "$0")"

# ── Colours ──────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; RESET='\033[0m'

echo ""
echo -e "${BOLD}  APK-JTM — Just tell me if it's dodgy!${RESET}"
echo -e "  ─────────────────────────────────────"
echo ""

# ── Check Python ─────────────────────────────────────────────────────────────
if ! command -v python3 &>/dev/null; then
  echo -e "${RED}  [ERROR] Python 3 is not installed.${RESET}"
  echo ""
  echo "  Please install it from: https://www.python.org/downloads/"
  echo "  Then double-click this file again."
  echo ""
  read -p "  Press Enter to close..."
  exit 1
fi

PY_VER=$(python3 -c 'import sys; print(sys.version_info.minor)')
if [ "$PY_VER" -lt 10 ]; then
  echo -e "${RED}  [ERROR] Python 3.10 or newer is required.${RESET}"
  echo "  Your version: $(python3 --version)"
  echo "  Download from: https://www.python.org/downloads/"
  echo ""
  read -p "  Press Enter to close..."
  exit 1
fi

echo -e "  ${GREEN}✓${RESET} Python $(python3 --version | cut -d' ' -f2)"

# ── Virtual environment ───────────────────────────────────────────────────────
if [ ! -d ".venv" ]; then
  echo -e "  ${CYAN}Creating virtual environment (first run only)...${RESET}"
  if ! python3 -m venv .venv; then
    echo -e "${RED}  [ERROR] Failed to create virtual environment.${RESET}"
    read -p "  Press Enter to close..."
    exit 1
  fi
fi

source .venv/bin/activate

# ── Install / update dependencies ────────────────────────────────────────────
echo -e "  ${CYAN}Checking dependencies...${RESET}"

# Show errors but suppress routine progress output
if ! pip install -r requirements.txt --upgrade -q 2>&1 | grep -v "^$" | grep -i "error\|warning\|failed" >&2; then
  : # pip succeeded (grep found no errors, non-zero exit is fine here)
fi

# Re-run to catch actual failures
if ! pip install -r requirements.txt --upgrade -q; then
  echo ""
  echo -e "${RED}  [ERROR] Failed to install dependencies.${RESET}"
  echo "  Check your internet connection and try again."
  echo ""
  read -p "  Press Enter to close..."
  exit 1
fi

echo -e "  ${GREEN}✓${RESET} Dependencies ready"
echo ""

# ── Docker / MobSF (optional) ─────────────────────────────────────────────────
if ! command -v docker &>/dev/null; then
  echo -e "  ${YELLOW}Note:${RESET} Docker not found — APK scanning via MobSF won't be available."
  echo "  You can still load an existing MobSF JSON report for AI analysis."
  echo "  Install Docker Desktop: https://www.docker.com/products/docker-desktop"
  echo ""
else
  if ! curl -s --max-time 3 http://localhost:8000 &>/dev/null; then
    echo -e "  ${CYAN}Starting MobSF (Docker)...${RESET}"
    docker run -d --name mobsf -p 8000:8000 \
      -v mobsf_data:/home/mobsf/.MobSF \
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
read -p ""
