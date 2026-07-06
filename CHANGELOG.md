# Changelog

All notable changes are documented here. Versions follow [Semantic Versioning](https://semver.org).

---

## [v1.11.0] — 2026-07-06

### New features

- **Reports can now be written in any language** — a new "Report Language" field in ⚙ Settings (default British English) controls the language the AI writes its report in, alongside a matching `--language` CLI flag and `REPORT_LANGUAGE` config key. Since the AI generates the report body itself, this covers non-English languages essentially for free, not just US/UK English.
- **Offline install bundle for air-gapped machines** — `scripts/build_offline_bundle.sh` produces a pre-built archive (vendored dependency wheels, a saved MobSF Docker image, and a Quark-Engine rules snapshot) plus a matching offline launcher (`Start - Mac (Offline).command`, `Start - Linux (Offline).sh`), so the app can be installed with zero network access — only Python 3.12 and Docker need to already be present on the target machine. See [docs/OFFLINE.md](docs/OFFLINE.md). Windows offline bundles aren't built yet; `main.py --report <mobsf.json>` remains a fully offline workaround there.

---

## [v1.10.1] — 2026-07-06

### Fixes

- **The progress view could show "Analysis complete" for a scan that had barely started** — starting a new scan reused the progress screen from the last one without resetting the heading, subtitle, AI-output label, and "View Report" button styling that only get set once a scan actually finishes. If those were still showing a previous scan's completed state, a fresh scan would look "done" while its stages were genuinely still running underneath. The progress view now resets fully to its in-progress state at the start of every scan.

---

## [v1.10.0] — 2026-07-06

### Fixes

- **Fixed a stored XSS vulnerability in the history and version-compare views** — app names, package IDs, versions, AI summaries, and verdict labels come from the scanned APK's manifest (or the AI's own output) and were being written into the page without escaping. A maliciously-crafted app name or version string could run arbitrary script in your browser the next time its report appeared in your history or a version comparison. Every untrusted field across both views is now escaped before display.
- **JSON-uploaded MobSF reports could show a false "0/100 — Critical Risk"** — the "Analyse existing JSON" flow never fetched MobSF's real security score, so it rendered whatever placeholder value (always 0) was baked into the raw export. Now fetches the real score when possible, or shows "N/A" instead of a misleading 0.
- **AI analysis could be killed prematurely on slow or cold-starting local models** — a flat 2-minute timeout applied to every gap between streamed chunks, even though the app's own progress hint said "large models can take 2–5 min". Replaced with a longer allowance for the model's first response (covers cold-start/model-load) and a shorter stall timeout once it's actually streaming.
- **A rate-limit retry notice could leak into a saved report** — OpenRouter's "retrying in Ns…" message was written directly into the AI's output stream and could land in the persisted report, occasionally interfering with verdict extraction. It's now shown live as a status update and kept out of the saved report entirely.
- **Fixed a memory leak on long-running instances** — a scan's progress queue was never cleaned up if the browser tab closed before the analysis view opened. A stale-queue sweep now runs on every new scan, mirroring the existing upload-file cleanup.
- **Large APK/JSON uploads were fully buffered in memory twice over** — now streamed to disk in chunks with a 500MB cap, so an oversized upload is rejected cleanly instead of risking an out-of-memory crash.
- **Closed a path-traversal gap on the report-serving endpoint** — brought it in line with the other report endpoints, which already validated filenames.
- **Fixed a model-tier misclassification** — a cheap/fast model variant from the same generation as a frontier model (e.g. a "-nano" or "-flash-lite" sibling) could be wrongly badged "Frontier".

### Improvements

- **Generated reports now support dark mode** — previously hardcoded light colours regardless of system preference; now follows your system's dark/light setting, matching the app's own (already-dark) interface.
- **Icon-only buttons (open, download, re-run, delete) now have accessible labels** for screen readers.
- **Domain list now shows when it's been truncated** — "Showing 20 of N" appears when a scan found more domains than the report displays.
- **Update check no longer phones home when running fully offline** — skipped entirely when your selected AI provider is Ollama or LM Studio, in line with the app's local-first privacy premise.

### Internal

- Simplified a redundant exception handler in the APKiD client (no behaviour change).
- Added 15 new tests (68 total) covering all of the above.

---

## [v1.9.4] — 2026-07-03

### Documentation

- **Added CONTRIBUTING.md** — documents the actual maintenance model (solo direct-to-`main` commits by the maintainer) and the process for external contributors (fork, branch, PR, tests must pass, update CHANGELOG under `[Unreleased]`). Prompted by a git-practices review that found issue templates existed but nothing told an outside contributor how to actually submit a code change.

---

## [v1.9.3] — 2026-07-03

### Fixes

- **Migrated Gemini provider from `google-generativeai` to `google-genai`** — Google deprecated the old SDK; `GeminiProvider.stream()` now uses `genai.Client(...).models.generate_content_stream(...)`, same streaming interface, no behaviour change for users.
- **README Acknowledgements entry updated to match** — was pointing at the deprecated package's repo; now links `googleapis/python-genai`, the SDK actually installed.
- **"Compare versions" description now mentions Quark-Engine** — the feature has diffed Quark threat-level changes since v1.7.0, but the README's description of what gets compared never mentioned it.

---

## [v1.9.2] — 2026-07-03

### Documentation

- **README intro paragraph now mentions Quark-Engine** — it had described the app as MobSF + APKiD only, missed when Quark-Engine was added back in v1.7.0.

---

## [v1.9.1] — 2026-07-03

### Documentation

- **Added an Acknowledgements section to the README** — credits MobSF, APKiD, and Quark-Engine (the three engines this app orchestrates, all GPL-3.0/GPL-compatible) plus the supporting Python libraries, each with a verified licence and link. Licences were confirmed against installed package metadata rather than assumed.

---

## [v1.9.0] — 2026-07-03

### New features

- **Settings is now a proper single-page menu, separate from onboarding** — the ⚙ icon no longer reopens the 3-step first-run wizard. Instead it opens a Settings page with MobSF Connection, AI Provider, and Configure all visible at once, one "Save Settings" button, no Back/Continue step navigation. Switching AI provider only redraws the "Configure" section — MobSF fields (and any unsaved edits there) are left untouched. The onboarding wizard is unchanged and still runs on first launch.

### Internal

- Extracted `buildProviderConfigFields()` and `buildConfigPayload()` — the per-provider field HTML and payload-reading logic, previously duplicated inline in the wizard, are now shared between the wizard's step 3 and the new Settings page (parameterised by ID prefix so both can coexist in the DOM).

---

## [v1.8.1] — 2026-07-03

### Fixes

- **Settings always showed Ollama selected, regardless of your actual configured provider** — `state.selectedProvider` was hardcoded at startup and never synced from the saved config, so opening ⚙ Settings highlighted Ollama even if you'd configured Claude (or anything else). Now syncs correctly on load and after saving.
- **OpenAI/Gemini provider card descriptions still said "GPT-4o"/"Gemini 1.5 Pro"** — missed in the v1.8.0 model refresh since the card descriptions live in a separate array from the default model strings. Updated to "GPT-5 and above" / "Gemini 2.5 and above".

---

## [v1.8.0] — 2026-07-03

### Fixes

- **Groq default model was heading toward breakage** — `llama-3.3-70b-versatile` (the app's hardcoded Groq default) was deprecated by Groq in June 2026. Default changed to `openai/gpt-oss-120b` (Groq's own recommended migration target — also faster and cheaper). If you configured Groq before this update, update your model in ⚙ Settings.

### Improvements

- **Refreshed cloud AI defaults** — Claude → `claude-sonnet-5`, OpenAI → `gpt-5.5`, Gemini → `gemini-2.5-pro`, OpenRouter → `anthropic/claude-sonnet-5`. Previous defaults (Sonnet 4.6, GPT-4o, Gemini 1.5 Pro) were one to two generations behind current.
- **Model tier classifier updated** — added pattern matches for the new defaults plus `gpt-5.x` generally, `gpt-oss-120b`/`gpt-oss-20b`, and Qwen 3.5/3.6, so newer models correctly show as Frontier/Capable instead of falling through to "Unknown".
- **README AI section overhauled** — cloud provider table notes now name actual current defaults; offline/Apple Silicon recommendations replaced with a RAM-tiered list (Qwen 3.5/3.6, gpt-oss 20B/120B) reflecting the current local-model landscape, while keeping the app's built-in Ollama default (`qwen2.5-coder:32b`) as the baseline recommendation.
- Wizard field hints (Groq, OpenRouter, retry-with-model suggestions) updated to match.

---

## [v1.7.0] — 2026-07-03

### New features

- **Quark-Engine behavioural analysis** — runs in parallel with MobSF and APKiD on every new APK scan. Matches API-call patterns against ~280 community rules covering known malware-family behaviours (banking trojans, spyware, persistence/evasion techniques). Pure Python, no native build tools required — its rule database is fetched once via `freshquark` (needs internet for that one step), then every scan runs fully offline against the local copy. The AI is explicitly instructed not to blindly trust Quark's mechanical "threat level" — many legitimate apps trigger Moderate/High purely from using APIs also common in malware — and instead reasons about each matched behaviour in context.
- **Report cards show a Quark badge** when the threat level is above Low Risk — styled as neutral info (never an alarm colour), since the signal is noisy on its own and the AI report gives the real context.
- **Version comparison now covers Quark too** — the "⇄ Compare" feature added in v1.6.0 diffs threat-level changes between two saved scans of the same app, alongside permissions/trackers/domains/secrets/code issues/APKiD.
- Re-runs reuse Quark-Engine results from the original scan, same as APKiD — no APK needed to re-analyse with a different AI model.

### Internal

- Added `quark_client.py` (parses Quark's raw JSON — which includes every one of ~280 rules checked, matched or not — down to genuine ≥80%-confidence matches, sorted by weight).
- 12 new tests covering the parser and its error paths (missing binary, missing rule database, timeout).
- All three launchers (Mac/Linux/Windows) and the dev launcher install Quark-Engine and run `freshquark` during first-run setup.

---

## [v1.6.0] — 2026-07-03

### New features

- **Compare versions** — a "⇄ Compare" button appears on any report group with 2+ analyses. Pick any two saved runs to see what changed between them: permissions, trackers, domains, secrets, and code issues (added/removed), plus APKiD packer/anti-emulator/malware-packer flag changes. Built entirely from existing report data — no re-scanning required. Older reports predating this feature show "Not available" for detailed diffs until re-run.
- **Cache-busted static assets** — `/static/app.js` and `/static/style.css` are now served with a version-tied query string, so a browser that cached the frontend from a previous install reliably picks up new JS/CSS after an update instead of silently running stale code.

### Fixes

- **Uploaded APK/JSON files were never deleted after a scan** — `uploads/` had silently grown to 482MB of orphaned files, including on failed scans. Every exit path now cleans up via a `finally` block. A startup sweep also clears anything older than an hour, as a safety net for hard process kills where the normal cleanup never runs.

### Internal

- Added a pytest suite (44 tests) covering the pure logic modules (`extractor.py`, `apkid_client.py`, `model_tier.py`, `paths.py`) and regression tests for the upload leak and the version-comparison diff logic. Wired up GitHub Actions to run the suite on every push/PR to main.

---

## [v1.5.0] — 2026-06-24

### New features

- **Platform-standard user data directory** — config (`.env`) and reports now live outside the app folder in the OS-standard location (`~/Library/Application Support/APK-JTM/` on Mac, `%APPDATA%\APK-JTM\` on Windows, `~/.local/share/apk-jtm/` on Linux). Existing installs are migrated automatically on first launch. Updates are now frictionless — `git pull` or replace the app folder and nothing needs to be copied.
- **Update notifications** — the app checks GitHub releases on startup (once per session) and shows a dismissible banner if a newer version is available, with a "How to update" modal covering both Git and ZIP install paths.
- **Version in Settings** — the ⚙ Settings panel now shows the current version and data directory path at the bottom.

### Improvements

- **Consolidated status pills on report cards** — when everything is clear (LOW verdict + no APKiD flags), a single green "✓ Safe to use" pill replaces the previous two-pill layout. Warning pills (Malware packer / Packed / Anti-emulator) only appear when APKiD flagged something — clean results earn no badge.
- **Settings panel title** — shows "Settings" for returning users, "Welcome to APK-JTM" for first-time setup.

---

## [v1.4.0] — 2026-06-24

### New features

- **APKiD packer & obfuscation analysis** — runs in parallel with MobSF on every new APK scan. Detects packers, obfuscators, anti-VM/anti-debug/anti-disassembly techniques, and compiler fingerprints. Known malware-associated packers (Bangcle, SecNeo, Jiagu, DexProtect, etc.) trigger a mandatory HIGH/CRITICAL verdict escalation.
- **Re-analyse with a different AI model** — reports page now has a ⟳ button on every report. Re-runs the AI analysis against the original MobSF scan data without re-uploading the APK. APKiD results from the original scan are reused automatically.
- **Grouped reports by app** — the reports page groups multiple analyses of the same app together, with the most recent shown in full and older runs collapsed into compact rows.

### Improvements

- **Smart launchers for all three platforms** — Mac, Linux, and Windows launchers now auto-detect and offer to install missing dependencies (Python 3.12, Docker, APKiD) using the platform's package manager (Homebrew / apt/dnf/pacman / winget). System-level installs always prompt for consent first.
- **APKiD badges on report cards** — clean scans show a green ✅ No packers badge; flagged scans show colour-coded badges (🚨 Malware packer / 📦 Packed / 🕵️ Anti-emulator).
- **Clearer completion state** — the analysis progress page now updates its heading to "Analysis complete", switches the button to green, and strips in-progress "..." suffixes from all stage messages when done.
- **Anti-emulator framing** — anti-VM detection is now explained as "this app may not run on emulators or test devices" rather than treated as inherently malicious. Banking apps, DRM, and anti-cheat legitimately use this.
- **AI prompt improvements** — APKiD section added with mandatory verdict escalation rule; clean APKiD results explicitly passed to AI; unknown-app risk rule tightened.
- **Fixed: View Report appearing before AI streaming finishes** — race condition between SSE `complete` and buffered `analysis` chunk events resolved with an `analysis_done` sentinel.
- **Fixed: APKiD JSON parse error** — APKiD 2.1.x outputs `files` as a list, not a dict. Parser now handles both formats.

---

## [v1.3.0] — 2026-06-10

### New features

- **AI verdict and summary** — every report now ends with a machine-readable `VERDICT: LOW|MEDIUM|HIGH|CRITICAL` and one-sentence plain-English summary, displayed as a badge on report cards.
- **Geographic server analysis** — AI prompt includes a dedicated section on where the app's servers are hosted and what that means for data privacy under local law.
- **AI model tier badge** — reports show whether the analysis used a Frontier, Capable, Basic, or Unknown model.
- **App icon in reports** — fetched from MobSF and embedded in the HTML report header.
- **Expandable chip details** — security finding chips in the report header now expand to show the list of items (e.g. specific permissions, trackers, secrets).

### Improvements

- Non-technical card redesign with plain-English verdict labels (✓ Safe to use / ⚠ Use with caution / ✗ Avoid)
- Dual risk signal on cards: AI verdict badge + MobSF score
- Prompt: app reputation context injected before findings; false-positive guidance for hardcoded secrets
- Ollama context window configurable via `OLLAMA_NUM_CTX` env var (default 32768, for Gemma 4 / large models)

---

## [v1.2.0] — 2026-05-20

### New features

- **Rich reports page** — saved reports shown as cards with score, permissions count, tracker count, date, and file size
- **Delete reports** from the UI
- **Metadata sidecars** — `.meta.json` files store report metadata for fast card rendering without re-parsing HTML
- **MobSF scan caching** — uploading an APK that MobSF has already scanned skips re-scanning and uses cached results (shown as ⚡ in progress view)

---

## [v1.1.0] — 2026-05-01

### New features

- **Multi-provider AI support** — Claude, OpenAI, Gemini, Groq, Mistral, OpenRouter, Ollama, LM Studio
- **Setup wizard** — 3-step first-run wizard to configure MobSF connection and AI provider
- **Settings panel** — edit `.env` configuration from the UI without touching the command line
- **SSE streaming** — AI analysis streams token-by-token to the browser as it's generated

---

## [v1.0.0] — 2026-04-15

Initial release.

- MobSF static analysis + AI plain-English report generation
- Drag-and-drop APK upload
- Load existing MobSF JSON report
- Mac and Windows launcher scripts
- Ollama (local) and Claude (cloud) support
