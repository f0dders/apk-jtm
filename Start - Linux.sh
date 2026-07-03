#!/bin/bash
# APK-JTM — Linux launcher
# Make executable once: chmod +x "Start - Linux.sh"
# Then run: ./"Start - Linux.sh"

cd "$(dirname "$0")"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; RESET='\033[0m'

echo ""
echo -e "${BOLD}  APK-JTM — Just tell me if it's dodgy!${RESET}"
echo -e "  ─────────────────────────────────────"
echo ""

# ── Helper: yes/no prompt ─────────────────────────────────────────────────────
confirm() {
  while true; do
    read -rp "  $1 [y/n] " ans
    case "$ans" in [Yy]*) return 0 ;; [Nn]*) return 1 ;; esac
  done
}

# ── Detect package manager ────────────────────────────────────────────────────
PKG_MGR=""
if   command -v apt-get &>/dev/null; then PKG_MGR="apt"
elif command -v dnf     &>/dev/null; then PKG_MGR="dnf"
elif command -v pacman  &>/dev/null; then PKG_MGR="pacman"
fi

pkg_install() {
  # Usage: pkg_install "display name" pkg-apt pkg-dnf pkg-pacman
  local name="$1" apt_pkg="$2" dnf_pkg="$3" pac_pkg="$4"
  case "$PKG_MGR" in
    apt)    sudo apt-get install -y "$apt_pkg" ;;
    dnf)    sudo dnf install -y "$dnf_pkg" ;;
    pacman) sudo pacman -S --noconfirm "$pac_pkg" ;;
    *)
      echo -e "  ${YELLOW}Cannot auto-install $name — no supported package manager found.${RESET}"
      return 1
      ;;
  esac
}

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

if [ -z "$PYTHON" ]; then
  echo -e "  ${YELLOW}No compatible Python found (3.10+ required).${RESET}"
  echo ""
  if [ -n "$PKG_MGR" ]; then
    if confirm "Install Python 3.12 now? (requires sudo)"; then
      echo -e "  ${CYAN}Installing Python 3.12...${RESET}"
      pkg_install "Python 3.12" "python3.12 python3.12-venv python3-pip" "python3.12" "python312"
      command -v python3.12 &>/dev/null && PYTHON=python3.12
    fi
  else
    echo "  Install Python 3.10+ from: https://www.python.org/downloads/"
    echo "    Ubuntu/Debian:  sudo apt install python3.12 python3.12-venv python3-pip"
    echo "    Fedora:         sudo dnf install python3.12"
    echo "    Arch:           sudo pacman -S python312"
  fi
  if [ -z "$PYTHON" ]; then
    echo -e "${RED}  [ERROR] Python 3.10+ is required. Exiting.${RESET}"
    read -rp "  Press Enter to close..."
    exit 1
  fi
fi

PY_VER=$("$PYTHON" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
MINOR_ONLY=$("$PYTHON" -c 'import sys; print(sys.version_info.minor)')
echo -e "  ${GREEN}✓${RESET} Python $PY_VER ($PYTHON)"

# Suggest 3.12 for APKiD if on 3.14+ or <3.12
if { [ "$MINOR_ONLY" -ge 14 ] || [ "$MINOR_ONLY" -lt 12 ]; } && ! command -v python3.12 &>/dev/null && [ -n "$PKG_MGR" ]; then
  echo -e "  ${YELLOW}Note:${RESET} APKiD (packer analysis) works best on Python 3.12."
  echo ""
  if confirm "Install Python 3.12 alongside your current version?"; then
    echo -e "  ${CYAN}Installing Python 3.12...${RESET}"
    pkg_install "Python 3.12" "python3.12 python3.12-venv" "python3.12" "python312"
    command -v python3.12 &>/dev/null && PYTHON=python3.12 && \
      echo -e "  ${GREEN}✓${RESET} Python 3.12 installed"
  fi
  echo ""
fi

# ── Check python3-venv (Debian/Ubuntu split package) ─────────────────────────
if ! "$PYTHON" -m venv --help &>/dev/null 2>&1; then
  echo -e "  ${YELLOW}python3-venv is missing.${RESET}"
  if [ "$PKG_MGR" = "apt" ] && confirm "Install python3-venv now? (requires sudo)"; then
    sudo apt-get install -y python3-venv python3.12-venv 2>/dev/null || sudo apt-get install -y python3-venv
  else
    echo "  Run: sudo apt install python3-venv"
    read -rp "  Press Enter to close..."
    exit 1
  fi
fi

# ── Virtual environment ───────────────────────────────────────────────────────
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

# ── APKiD (optional) ──────────────────────────────────────────────────────────
if pip install apkid -q 2>/dev/null; then
  echo -e "  ${GREEN}✓${RESET} APKiD ready (packer analysis enabled)"
else
  echo -e "  ${YELLOW}Note:${RESET} APKiD unavailable on Python $PY_VER — packer analysis skipped"
  if [ "$MINOR_ONLY" -ge 14 ] && ! command -v python3.12 &>/dev/null; then
    echo "        To enable: install Python 3.12 and re-run this launcher"
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
  if [ -n "$PKG_MGR" ]; then
    echo "  Docker Desktop cannot be installed automatically."
    echo "  Install it from: https://docs.docker.com/engine/install/"
    case "$PKG_MGR" in
      apt)    echo "  Or try: sudo apt install docker.io && sudo usermod -aG docker \$USER" ;;
      dnf)    echo "  Or try: sudo dnf install docker && sudo usermod -aG docker \$USER" ;;
      pacman) echo "  Or try: sudo pacman -S docker && sudo usermod -aG docker \$USER" ;;
    esac
  fi
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
echo -e "  ${GREEN}${BOLD}Launching APK Analyser...${RESET}"
echo -e "  Opening ${CYAN}http://localhost:7842${RESET} in your browser"
echo ""
echo "  Close this window to stop the app."
echo ""

python3 launch.py
