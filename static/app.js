/* APK Analyser — frontend logic */

const $ = id => document.getElementById(id);
const show = id => $(id)?.classList.remove('hidden');
const hide = id => $(id)?.classList.add('hidden');

// ─── State ────────────────────────────────────────────────────────────────────
const state = {
  view: 'loading',       // loading | wizard | scan | progress | report | history
  wizardStep: 1,
  selectedProvider: 'ollama',
  config: {},
  scanFile: null,
  reportFile: null,
  scanId: null,
  reportUrl: null,
};

// ─── Init ─────────────────────────────────────────────────────────────────────
async function init() {
  // Show a manual fallback after 4 seconds in case fetch hangs
  const fallbackTimer = setTimeout(() => {
    $('loading-fallback')?.classList.remove('hidden');
  }, 4000);

  try {
    const cfg = await apiWithTimeout('/api/config', 8000);
    clearTimeout(fallbackTimer);
    state.config = cfg;
    if (!cfg.configured) setView('wizard');
    else setView('scan');
  } catch (e) {
    clearTimeout(fallbackTimer);
    // Server unreachable or JS error — go straight to wizard so user isn't stuck
    setView('wizard');
  }
}

function skipToApp() {
  clearTimeout();
  setView('wizard');
}

// ─── View routing ─────────────────────────────────────────────────────────────
function setView(view) {
  state.view = view;
  ['view-loading','view-wizard','view-scan','view-progress','view-report','view-history']
    .forEach(id => hide(id));
  show(`view-${view}`);

  if (view === 'wizard') renderWizard();
  if (view === 'scan')   renderScan();
  if (view === 'history') loadHistory();
}

// ─── Wizard ───────────────────────────────────────────────────────────────────
const PROVIDERS = [
  { id: 'ollama',      name: 'Ollama',      type: 'offline', flag: '🖥️', location: 'Your machine',     desc: 'Local models via Ollama. Fully offline.' },
  { id: 'lmstudio',   name: 'LM Studio',   type: 'offline', flag: '🖥️', location: 'Your machine',     desc: 'Local models via LM Studio. Fully offline.' },
  { id: 'claude',     name: 'Claude',      type: 'cloud',   flag: '🇺🇸', location: 'USA',              desc: 'Anthropic Claude. Best analysis quality.' },
  { id: 'openai',     name: 'OpenAI',      type: 'cloud',   flag: '🇺🇸', location: 'USA',              desc: 'ChatGPT / GPT-4o.' },
  { id: 'gemini',     name: 'Gemini',      type: 'cloud',   flag: '🇺🇸', location: 'USA',              desc: 'Google Gemini 1.5 Pro.' },
  { id: 'groq',       name: 'Groq',        type: 'cloud',   flag: '🇺🇸', location: 'USA',              desc: 'Ultra-fast inference. Generous free tier.' },
  { id: 'mistral',    name: 'Mistral',     type: 'cloud',   flag: '🇪🇺', location: 'EU (France)',       desc: 'European AI. Strong code & reasoning models.' },
  { id: 'openrouter', name: 'OpenRouter',  type: 'cloud',   flag: '🇺🇸', location: 'USA (multi-model)', desc: 'One key, 100+ models — Claude, GPT-4, Llama & more.' },
];

const DEFAULT_MODELS = {
  ollama:      'qwen2.5-coder:32b',
  lmstudio:    '',
  claude:      'claude-sonnet-4-6',
  openai:      'gpt-4o',
  gemini:      'gemini-1.5-pro',
  groq:        'llama-3.3-70b-versatile',
  mistral:     'mistral-large-latest',
  openrouter:  'anthropic/claude-sonnet-4-6',
};

function renderWizard() {
  updateWizardSteps();
  renderWizardStep();
}

function updateWizardSteps() {
  [1,2,3].forEach(n => {
    const el = $(`wstep-${n}`);
    if (!el) return;
    el.className = 'wizard-step' +
      (n === state.wizardStep ? ' active' : '') +
      (n < state.wizardStep ? ' done' : '');
    const num = el.querySelector('.step-num');
    if (n < state.wizardStep) num.textContent = '✓';
    else num.textContent = n;
  });
}

function renderWizardStep() {
  const body = $('wizard-body');
  if (!body) return;

  if (state.wizardStep === 1) {
    body.innerHTML = `
      <div class="wizard-title">Welcome to APK-JTM</div>
      <div class="wizard-subtitle">Let's get you set up in 3 quick steps. First, enter your MobSF details.</div>
      <div class="field">
        <label>MobSF URL</label>
        <input id="wiz-mobsf-url" type="text" value="${state.config.mobsf_url || 'http://localhost:8000'}" placeholder="http://localhost:8000">
        <div class="field-hint">Run MobSF with Docker: <code>docker run -d --name mobsf -p 8000:8000 -v mobsf_data:/home/mobsf/.MobSF opensecurity/mobile-security-framework-mobsf</code> — the <code>-v</code> flag keeps your API key and scan history across restarts</div>
      </div>
      <div class="field">
        <label>MobSF API Key</label>
        <input id="wiz-mobsf-key" type="password"
               value="${state.config.mobsf_key_set ? '••••••••' : ''}"
               placeholder="Paste your API key from MobSF → REST API">
        <div class="field-hint">${state.config.mobsf_key_set ? '✓ Key saved — leave blank to keep existing key.' : 'Find it at http://localhost:8000 → top-right menu → REST API'}</div>
      </div>
    `;
  }

  if (state.wizardStep === 2) {
    const grid = PROVIDERS.map(p => `
      <div class="provider-card ${state.selectedProvider === p.id ? 'selected' : ''}"
           onclick="selectProvider('${p.id}')">
        <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:4px">
          <div class="provider-name">${p.name}</div>
          <span title="${p.location}" style="font-size:18px;line-height:1">${p.flag}</span>
        </div>
        <span class="provider-type badge-${p.type === 'offline' ? 'offline' : 'cloud'}">${p.type}</span>
        <div class="provider-desc">${p.desc}</div>
      </div>
    `).join('');

    body.innerHTML = `
      <div class="wizard-title">Choose AI Provider</div>
      <div class="wizard-subtitle">Offline providers run entirely on your machine. Cloud providers give the best analysis quality but require an internet connection.</div>
      <div class="provider-grid">${grid}</div>
    `;
  }

  if (state.wizardStep === 3) {
    const p = state.selectedProvider;
    const cfg = state.config;
    let fields = '';

    if (p === 'ollama') {
      fields = `
        <div class="field">
          <label>Ollama URL</label>
          <input id="wiz-ollama-url" type="text" value="${cfg.ollama_url || 'http://localhost:11434'}">
        </div>
        <div class="field">
          <label>Model</label>
          <input id="wiz-ollama-model" type="text" value="${cfg.ollama_model || DEFAULT_MODELS.ollama}" placeholder="qwen2.5-coder:32b">
          <div class="field-hint">Install with: <code>ollama pull qwen2.5-coder:32b</code></div>
        </div>
      `;
    } else if (p === 'lmstudio') {
      fields = `
        <div class="field">
          <label>LM Studio Server URL</label>
          <input id="wiz-lmstudio-url" type="text" value="${cfg.lmstudio_url || 'http://localhost:1234'}">
          <div class="field-hint">Start the server in LM Studio → Local Server tab</div>
        </div>
        <div class="field">
          <label>Model name</label>
          <input id="wiz-lmstudio-model" type="text" value="${cfg.lmstudio_model || ''}" placeholder="Must match the model loaded in LM Studio">
        </div>
      `;
    } else if (p === 'claude') {
      fields = `
        <div class="field">
          <label>Anthropic API Key</label>
          <input id="wiz-anthropic-key" type="password" placeholder="sk-ant-..." value="${cfg.claude_key_set ? '••••••••' : ''}">
          <div class="field-hint">Get a key at console.anthropic.com</div>
        </div>
        <div class="field">
          <label>Model</label>
          <input id="wiz-claude-model" type="text" value="${cfg.claude_model || DEFAULT_MODELS.claude}">
        </div>
      `;
    } else if (p === 'openai') {
      fields = `
        <div class="field">
          <label>OpenAI API Key</label>
          <input id="wiz-openai-key" type="password" placeholder="sk-..." value="${cfg.openai_key_set ? '••••••••' : ''}">
          <div class="field-hint">Get a key at platform.openai.com/api-keys</div>
        </div>
        <div class="field">
          <label>Model</label>
          <input id="wiz-openai-model" type="text" value="${cfg.openai_model || DEFAULT_MODELS.openai}">
        </div>
      `;
    } else if (p === 'gemini') {
      fields = `
        <div class="field">
          <label>Google Gemini API Key</label>
          <input id="wiz-gemini-key" type="password" placeholder="AIza..." value="${cfg.gemini_key_set ? '••••••••' : ''}">
          <div class="field-hint">Get a key at aistudio.google.com/app/apikey</div>
        </div>
        <div class="field">
          <label>Model</label>
          <input id="wiz-gemini-model" type="text" value="${cfg.gemini_model || DEFAULT_MODELS.gemini}">
        </div>
      `;
    } else if (p === 'groq') {
      fields = `
        <div class="field">
          <label>Groq API Key</label>
          <input id="wiz-groq-key" type="password" placeholder="gsk_..." value="${cfg.groq_key_set ? '••••••••' : ''}">
          <div class="field-hint">Free tier available at <strong>console.groq.com</strong> — no credit card required</div>
        </div>
        <div class="field">
          <label>Model</label>
          <input id="wiz-groq-model" type="text" value="${cfg.groq_model || DEFAULT_MODELS.groq}">
          <div class="field-hint">Fast options: llama-3.3-70b-versatile · mixtral-8x7b-32768 · gemma2-9b-it</div>
        </div>
      `;
    } else if (p === 'mistral') {
      fields = `
        <div class="field">
          <label>Mistral API Key</label>
          <input id="wiz-mistral-key" type="password" placeholder="..." value="${cfg.mistral_key_set ? '••••••••' : ''}">
          <div class="field-hint">Get a key at <strong>console.mistral.ai</strong></div>
        </div>
        <div class="field">
          <label>Model</label>
          <input id="wiz-mistral-model" type="text" value="${cfg.mistral_model || DEFAULT_MODELS.mistral}">
          <div class="field-hint">Recommended: mistral-large-latest · codestral-latest (code-focused)</div>
        </div>
      `;
    } else if (p === 'openrouter') {
      fields = `
        <div class="field">
          <label>OpenRouter API Key</label>
          <input id="wiz-openrouter-key" type="password" placeholder="sk-or-..." value="${cfg.openrouter_key_set ? '••••••••' : ''}">
          <div class="field-hint">Get a key at <strong>openrouter.ai/keys</strong> — access 100+ models with one key</div>
        </div>
        <div class="field">
          <label>Model</label>
          <input id="wiz-openrouter-model" type="text" value="${cfg.openrouter_model || DEFAULT_MODELS.openrouter}">
          <div class="field-hint">Use the full <code>provider/model</code> slug from openrouter.ai/models, e.g. <code>anthropic/claude-sonnet-4-6</code> · <code>openai/gpt-4o</code> · <code>meta-llama/llama-3.3-70b-instruct:free</code></div>
        </div>
        <div class="info-box">
          ⏱ <strong>Free-tier models can be slow.</strong> Large models (200B+) may take 2–5 minutes to respond, or time out under heavy load. For reliable speed, try <code>meta-llama/llama-3.3-70b-instruct:free</code> or a paid model.
        </div>
      `;
    }

    const pName = PROVIDERS.find(x => x.id === p)?.name || p;
    body.innerHTML = `
      <div class="wizard-title">Configure ${pName}</div>
      <div class="wizard-subtitle">Almost done. Fill in the connection details for ${pName}.</div>
      ${fields}
    `;
  }
}

function selectProvider(id) {
  state.selectedProvider = id;
  document.querySelectorAll('.provider-card').forEach(el => {
    el.classList.toggle('selected', el.onclick.toString().includes(`'${id}'`));
  });
  // Re-render to apply selected class reliably
  renderWizardStep();
}

async function wizardNext() {
  if (state.wizardStep === 1) {
    const url = $('wiz-mobsf-url')?.value?.trim();
    const key = $('wiz-mobsf-key')?.value?.trim();
    if (!url) { toast('Enter a MobSF URL', 'err'); return; }
    state._mobsfUrl = url;
    state._mobsfKey = key;
    state.wizardStep = 2;
  } else if (state.wizardStep === 2) {
    if (!state.selectedProvider) { toast('Select a provider', 'err'); return; }
    state.wizardStep = 3;
  } else if (state.wizardStep === 3) {
    await saveWizardConfig();
    return;
  }
  renderWizard();
}

function wizardBack() {
  if (state.wizardStep > 1) {
    state.wizardStep--;
    renderWizard();
  }
}

async function saveWizardConfig() {
  const p = state.selectedProvider;
  const payload = {
    MOBSF_URL: state._mobsfUrl,
    PROVIDER: p,
  };
  if (state._mobsfKey && !state._mobsfKey.startsWith('•')) {
    payload.MOBSF_API_KEY = state._mobsfKey;
  }

  const g = id => $(id)?.value?.trim();

  if (p === 'ollama') {
    payload.OLLAMA_URL = g('wiz-ollama-url') || 'http://localhost:11434';
    payload.OLLAMA_MODEL = g('wiz-ollama-model') || DEFAULT_MODELS.ollama;
  } else if (p === 'lmstudio') {
    payload.LM_STUDIO_URL = g('wiz-lmstudio-url') || 'http://localhost:1234';
    payload.LM_STUDIO_MODEL = g('wiz-lmstudio-model') || '';
  } else if (p === 'claude') {
    const key = g('wiz-anthropic-key');
    if (key && !key.startsWith('•')) payload.ANTHROPIC_API_KEY = key;
    payload.CLAUDE_MODEL = g('wiz-claude-model') || DEFAULT_MODELS.claude;
  } else if (p === 'openai') {
    const key = g('wiz-openai-key');
    if (key && !key.startsWith('•')) payload.OPENAI_API_KEY = key;
    payload.OPENAI_MODEL = g('wiz-openai-model') || DEFAULT_MODELS.openai;
  } else if (p === 'gemini') {
    const key = g('wiz-gemini-key');
    if (key && !key.startsWith('•')) payload.GEMINI_API_KEY = key;
    payload.GEMINI_MODEL = g('wiz-gemini-model') || DEFAULT_MODELS.gemini;
  } else if (p === 'groq') {
    const key = g('wiz-groq-key');
    if (key && !key.startsWith('•')) payload.GROQ_API_KEY = key;
    payload.GROQ_MODEL = g('wiz-groq-model') || DEFAULT_MODELS.groq;
  } else if (p === 'mistral') {
    const key = g('wiz-mistral-key');
    if (key && !key.startsWith('•')) payload.MISTRAL_API_KEY = key;
    payload.MISTRAL_MODEL = g('wiz-mistral-model') || DEFAULT_MODELS.mistral;
  } else if (p === 'openrouter') {
    const key = g('wiz-openrouter-key');
    if (key && !key.startsWith('•')) payload.OPENROUTER_API_KEY = key;
    payload.OPENROUTER_MODEL = g('wiz-openrouter-model') || DEFAULT_MODELS.openrouter;
  }

  try {
    await api('/api/config', { method: 'POST', body: payload });
    state.config = await api('/api/config');
    toast('Configuration saved', 'ok');
    setView('scan');
  } catch (e) {
    toast('Failed to save config', 'err');
  }
}

// ─── Scan view ────────────────────────────────────────────────────────────────
function renderScan() {
  // No dynamic rendering needed — HTML is static, just bind events
  const apkZone = $('apk-dropzone');
  const apkInput = $('apk-input');
  const jsonInput = $('json-input');

  if (apkZone) {
    apkZone.addEventListener('dragover', e => { e.preventDefault(); apkZone.classList.add('over'); });
    apkZone.addEventListener('dragleave', () => apkZone.classList.remove('over'));
    apkZone.addEventListener('drop', e => {
      e.preventDefault(); apkZone.classList.remove('over');
      const file = e.dataTransfer.files[0];
      if (file) handleApkFile(file);
    });
  }

  if (apkInput) apkInput.addEventListener('change', e => { if (e.target.files[0]) handleApkFile(e.target.files[0]); });
  if (jsonInput) jsonInput.addEventListener('change', e => { if (e.target.files[0]) handleJsonFile(e.target.files[0]); });
}

function handleApkFile(file) {
  if (!file.name.endsWith('.apk')) { toast('Please drop an .apk file', 'err'); return; }
  state.scanFile = file;
  state.reportFile = null;
  $('dropzone-title').textContent = file.name;
  $('dropzone-sub').textContent = `${(file.size / 1024 / 1024).toFixed(1)} MB — ready to scan`;
  $('btn-start-scan').disabled = false;
  $('btn-start-scan').textContent = 'Scan APK';
}

function handleJsonFile(file) {
  if (!file.name.endsWith('.json')) { toast('Please select a .json file', 'err'); return; }
  state.reportFile = file;
  state.scanFile = null;
  $('dropzone-title').textContent = 'APK drop zone';
  $('dropzone-sub').textContent = 'Drop an .apk here or click to browse';
  $('btn-start-scan').disabled = false;
  $('btn-start-scan').textContent = `Analyse: ${file.name}`;
}

async function startScan() {
  if (!state.scanFile && !state.reportFile) return;

  const form = new FormData();
  if (state.scanFile) form.append('apk', state.scanFile);
  if (state.reportFile) form.append('report_json', state.reportFile);

  try {
    const res = await fetch('/api/scan/upload', { method: 'POST', body: form });
    if (!res.ok) throw new Error(await res.text());
    const { scan_id } = await res.json();
    state.scanId = scan_id;
    setView('progress');
    streamProgress(scan_id);
  } catch (e) {
    toast(`Upload failed: ${e.message}`, 'err');
  }
}

// ─── Progress / streaming ─────────────────────────────────────────────────────
const STAGE_LABELS = {
  provider: 'AI provider ready',
  loading: 'Loading MobSF report',
  upload: 'Uploading to MobSF',
  scan: 'Scanning APK',
  extract: 'Extracting findings',
  extracted: 'Findings extracted',
  analysis: 'AI analysis',
};

function resetProgressView() {
  $('progress-stages').innerHTML = '';
  $('progress-terminal').textContent = '';
  hide('progress-terminal-wrap');
  hide('progress-meta');
  hide('btn-view-report');
  show('btn-cancel-scan');
}

function streamProgress(scanId) {
  resetProgressView();
  const terminal = $('progress-terminal');
  const stagesEl = $('progress-stages');
  const stages = {};

  function getOrCreateStage(key) {
    if (stages[key]) return stages[key];
    const el = document.createElement('div');
    el.className = 'stage active';
    el.innerHTML = `
      <span class="stage-icon"><span class="spinner"></span></span>
      <span class="stage-label">${STAGE_LABELS[key] || key}</span>
      <span class="stage-msg"></span>
    `;
    stagesEl.appendChild(el);
    stages[key] = el;
    return el;
  }

  function markStageDone(key, msg = '') {
    const el = stages[key];
    if (!el) return;
    el.classList.remove('active');
    el.classList.add('done');
    el.querySelector('.stage-icon').textContent = '✓';
    if (msg) el.querySelector('.stage-msg').textContent = msg;
  }

  const evtSource = new EventSource(`/api/scan/${scanId}/stream`);
  let analysisStarted = false;
  let analysisTimer = null;
  let analysisSeconds = 0;

  function startAnalysisTimer() {
    analysisSeconds = 0;
    analysisTimer = setInterval(() => {
      analysisSeconds++;
      const el = stages['analysis'];
      if (!el) return;
      const msgEl = el.querySelector('.stage-msg');
      let hint = `${analysisSeconds}s elapsed`;
      if (analysisSeconds >= 20) hint += ' — large models can take 2–5 min';
      if (analysisSeconds >= 90) hint += '. Still waiting…';
      msgEl.textContent = hint;
    }, 1000);
  }

  function stopAnalysisTimer() {
    if (analysisTimer) { clearInterval(analysisTimer); analysisTimer = null; }
  }

  evtSource.addEventListener('progress', e => {
    const data = JSON.parse(e.data);
    const stage = data.stage;
    getOrCreateStage(stage);

    if (stage === 'extracted') {
      markStageDone('extract');
      markStageDone('extracted');
      renderMetaCard(data);
      show('progress-meta');
    } else if (stage === 'analysis') {
      markStageDone('extracted');
      getOrCreateStage('analysis');
      if (!analysisStarted) {
        analysisStarted = true;
        show('progress-terminal-wrap');
        startAnalysisTimer();
      }
    } else {
      const el = stages[stage];
      if (el) el.querySelector('.stage-msg').textContent = data.message || '';
    }
  });

  evtSource.addEventListener('analysis', e => {
    if (!analysisStarted) {
      analysisStarted = true;
      show('progress-terminal-wrap');
      getOrCreateStage('analysis');
      startAnalysisTimer();
    }
    stopAnalysisTimer();
    terminal.textContent += e.data;
    terminal.scrollTop = terminal.scrollHeight;
  });

  evtSource.addEventListener('complete', e => {
    const data = JSON.parse(e.data);
    evtSource.close();
    stopAnalysisTimer();
    markStageDone('analysis', 'Complete');
    Object.keys(stages).forEach(k => markStageDone(k));
    state.reportUrl = data.report_url;
    show('btn-view-report');
    hide('btn-cancel-scan');
    toast('Analysis complete', 'ok');
  });

  evtSource.addEventListener('error', e => {
    let msg = 'Unknown error';
    let errType = 'error';
    let provider = '';
    try {
      const d = JSON.parse(e.data);
      msg = d.message;
      errType = d.type || 'error';
      provider = d.provider || '';
    } catch {}
    evtSource.close();
    stopAnalysisTimer();

    const errEl = document.createElement('div');
    errEl.className = 'stage error';
    errEl.innerHTML = `<span class="stage-icon">✕</span><span class="stage-label">Error</span><span class="stage-msg">${msg}</span>`;
    stagesEl.appendChild(errEl);
    terminal.textContent += `\n\nError: ${msg.replace(/<[^>]+>/g, '')}`;

    if (errType === 'rate_limit' || errType === 'timeout') {
      stagesEl.appendChild(buildModelSuggestions(provider));
    }

    toast('Analysis failed — see suggestions below', 'err');
  });
}

function renderMetaCard(data) {
  const meta = $('progress-meta');
  if (!meta) return;
  const score = parseInt(data.score) || 0;
  const cls = score >= 70 ? 'score-ok' : score >= 40 ? 'score-warn' : 'score-crit';
  meta.innerHTML = `
    <div class="meta-grid">
      <div class="meta-item"><div class="meta-label">App</div><div class="meta-value">${data.app_name || '—'}</div></div>
      <div class="meta-item"><div class="meta-label">Package</div><div class="meta-value" style="font-size:12px;word-break:break-all">${data.package || '—'}</div></div>
      <div class="meta-item"><div class="meta-label">Version</div><div class="meta-value">${data.version || '—'}</div></div>
      <div class="meta-item"><div class="meta-label">Security Score</div><div class="meta-value ${cls}">${score}/100</div></div>
      <div class="meta-item"><div class="meta-label">Trackers</div><div class="meta-value ${data.trackers > 3 ? 'score-warn' : ''}">${data.trackers}</div></div>
      <div class="meta-item"><div class="meta-label">Dangerous Perms</div><div class="meta-value ${data.dangerous_perms > 5 ? 'score-crit' : data.dangerous_perms > 2 ? 'score-warn' : ''}">${data.dangerous_perms}</div></div>
    </div>
  `;
}

// ─── Model suggestions after rate limit / timeout ─────────────────────────────
const SUGGESTED_MODELS = [
  { slug: 'meta-llama/llama-3.3-70b-instruct:free', label: 'Llama 3.3 70B', note: 'Fast · Free · OpenRouter' },
  { slug: 'google/gemma-3-12b-it:free',             label: 'Gemma 3 12B',   note: 'Lightweight · Free · OpenRouter' },
  { slug: 'mistralai/mistral-7b-instruct:free',     label: 'Mistral 7B',    note: 'Reliable · Free · OpenRouter' },
  { slug: 'deepseek/deepseek-r1-0528:free',         label: 'DeepSeek R1',   note: 'Strong reasoning · Free · OpenRouter' },
];

function buildModelSuggestions(provider) {
  const wrap = document.createElement('div');
  wrap.className = 'model-suggestions';

  const title = document.createElement('div');
  title.className = 'model-suggestions-title';
  title.textContent = '💡 Try a different model — click to switch and re-run:';
  wrap.appendChild(title);

  const grid = document.createElement('div');
  grid.className = 'model-suggestions-grid';

  // If provider is openrouter, show free alternatives; otherwise suggest openrouter or groq
  const suggestions = provider === 'openrouter'
    ? SUGGESTED_MODELS
    : [
        { slug: 'meta-llama/llama-3.3-70b-instruct:free', label: 'Switch to OpenRouter (free)', note: 'openrouter.ai' },
        { slug: 'llama-3.3-70b-versatile', label: 'Switch to Groq (free)', note: 'Very fast · console.groq.com' },
      ];

  suggestions.forEach(({ slug, label, note }) => {
    const btn = document.createElement('button');
    btn.className = 'model-suggestion-btn';
    btn.innerHTML = `<span class="suggestion-label">${label}</span><span class="suggestion-note">${note}</span>`;
    btn.onclick = () => retryWithModel(provider, slug, btn, wrap);
    grid.appendChild(btn);
  });

  wrap.appendChild(grid);
  return wrap;
}

async function retryWithModel(provider, modelSlug, btn, wrap) {
  // Disable all buttons to prevent double-clicks
  wrap.querySelectorAll('button').forEach(b => b.disabled = true);
  btn.innerHTML = `<span class="suggestion-label">Saving…</span>`;

  // Save the new model to config
  const key = provider === 'openrouter' ? 'OPENROUTER_MODEL'
    : provider === 'groq' ? 'GROQ_MODEL'
    : provider === 'mistral' ? 'MISTRAL_MODEL'
    : provider === 'ollama' ? 'OLLAMA_MODEL'
    : null;

  if (key) {
    try { await api('/api/config', { method: 'POST', body: { [key]: modelSlug } }); } catch {}
  }

  // Re-run scan with the chosen model passed as an override
  if (!state.scanFile && !state.reportFile) {
    toast('Original file no longer available — please re-upload', 'err');
    return;
  }

  const form = new FormData();
  if (state.scanFile) form.append('apk', state.scanFile);
  if (state.reportFile) form.append('report_json', state.reportFile);
  form.append('model_override', modelSlug);

  try {
    const res = await fetch('/api/scan/upload', { method: 'POST', body: form });
    if (!res.ok) throw new Error(await res.text());
    const { scan_id } = await res.json();
    state.scanId = scan_id;
    setView('progress');
    streamProgress(scan_id);
  } catch (err) {
    toast(`Failed to restart scan: ${err.message}`, 'err');
  }
}

function viewReport() {
  if (!state.reportUrl) return;
  const frame = $('report-frame');
  frame.src = state.reportUrl;
  setView('report');
}

// ─── History ──────────────────────────────────────────────────────────────────
async function loadHistory() {
  const list = $('report-list');
  list.innerHTML = '<div class="text-muted text-sm">Loading...</div>';
  try {
    const { reports } = await api('/api/reports');
    if (!reports.length) {
      list.innerHTML = '<div class="text-muted text-sm">No reports yet.</div>';
      return;
    }
    list.innerHTML = reports.map(r => `
      <div class="report-item">
        <div>
          <div class="report-name">${r.name.replace('report_','').replace('.html','').replace(/_/g,' ')}</div>
          <div class="report-meta">${new Date(r.modified * 1000).toLocaleString()} · ${(r.size/1024).toFixed(0)} KB</div>
        </div>
        <div class="report-actions">
          <button class="btn-icon" onclick="openReport('${r.url}')">Open</button>
          <a href="${r.url}" download class="btn-icon" style="text-decoration:none;display:inline-flex;align-items:center;padding:7px 10px">↓</a>
        </div>
      </div>
    `).join('');
  } catch {
    list.innerHTML = '<div class="text-muted text-sm">Failed to load reports.</div>';
  }
}

function openReport(url) {
  const frame = $('report-frame');
  frame.src = url;
  setView('report');
}

// ─── Settings shortcut ────────────────────────────────────────────────────────
function openSettings() {
  state.wizardStep = 1;
  setView('wizard');
}

// ─── Helpers ──────────────────────────────────────────────────────────────────
async function api(path, opts = {}) {
  const options = { headers: { 'Content-Type': 'application/json' } };
  if (opts.method) options.method = opts.method;
  if (opts.body) options.body = JSON.stringify(opts.body);
  const res = await fetch(path, options);
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
}

async function apiWithTimeout(path, ms) {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), ms);
  try {
    const res = await fetch(path, {
      headers: { 'Content-Type': 'application/json' },
      signal: ctrl.signal,
    });
    if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
    return res.json();
  } finally {
    clearTimeout(timer);
  }
}

const sleep = ms => new Promise(r => setTimeout(r, ms));

let _toastTimer;
function toast(msg, type = '') {
  const el = $('toast');
  el.textContent = msg;
  el.className = `show ${type}`;
  clearTimeout(_toastTimer);
  _toastTimer = setTimeout(() => el.classList.remove('show'), 3500);
}

// ─── Boot ─────────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', init);
