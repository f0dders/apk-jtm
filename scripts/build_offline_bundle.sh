#!/bin/bash
# APK-JTM — Offline bundle builder
#
# Run on a connected macOS or Linux machine to produce an install bundle that
# needs zero network access on the target machine, beyond Python 3.12 and
# Docker Desktop already being installed there (neither is bundled — see
# docs/OFFLINE.md for why).
#
# Usage: scripts/build_offline_bundle.sh [--skip-docker] [--output-dir dist]
#   --skip-docker   Skip pulling/saving the MobSF image (~1.5-2GB) — produces
#                   a partial bundle, useful for quickly testing the rest of
#                   the pipeline.
#   --output-dir    Where to write the final archive (default: dist/).

set -euo pipefail

SKIP_DOCKER=0
OUTPUT_DIR="dist"

while [ $# -gt 0 ]; do
  case "$1" in
    --skip-docker) SKIP_DOCKER=1; shift ;;
    --output-dir) OUTPUT_DIR="$2"; shift 2 ;;
    *) echo "Unknown argument: $1" >&2; exit 1 ;;
  esac
done

cd "$(dirname "$0")/.."   # repo root

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; RESET='\033[0m'

echo ""
echo -e "${BOLD}  APK-JTM — Offline bundle builder${RESET}"
echo -e "  ─────────────────────────────────────"
echo ""

# ── Validate build machine ───────────────────────────────────────────────────
if ! command -v python3.12 &>/dev/null; then
  echo -e "${RED}  [ERROR] python3.12 not found.${RESET}"
  echo "  The offline bundle is built with — and requires — exactly Python 3.12:"
  echo "  several vendored dependencies (pydantic-core, numpy, grpcio, etc.) ship"
  echo "  as compiled wheels tied to one Python minor version, and the target"
  echo "  machine has no internet to fall back to a source build."
  echo "  Install Python 3.12 (e.g. brew install python@3.12) and re-run."
  exit 1
fi

if [ "$SKIP_DOCKER" -eq 0 ]; then
  if ! command -v docker &>/dev/null; then
    echo -e "${RED}  [ERROR] Docker not found.${RESET}"
    echo "  Needed to pull + save the MobSF image. Install Docker Desktop, or"
    echo "  pass --skip-docker to build a partial bundle without it (for testing)."
    exit 1
  fi
  if ! docker info &>/dev/null; then
    echo -e "${RED}  [ERROR] Docker daemon not reachable.${RESET}"
    echo "  Start Docker Desktop and re-run, or pass --skip-docker."
    exit 1
  fi
fi

echo -e "  ${GREEN}✓${RESET} Python 3.12 found"
[ "$SKIP_DOCKER" -eq 0 ] && echo -e "  ${GREEN}✓${RESET} Docker reachable"
echo ""

# ── Version + platform detection ─────────────────────────────────────────────
VERSION=$(python3.12 -c "exec(open('version.py').read()); print(VERSION)")
OS_NAME=$(uname -s)
ARCH_NAME=$(uname -m)

case "$OS_NAME" in
  Darwin) PLATFORM="macos" ;;
  Linux)  PLATFORM="linux" ;;
  *) echo -e "${RED}  [ERROR] Unsupported build platform: $OS_NAME${RESET}"; exit 1 ;;
esac

case "$ARCH_NAME" in
  arm64|aarch64) ARCH="arm64" ;;
  x86_64)        ARCH="x86_64" ;;
  *) echo -e "${RED}  [ERROR] Unsupported architecture: $ARCH_NAME${RESET}"; exit 1 ;;
esac

BUNDLE_NAME="apk-jtm-${VERSION}"
ARCHIVE_NAME="apk-jtm-offline-${VERSION}-${PLATFORM}-${ARCH}.tar.gz"

echo -e "  ${CYAN}Building offline bundle:${RESET} v${VERSION} (${PLATFORM}-${ARCH})"
echo ""

# ── Staging directory ─────────────────────────────────────────────────────────
STAGING_ROOT="${OUTPUT_DIR}/.staging"
STAGING_DIR="${STAGING_ROOT}/${BUNDLE_NAME}"

rm -rf "$STAGING_ROOT"
mkdir -p "$STAGING_DIR"
mkdir -p "$OUTPUT_DIR"

# ── Source tree (git archive already respects .gitignore) ───────────────────
echo -e "  ${CYAN}Copying source tree...${RESET}"
git archive HEAD | tar -x -C "$STAGING_DIR"
echo -e "  ${GREEN}✓${RESET} Source tree copied"

# ── Wheels ────────────────────────────────────────────────────────────────────
echo -e "  ${CYAN}Downloading wheels (python3.12, this machine's platform)...${RESET}"
WHEELS_DIR="${STAGING_DIR}/wheels"
mkdir -p "$WHEELS_DIR"
python3.12 -m pip download -r requirements.txt -d "$WHEELS_DIR"
echo -e "  ${GREEN}✓${RESET} Core dependency wheels downloaded"

if python3.12 -m pip download apkid -d "$WHEELS_DIR" &>/dev/null; then
  echo -e "  ${GREEN}✓${RESET} APKiD wheel bundled"
else
  echo -e "  ${YELLOW}Note:${RESET} APKiD wheel unavailable for this platform/Python — skipped (mirrors the online launcher's behaviour)"
fi

if python3.12 -m pip download quark-engine -d "$WHEELS_DIR" &>/dev/null; then
  echo -e "  ${GREEN}✓${RESET} Quark-Engine wheel bundled"
else
  echo -e "  ${YELLOW}Note:${RESET} Quark-Engine wheel download failed — skipped"
fi

WHEELS_SIZE=$(du -sh "$WHEELS_DIR" | cut -f1)
echo -e "  ${CYAN}wheels/ total:${RESET} $WHEELS_SIZE"
echo ""

# ── Quark rules snapshot ──────────────────────────────────────────────────────
QUARK_RULES="$HOME/.quark-engine/quark-rules/rules"
if [ ! -d "$QUARK_RULES" ]; then
  echo -e "  ${CYAN}Fetching Quark-Engine rule database (one-time on this build machine)...${RESET}"
  if command -v freshquark &>/dev/null; then
    freshquark &>/dev/null || true
  else
    # Don't permanently install quark-engine into the build machine's global
    # Python just to run freshquark once — use a throwaway venv instead.
    TMP_VENV=$(mktemp -d)
    python3.12 -m venv "$TMP_VENV" &>/dev/null
    "$TMP_VENV/bin/pip" install --quiet quark-engine &>/dev/null || true
    "$TMP_VENV/bin/freshquark" &>/dev/null || true
    rm -rf "$TMP_VENV"
  fi
fi

if [ -d "$QUARK_RULES" ]; then
  mkdir -p "${STAGING_DIR}/quark-rules-snapshot"
  cp -R "$QUARK_RULES" "${STAGING_DIR}/quark-rules-snapshot/rules"
  echo -e "  ${GREEN}✓${RESET} Quark-Engine rules snapshot bundled"
else
  echo -e "  ${YELLOW}Note:${RESET} Quark-Engine rules unavailable — bundle will skip behavioural analysis until 'freshquark' is run online later"
fi
echo ""

# ── MobSF Docker image ────────────────────────────────────────────────────────
MOBSF_IMAGE="opensecurity/mobile-security-framework-mobsf"
DIGEST="(skipped — --skip-docker)"
if [ "$SKIP_DOCKER" -eq 0 ]; then
  echo -e "  ${CYAN}Pulling MobSF image (can take a few minutes, ~1.5-2GB)...${RESET}"
  docker pull "$MOBSF_IMAGE"
  DIGEST=$(docker inspect --format '{{index .RepoDigests 0}}' "$MOBSF_IMAGE" 2>/dev/null || echo "unknown")
  echo -e "  ${CYAN}Saving image to bundle...${RESET}"
  docker save "$MOBSF_IMAGE" -o "${STAGING_DIR}/mobsf-image.tar"
  echo -e "  ${GREEN}✓${RESET} MobSF image bundled ($DIGEST)"
else
  echo -e "  ${YELLOW}Skipping Docker image (--skip-docker) — bundle will be partial, for testing only.${RESET}"
fi
echo ""

# ── Offline launcher + install notes ─────────────────────────────────────────
# These templates live under scripts/launchers/offline/, not repo root — the
# offline launcher only ever runs from inside an extracted bundle (against
# its wheels/, mobsf-image.tar, quark-rules-snapshot/), never in place in a
# git checkout, so it has no reason to sit at the repo's top level.
LAUNCHER_NAME="Start - Mac (Offline).command"
[ "$PLATFORM" = "linux" ] && LAUNCHER_NAME="Start - Linux (Offline).sh"
LAUNCHER_SRC="scripts/launchers/offline/${LAUNCHER_NAME}"

if [ -f "$LAUNCHER_SRC" ]; then
  cp "$LAUNCHER_SRC" "${STAGING_DIR}/${LAUNCHER_NAME}"
  chmod +x "${STAGING_DIR}/${LAUNCHER_NAME}"
else
  echo -e "${RED}  [ERROR] Offline launcher '${LAUNCHER_SRC}' not found.${RESET}"
  exit 1
fi

cat > "${STAGING_DIR}/OFFLINE_INSTALL.md" <<EOF
# APK-JTM v${VERSION} — Offline bundle (${PLATFORM}-${ARCH})

Built: $(date -u +"%Y-%m-%d %H:%M UTC")
MobSF image: ${MOBSF_IMAGE} @ ${DIGEST}

This is a point-in-time snapshot — wheels, Quark rules, and the MobSF image are
all frozen at build time. Re-cut this bundle alongside future app releases
rather than treating it as evergreen.

## Requirements on the target machine
- Python 3.12 (exactly — the bundled wheels are compiled for this version)
- Docker Desktop, already installed and able to run containers

Neither of these is bundled here — see docs/OFFLINE.md in the source repo for why.

## Install
1. Extract this archive.
2. Double-click \`${LAUNCHER_NAME}\` (or run it from a terminal).
3. The launcher installs everything from the bundled \`wheels/\`, loads MobSF
   from \`mobsf-image.tar\`, and starts the app — no network access needed.
EOF

echo -e "  ${GREEN}✓${RESET} Offline launcher + install notes bundled"
echo ""

# ── Archive ────────────────────────────────────────────────────────────────────
echo -e "  ${CYAN}Creating archive...${RESET}"
tar -czf "${OUTPUT_DIR}/${ARCHIVE_NAME}" -C "$STAGING_ROOT" "$BUNDLE_NAME"
rm -rf "$STAGING_ROOT"

SIZE=$(du -h "${OUTPUT_DIR}/${ARCHIVE_NAME}" | cut -f1)
echo -e "  ${GREEN}${BOLD}✓ Bundle built:${RESET} ${OUTPUT_DIR}/${ARCHIVE_NAME} (${SIZE})"
echo ""
