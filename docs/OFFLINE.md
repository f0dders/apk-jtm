# Offline installation

APK-JTM can already *run* fully offline — using a local AI provider (Ollama or
LM Studio) means no scan or report ever needs internet access. This document
covers the separate matter of *installing* it offline, e.g. on an air-gapped
sandbox VM, which is a natural place to want to test a dodgy APK without it
phoning home.

The regular launchers (`Start - Mac.command`, `Start - Linux.sh`,
`Start - Windows.bat`) install everything from the internet on first run. The
offline bundle described here is a pre-built alternative: a maintainer builds
it once on a connected machine, and it installs on the target machine with no
network access at all.

## For end users — installing from an offline bundle

1. Download the release's offline archive for your platform, e.g.
   `apk-jtm-offline-1.11.0-macos-arm64.tar.gz`.
2. Extract it.
3. Double-click `Start - Mac (Offline).command` (or run
   `./"Start - Linux (Offline).sh"` on Linux).

**Requirements already installed on the target machine** (neither is bundled):
- **Python 3.12, exactly.** The bundle's `wheels/` were downloaded for that one
  Python version — several dependencies (pydantic-core, numpy, grpcio, and
  others pulled in by Quark-Engine's dependency tree) ship as compiled wheels
  tied to a specific Python minor version, OS, and CPU architecture. With no
  internet on the target machine there's no way to fetch or build a wheel for
  a different version, so the launcher checks for `python3.12` specifically
  and stops with an actionable message if it's missing, rather than trying a
  nearby version and failing partway through.
- **Docker Desktop** (or Docker Engine on Linux), already installed and able
  to run containers. This can't be bundled either.
- Also implied: whatever minimum OS version the downloaded arm64/x86_64 wheels
  declare — currently `macosx_11_0` for the arm64 wheels in this dependency
  set (check at build time rather than assuming it never changes).

If Docker isn't available at all, `main.py --report <existing-mobsf.json>`
still runs the AI-analysis half fully offline with no Docker dependency,
for anyone who already has a MobSF JSON export from elsewhere. This is also
the practical **offline workaround for Windows**, where a full offline bundle
isn't built yet (see below).

## For maintainers — building a bundle

```
scripts/build_offline_bundle.sh [--skip-docker] [--output-dir dist]
```

Run this on a connected machine of the **same OS and architecture as the
target** — there's no cross-compilation; a Mac build produces a Mac bundle
for that Mac's architecture (arm64 or x86_64), a Linux build produces a Linux
bundle, and so on. It needs `python3.12` and (unless `--skip-docker`) a
reachable Docker daemon on the build machine itself.

The script:
1. Copies the source tree via `git archive HEAD` (already respects
   `.gitignore` — no dev-only or generated files end up in the bundle).
2. Downloads all `requirements.txt` dependencies as wheels via
   `python3.12 -m pip download`, plus best-effort APKiD/Quark-Engine wheels
   (tolerating failure exactly like the online launchers do today).
3. Snapshots `~/.quark-engine/quark-rules/rules` (fetching it first via
   `freshquark` in a throwaway venv if the build machine doesn't have it yet).
4. Pulls and `docker save`s the MobSF image into the bundle.
5. Packages everything plus the matching offline launcher into a single
   `.tar.gz` under `dist/` (gitignored — not meant to be committed).

`--skip-docker` skips step 4 for a much faster partial bundle, useful when
iterating on the rest of the pipeline — the result won't run MobSF scans but
is fine for checking the source/wheels/quark-rules steps.

**Expected size**: roughly 2-3GB, dominated by the MobSF image (~1.5-2GB)
plus a sizeable `wheels/` — Quark-Engine's dependency tree pulls in
numpy/matplotlib/plotly/grpcio, none of which are small.

**This is a point-in-time snapshot.** Wheels, Quark rules, and the MobSF
image are all frozen at build time — re-cut the bundle alongside future app
releases rather than treating one build as evergreen. (A launcher-side
"this bundle looks old" warning would be a reasonable future addition; not
built yet.)

## What's deliberately out of scope

- **Windows offline bundle.** Deferred — batch-script handling of wheel
  installs and `docker load` is more error-prone than bash, and macOS is the
  priority platform. The `main.py --report` workaround above covers the most
  common offline need in the meantime.
- **Bundling Python or Docker Desktop themselves.** Both are assumed
  pre-installed on the target machine.
- **Cross-compilation.** One build machine produces one platform/arch's
  bundle; there's no way to produce, say, a Linux bundle from a Mac.
