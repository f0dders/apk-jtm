# Changelog

All notable changes are documented here. Versions follow [Semantic Versioning](https://semver.org).

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
