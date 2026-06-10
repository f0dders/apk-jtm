# APK-JTM — Just tell me if it's dodgy!

Analyses Android APKs using [MobSF](https://github.com/MobSF/Mobile-Security-Framework-MobSF) for static analysis, then passes the findings to an AI model to produce a plain-English security report — no pentesting background required.

Supports **local AI models** (Ollama, LM Studio) for fully offline use, and **cloud AI** (Claude, OpenAI, Gemini) for maximum analysis quality.

---

## Quick Start

### Step 1 — Install Python

You need Python 3.10 or newer. Check if you already have it:

```
python3 --version
```

If not installed, download it from **https://www.python.org/downloads/**

> **Windows users:** during installation, tick **"Add Python to PATH"**

---

### Step 2 — Install Docker (for MobSF)

MobSF is the scanning engine that analyses the APK before the AI steps in.

Download **Docker Desktop** from **https://www.docker.com/products/docker-desktop** and install it. You don't need to know how to use Docker — the launcher handles everything.

> If you already have MobSF running elsewhere, or just want to test with an existing MobSF JSON report, you can skip this step.

---

### Step 3 — Launch the app

Double-click the launcher for your operating system:

| OS | File to double-click |
|---|---|
| **Mac** | `Start - Mac.command` |
| **Windows** | `Start - Windows.bat` |
| **Linux** | `Start - Linux.sh` |

**On first run**, the launcher will:
1. Create an isolated Python environment
2. Install all dependencies automatically
3. Start MobSF via Docker
4. Open the app in your browser at `http://localhost:7842`

Subsequent launches are faster — the setup only runs once.

> **Mac note:** the first time you double-click, macOS may warn you about an unrecognised developer. Right-click the file → **Open** → **Open** to allow it. You only need to do this once.

> **Linux note:** if double-clicking doesn't work, right-click the file → **Properties** → tick **Allow executing as program**, then double-click again.

---

### Step 4 — Complete the setup wizard

On your first visit, a 3-step wizard will guide you through:

1. **MobSF** — paste your API key (shown at `http://localhost:8000` → top-right menu → REST API)
2. **AI provider** — choose offline (Ollama or LM Studio) or cloud (Claude, OpenAI, Gemini)
3. **Configure** — enter your model name or API key for the chosen provider

Your settings are saved locally in a `.env` file and remembered for future sessions.

---

## AI Provider Options

### Offline (no internet required for analysis)

| Provider | Setup | Recommended model |
|---|---|---|
| **Ollama** | Install from [ollama.com](https://ollama.com), then run `ollama pull qwen2.5-coder:32b` | `qwen2.5-coder:32b` (~20 GB) |
| **LM Studio** | Install from [lmstudio.ai](https://lmstudio.ai), load a model, start the local server | Any GGUF model |

**Mac Pro / Apple Silicon** can run large models comfortably:
- `qwen2.5-coder:32b` — excellent code analysis, needs ~20 GB RAM
- `llama3.3:70b` — best reasoning, needs ~40 GB RAM

### Cloud (best quality, requires internet)

| Provider | Where to get a key |
|---|---|
| **Claude** (recommended) | [console.anthropic.com](https://console.anthropic.com) |
| **OpenAI** | [platform.openai.com/api-keys](https://platform.openai.com/api-keys) |
| **Gemini** | [aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey) |

---

## What the report covers

- **Executive summary** — what the app is and its overall risk level
- **Top security findings** — prioritised, plain-English descriptions
- **Privacy concerns** — what data the app can access and how
- **Network activity** — where data is sent, flagged domains, geographic concerns
- **Red flags** — signs of spyware, excessive data harvesting, or malicious intent
- **Recommendations** — clear action items for whether to allow the app

Reports are saved as HTML and Markdown in the `reports/` folder and accessible from the Reports tab in the app.

---

## Scanning options

**Scan a new APK** — drop your `.apk` file onto the app. It's uploaded to MobSF, scanned, and then passed to the AI.

**Use an existing MobSF report** — if you've already scanned an APK in MobSF, export the JSON report and load it directly. This skips the MobSF step entirely and goes straight to AI analysis.

---

## Stopping the app

Close the terminal window that opened when you launched the app. MobSF (Docker) continues running in the background — you can stop it from Docker Desktop if you want to free up resources.

---

## Troubleshooting

**"Could not connect to MobSF"** — make sure Docker Desktop is running and the MobSF container has fully started (can take 30–60 seconds on first launch). Visit `http://localhost:8000` to check.

**Ollama model not found** — run `ollama pull <model-name>` in a terminal before launching the app.

**Slow first launch** — dependencies are installed on first run. This takes 1–3 minutes depending on your internet speed. Subsequent launches are instant.

**Mac Gatekeeper warning** — right-click `Start - Mac.command` → Open → Open. One-time step.

**Windows "Python not found"** — reinstall Python from python.org and make sure "Add Python to PATH" is ticked.
