<p align="center">
  <img src="static/logo.png" alt="APK-JTM" width="120">
</p>

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

### Step 2 — Install Docker and start MobSF

MobSF (Mobile Security Framework) is the scanning engine that tears apart the APK before the AI steps in. It runs locally in Docker — you don't need to know how Docker works.

#### 2a — Install Docker Desktop

Download from **https://www.docker.com/products/docker-desktop** and install it. Once installed, open Docker Desktop and leave it running in the background.

> **Windows:** you may be prompted to install WSL 2 during Docker setup — follow the on-screen instructions if so.

#### 2b — Start MobSF

Open a Terminal (Mac/Linux) or Command Prompt (Windows) and run:

**Mac / Linux:**
```
mkdir -p ~/.mobsf
docker run -d --name mobsf -p 8000:8000 -v ~/.mobsf:/home/mobsf/.MobSF opensecurity/mobile-security-framework-mobsf:latest
```

**Windows:**
```
mkdir %USERPROFILE%\.mobsf
docker run -d --name mobsf -p 8000:8000 -v %USERPROFILE%\.mobsf:/home/mobsf/.MobSF opensecurity/mobile-security-framework-mobsf:latest
```

MobSF will download on first run (~1–2 GB) and then start in the background. After 30–60 seconds, open **http://localhost:8000** in your browser to confirm it's running.

> **Why the `-v` flag?** This bind-mounts a local folder (`~/.mobsf`) into the container so MobSF's database — including your API key and scan history — persists across restarts. Using a named Docker volume instead causes a permissions error because Docker creates it owned by root, which MobSF can't write to.

#### 2c — Get your MobSF API key

1. Go to **http://localhost:8000**
2. Click the menu icon in the top-right corner
3. Select **REST API**
4. Copy the API key shown — you'll paste this into the app's setup wizard

> Your API key stays the same across restarts as long as you use the volume flag above. You only need to copy it once.

#### Keeping MobSF running

To stop MobSF: `docker stop mobsf`

To start it again: `docker start mobsf`

The launcher script (`Start - Mac.command` / `Start - Windows.bat` / `Start - Linux.sh`) handles this automatically — it starts MobSF if it's not already running each time you launch the app.

> If you already have MobSF running elsewhere, or just want to analyse an existing MobSF JSON report without scanning, you can skip this step entirely.

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

1. **MobSF** — confirm the URL (default `http://localhost:8000`) and paste your API key (see Step 2c above)
2. **AI provider** — choose offline (Ollama or LM Studio) or cloud (Claude, OpenAI, Gemini, Groq, Mistral, OpenRouter)
3. **Configure** — enter your model name or API key for the chosen provider

Your settings are saved locally in a `.env` file. To change them later, click the ⚙ icon in the top-right of the app.

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

| Provider | Where to get a key | Notes |
|---|---|---|
| **Claude** (recommended) | [console.anthropic.com](https://console.anthropic.com) | Best analysis quality |
| **OpenAI** | [platform.openai.com/api-keys](https://platform.openai.com/api-keys) | GPT-4o and above |
| **Gemini** | [aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey) | Free tier available |
| **Groq** | [console.groq.com](https://console.groq.com) | Very fast, free tier, no credit card |
| **Mistral** | [console.mistral.ai](https://console.mistral.ai) | Strong EU-based option |
| **OpenRouter** | [openrouter.ai/keys](https://openrouter.ai/keys) | One key, 100+ models including free ones |

> **OpenRouter model names** must use the `provider/model` format — e.g. `anthropic/claude-sonnet-4-6`, `openai/gpt-4o`, or `meta-llama/llama-3.3-70b-instruct:free`. Browse all available models at [openrouter.ai/models](https://openrouter.ai/models). Note that very large free-tier models (200B+) can take 2–5 minutes to respond.

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
