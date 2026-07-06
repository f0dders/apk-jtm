#!/bin/bash
# APK-JTM — Linux offline launcher
# For use with an offline install bundle (see OFFLINE_INSTALL.md alongside this
# file). Installs everything from the bundled wheels/, quark-rules-snapshot/,
# and mobsf-image.tar — no network access required.
#
# Requires Python 3.12 and Docker already installed on this machine — neither
# is bundled. Make executable once: chmod +x "Start - Linux (Offline).sh"
# Then run: ./"Start - Linux (Offline).sh"

cd "$(dirname "$0")"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; RESET='\033[0m'

echo ""
echo -e "${BOLD}  APK-JTM — Offline install${RESET}"
echo -e "  ─────────────────────────────────────"
echo ""

# ── Disk space (soft check — extracting + docker load needs headroom beyond
#    the compressed archive's own size) ───────────────────────────────────────
AVAILABLE_KB=$(df -k . | awk 'NR==2 {print $4}')
NEEDED_KB=$((5 * 1024 * 1024))
if [ -n "$AVAILABLE_KB" ] && [ "$AVAILABLE_KB" -lt "$NEEDED_KB" ]; then
  AVAILABLE_GB=$((AVAILABLE_KB / 1024 / 1024))
  echo -e "  ${YELLOW}Warning:${RESET} only ~${AVAILABLE_GB}GB free here — installing and loading"
  echo "  the MobSF image comfortably needs ~5GB. Continuing anyway, but if"
  echo "  something fails partway through, free up space and re-run."
  echo ""
fi

# ── Python — requires exactly 3.12 (bundled wheels are compiled for it) ──────
if ! command -v python3.12 &>/dev/null; then
  echo -e "${RED}  [ERROR] Python 3.12 not found.${RESET}"
  echo "  This offline bundle requires Python 3.12 specifically — the wheels in"
  echo "  wheels/ were downloaded for that exact version and won't install on a"
  echo "  different one without internet access to fetch a compatible build."
  echo ""
  echo "  Install Python 3.12 via your package manager (e.g. apt/dnf/pacman), or"
  echo "  from https://www.python.org/downloads/"
  echo "  (Or, if this machine has internet, use the online installer instead:"
  echo "   \"Start - Linux.sh\" in a regular checkout of the repo.)"
  echo ""
  read -rp "  Press Enter to close..."
  exit 1
fi

PY_VER=$(python3.12 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
echo -e "  ${GREEN}✓${RESET} Python $PY_VER"

# ── Virtual environment ───────────────────────────────────────────────────────
VENV_PYTHON=""
[ -f ".venv/bin/python3" ] && VENV_PYTHON=$(.venv/bin/python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")' 2>/dev/null)

if [ -d ".venv" ] && [ "$VENV_PYTHON" != "3.12" ]; then
  echo -e "  ${CYAN}Rebuilding virtual environment for Python 3.12...${RESET}"
  rm -rf .venv
fi

if [ ! -d ".venv" ]; then
  echo -e "  ${CYAN}Creating virtual environment (first run only)...${RESET}"
  if ! python3.12 -m venv .venv; then
    echo -e "${RED}  [ERROR] Failed to create virtual environment.${RESET}"
    read -rp "  Press Enter to close..."
    exit 1
  fi
fi

source .venv/bin/activate

# ── Core dependencies — installed from the bundled wheels/, no PyPI ─────────
echo -e "  ${CYAN}Installing dependencies from bundled wheels...${RESET}"
if ! pip install --no-index --find-links wheels/ -r requirements.txt --upgrade -q; then
  echo -e "${RED}  [ERROR] Failed to install dependencies from wheels/.${RESET}"
  echo "  This bundle may be incomplete, or built for a different platform/arch."
  read -rp "  Press Enter to close..."
  exit 1
fi
echo -e "  ${GREEN}✓${RESET} Dependencies ready"

# ── APKiD (optional — tolerates failure exactly like the online launcher) ───
if pip install --no-index --find-links wheels/ apkid -q 2>/dev/null; then
  echo -e "  ${GREEN}✓${RESET} APKiD ready (packer analysis enabled)"
else
  echo -e "  ${YELLOW}Note:${RESET} APKiD not in this bundle or unavailable for this platform — packer analysis skipped"
fi

# ── Quark-Engine (optional) + bundled rules snapshot ─────────────────────────
if pip install --no-index --find-links wheels/ quark-engine -q 2>/dev/null; then
  if [ ! -d "$HOME/.quark-engine/quark-rules/rules" ] && [ -d "quark-rules-snapshot/rules" ]; then
    echo -e "  ${CYAN}Restoring bundled Quark-Engine rule database...${RESET}"
    mkdir -p "$HOME/.quark-engine/quark-rules"
    cp -R "quark-rules-snapshot/rules" "$HOME/.quark-engine/quark-rules/rules"
  fi
  if [ -d "$HOME/.quark-engine/quark-rules/rules" ]; then
    echo -e "  ${GREEN}✓${RESET} Quark-Engine ready (behavioural pattern analysis enabled)"
  else
    echo -e "  ${YELLOW}Note:${RESET} No Quark-Engine rules bundled — behavioural analysis skipped"
  fi
else
  echo -e "  ${YELLOW}Note:${RESET} Quark-Engine not in this bundle — behavioural analysis skipped"
fi
echo ""

# ── Docker / MobSF ────────────────────────────────────────────────────────────
if ! command -v docker &>/dev/null; then
  echo -e "  ${YELLOW}Docker not found.${RESET}"
  echo "  Docker must already be installed to run MobSF for APK scanning — it"
  echo "  isn't bundled here. Install it via your package manager or from:"
  echo "  https://docs.docker.com/engine/install/"
  echo "  You can still load an existing MobSF JSON report without Docker."
  echo ""
else
  if ! curl -s --max-time 3 http://localhost:8000 &>/dev/null; then
    if ! docker image inspect opensecurity/mobile-security-framework-mobsf &>/dev/null; then
      if [ -f "mobsf-image.tar" ]; then
        echo -e "  ${CYAN}Loading MobSF image from bundle (no download needed)...${RESET}"
        docker load -i mobsf-image.tar
      else
        echo -e "  ${YELLOW}Note:${RESET} mobsf-image.tar not in this bundle and no local MobSF image found — scanning will be unavailable until one is loaded manually."
      fi
    fi
    if docker image inspect opensecurity/mobile-security-framework-mobsf &>/dev/null; then
      echo -e "  ${CYAN}Starting MobSF (Docker)...${RESET}"
      mkdir -p "$HOME/.mobsf"
      # Clear out any stale container from a previous install so a name clash
      # can't block the fresh one — MobSF's actual data lives in the
      # separately-mounted ~/.mobsf volume, not the container itself.
      docker stop mobsf &>/dev/null || true
      docker rm mobsf &>/dev/null || true
      docker run -d --name mobsf -p 8000:8000 \
        -v "$HOME/.mobsf:/home/mobsf/.MobSF" \
        opensecurity/mobile-security-framework-mobsf 2>/dev/null \
        || true
      echo -e "  ${GREEN}✓${RESET} MobSF starting at http://localhost:8000"
    fi
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
