"""
AI provider abstractions. Each provider implements
stream(prompt, system=None) -> Iterator[str].

Local:  OllamaProvider, LMStudioProvider
Cloud:  ClaudeProvider, OpenAIProvider, GeminiProvider,
        GroqProvider, MistralProvider, OpenRouterProvider
"""

from __future__ import annotations
from typing import Iterator

# Prefix marking a diagnostic/retry notice yielded mid-stream (e.g. a rate
# limit retry) so the caller can route it to the user live without it being
# treated as AI content and persisted into the saved report.
RETRY_NOTICE_PREFIX = "\x00RETRY\x00"

# Sampling is pinned so that re-running the same APK through the same model
# reproduces the same report. A low temperature alone is not enough: without an
# explicit seed the sampler restarts from fresh randomness on every call, which
# is why regenerating a report used to produce wildly different output.
FIXED_TEMPERATURE = 0.0
FIXED_TOP_P = 1.0

# Claude has no seed and rejects temperature on its current models, so the only
# lever there is output length. 4096 was tight enough that a full report could
# be cut off before the trailing VERDICT/SUMMARY tags the UI depends on.
CLAUDE_MAX_TOKENS = 16000

# Seed used when no APK hash is available to derive one from (JSON-only scans
# carrying no md5). Fixed rather than random so those runs stay self-consistent.
DEFAULT_SEED = 20260722


def seed_for_hash(md5: str | None) -> int:
    """Derive a stable per-APK sampling seed.

    Deriving rather than storing means the same APK always samples the same way
    with no extra state to keep in sync, while a different APK samples
    differently.
    """
    if md5 and len(md5) >= 8:
        try:
            return int(md5[:8], 16)
        except ValueError:
            pass
    return DEFAULT_SEED


def _messages(prompt: str, system: str | None) -> list[dict]:
    """Build an OpenAI-style message list, omitting an empty system turn."""
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    return messages


def _is_seed_rejection(exc: Exception) -> bool:
    """True if a request was rejected specifically because of `seed`.

    Not every OpenAI-compatible backend accepts the parameter — OpenRouter in
    particular fronts many models whose upstreams differ — and the wording of
    the refusal varies by vendor, so match on the parameter name plus a
    rejection verb rather than on any one vendor's message.
    """
    text = str(exc).lower()
    if "seed" not in text:
        return False
    return any(
        marker in text
        for marker in (
            "unrecognized", "unknown", "unsupported", "not supported",
            "unexpected", "invalid", "extra_forbidden", "additional",
        )
    )


def _create_completion(provider, client, prompt: str, system: str | None):
    """Open an OpenAI-compatible stream, degrading gracefully if `seed` is refused.

    Records on the provider whether the seed actually applied, so the caller can
    tell the user the truth about whether this run is reproducible instead of
    assuming it is.
    """
    from openai import BadRequestError

    kwargs = dict(
        model=provider.model,
        messages=_messages(prompt, system),
        stream=True,
        temperature=FIXED_TEMPERATURE,
    )
    if provider.seed is not None:
        kwargs["seed"] = provider.seed

    try:
        stream = client.chat.completions.create(**kwargs)
    except (BadRequestError, TypeError) as exc:
        if "seed" not in kwargs or not _is_seed_rejection(exc):
            raise
        kwargs.pop("seed")
        stream = client.chat.completions.create(**kwargs)
        provider.seed_applied = False
        return stream

    provider.seed_applied = provider.seed is not None
    return stream


def _iter_completion(stream) -> Iterator[str]:
    for chunk in stream:
        content = chunk.choices[0].delta.content
        if content:
            yield content


class OllamaProvider:
    name = "ollama"

    def __init__(self, model: str, base_url: str = "http://localhost:11434",
                 num_ctx: int = 32768, seed: int | None = None):
        self.model = model
        self.base_url = base_url
        self.num_ctx = num_ctx
        self.seed = seed
        self.seed_applied: bool | None = None

    def stream(self, prompt: str, system: str | None = None) -> Iterator[str]:
        import ollama
        client = ollama.Client(host=self.base_url)
        options = {
            "temperature": FIXED_TEMPERATURE,
            "top_p": FIXED_TOP_P,
            "num_ctx": self.num_ctx,
        }
        if self.seed is not None:
            options["seed"] = self.seed
        self.seed_applied = self.seed is not None
        for chunk in client.chat(
            model=self.model,
            messages=_messages(prompt, system),
            stream=True,
            options=options,
        ):
            content = chunk["message"]["content"]
            if content:
                yield content


class LMStudioProvider:
    """LM Studio exposes an OpenAI-compatible API."""
    name = "lmstudio"

    def __init__(self, model: str, base_url: str = "http://localhost:1234",
                 seed: int | None = None):
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.seed = seed
        self.seed_applied: bool | None = None

    def stream(self, prompt: str, system: str | None = None) -> Iterator[str]:
        from openai import OpenAI
        client = OpenAI(base_url=f"{self.base_url}/v1", api_key="lm-studio")
        yield from _iter_completion(_create_completion(self, client, prompt, system))


class ClaudeProvider:
    name = "claude"
    DEFAULT_MODEL = "claude-sonnet-5"

    def __init__(self, model: str, api_key: str, seed: int | None = None):
        self.model = model or self.DEFAULT_MODEL
        self.api_key = api_key
        # Anthropic exposes no seed parameter, and temperature is rejected
        # outright on the current models (Sonnet 5, Opus 4.8/4.7, Fable 5) —
        # sending either is a 400. Claude runs cannot be pinned at all.
        self.seed = seed
        self.seed_applied = False

    def stream(self, prompt: str, system: str | None = None) -> Iterator[str]:
        import anthropic
        client = anthropic.Anthropic(api_key=self.api_key)
        kwargs = dict(
            model=self.model,
            max_tokens=CLAUDE_MAX_TOKENS,
            messages=[{"role": "user", "content": prompt}],
        )
        if system:
            kwargs["system"] = system
        with client.messages.stream(**kwargs) as stream:
            for text in stream.text_stream:
                yield text


class OpenAIProvider:
    name = "openai"
    DEFAULT_MODEL = "gpt-5.5"

    def __init__(self, model: str, api_key: str, seed: int | None = None):
        self.model = model or self.DEFAULT_MODEL
        self.api_key = api_key
        self.seed = seed
        self.seed_applied: bool | None = None

    def stream(self, prompt: str, system: str | None = None) -> Iterator[str]:
        from openai import OpenAI
        client = OpenAI(api_key=self.api_key)
        yield from _iter_completion(_create_completion(self, client, prompt, system))


class GeminiProvider:
    name = "gemini"
    DEFAULT_MODEL = "gemini-2.5-pro"

    def __init__(self, model: str, api_key: str, seed: int | None = None):
        self.model = model or self.DEFAULT_MODEL
        self.api_key = api_key
        self.seed = seed
        self.seed_applied: bool | None = None

    def stream(self, prompt: str, system: str | None = None) -> Iterator[str]:
        from google import genai
        from google.genai import types
        client = genai.Client(api_key=self.api_key)
        config_kwargs = {"temperature": FIXED_TEMPERATURE}
        if system:
            config_kwargs["system_instruction"] = system
        if self.seed is not None:
            config_kwargs["seed"] = self.seed
        self.seed_applied = self.seed is not None
        response = client.models.generate_content_stream(
            model=self.model,
            contents=prompt,
            config=types.GenerateContentConfig(**config_kwargs),
        )
        for chunk in response:
            if chunk.text:
                yield chunk.text


class GroqProvider:
    """Groq — ultra-fast inference via LPU hardware. OpenAI-compatible API."""
    name = "groq"
    # Groq announced deprecation of llama-3.3-70b-versatile (June 2026) and
    # recommends gpt-oss-120b as the migration target — faster and cheaper too.
    DEFAULT_MODEL = "openai/gpt-oss-120b"

    def __init__(self, model: str, api_key: str, seed: int | None = None):
        self.model = model or self.DEFAULT_MODEL
        self.api_key = api_key
        self.seed = seed
        self.seed_applied: bool | None = None

    def stream(self, prompt: str, system: str | None = None) -> Iterator[str]:
        from openai import OpenAI
        client = OpenAI(base_url="https://api.groq.com/openai/v1", api_key=self.api_key)
        yield from _iter_completion(_create_completion(self, client, prompt, system))


class MistralProvider:
    """Mistral AI — strong European provider with a code-focused model (Codestral)."""
    name = "mistral"
    DEFAULT_MODEL = "mistral-large-latest"

    def __init__(self, model: str, api_key: str, seed: int | None = None):
        self.model = model or self.DEFAULT_MODEL
        self.api_key = api_key
        self.seed = seed
        self.seed_applied: bool | None = None

    def stream(self, prompt: str, system: str | None = None) -> Iterator[str]:
        from openai import OpenAI
        client = OpenAI(base_url="https://api.mistral.ai/v1", api_key=self.api_key)
        yield from _iter_completion(_create_completion(self, client, prompt, system))


class OpenRouterProvider:
    """OpenRouter — one API key, 100+ models from every major provider."""
    name = "openrouter"
    DEFAULT_MODEL = "anthropic/claude-sonnet-5"

    def __init__(self, model: str, api_key: str, seed: int | None = None):
        self.model = model or self.DEFAULT_MODEL
        self.api_key = api_key
        self.seed = seed
        self.seed_applied: bool | None = None

    def stream(self, prompt: str, system: str | None = None) -> Iterator[str]:
        from openai import OpenAI, RateLimitError
        import httpx
        import time
        import json as _json

        client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=self.api_key,
            # read=300s matches server.py's first-chunk stall timeout, so a
            # cold-starting model doesn't trip this before that one applies.
            timeout=httpx.Timeout(connect=15.0, read=300.0, write=15.0, pool=5.0),
            default_headers={
                "HTTP-Referer": "https://github.com/apk-analyser",
                "X-Title": "APK Security Analyser",
            },
        )

        max_retries = 3
        for attempt in range(max_retries):
            yielded_any = False
            try:
                for chunk in _iter_completion(
                    _create_completion(self, client, prompt, system)
                ):
                    yielded_any = True
                    yield chunk
                return
            except RateLimitError as e:
                # Retrying after content has already reached the caller would
                # splice a partial report onto a fresh one. Rate limits are
                # normally raised when the request is created, so this is the
                # rare case — fail cleanly rather than emit a spliced report.
                if yielded_any:
                    raise RuntimeError(
                        "Rate limited by the upstream provider part-way through the "
                        "response. The partial report was discarded — please try again."
                    ) from e
                # Extract retry_after from OpenRouter's metadata if present
                wait = 35  # safe default
                try:
                    body = _json.loads(e.response.text)
                    wait = int(body["error"]["metadata"].get("retry_after_seconds", 35)) + 2
                except Exception:
                    pass
                if attempt < max_retries - 1:
                    yield f"{RETRY_NOTICE_PREFIX}⏳ Rate limited by upstream provider — retrying in {wait}s (attempt {attempt + 1}/{max_retries})…"
                    time.sleep(wait)
                else:
                    raise RuntimeError(
                        f"Rate limited after {max_retries} attempts. "
                        "The free-tier model is under heavy load — try again in a few minutes, "
                        "or switch to a paid model or a different provider."
                    ) from e


def build_provider(
    provider_name: str,
    model: str | None,
    env: dict,
    seed: int | None = None,
) -> (OllamaProvider | LMStudioProvider | ClaudeProvider | OpenAIProvider |
      GeminiProvider | GroqProvider | MistralProvider | OpenRouterProvider):
    """Factory — builds the right provider from name + env config."""
    p = provider_name.lower()

    if p == "ollama":
        return OllamaProvider(
            model=model or env.get("OLLAMA_MODEL", "qwen2.5-coder:32b"),
            base_url=env.get("OLLAMA_URL", "http://localhost:11434"),
            num_ctx=int(env.get("OLLAMA_NUM_CTX", 32768)),
            seed=seed,
        )
    if p == "lmstudio":
        return LMStudioProvider(
            model=model or env.get("LM_STUDIO_MODEL", "local-model"),
            base_url=env.get("LM_STUDIO_URL", "http://localhost:1234"),
            seed=seed,
        )
    if p == "claude":
        key = env.get("ANTHROPIC_API_KEY", "")
        if not key:
            raise ValueError("ANTHROPIC_API_KEY not set in .env")
        return ClaudeProvider(
            model=model or env.get("CLAUDE_MODEL", ClaudeProvider.DEFAULT_MODEL),
            api_key=key,
            seed=seed,
        )
    if p == "openai":
        key = env.get("OPENAI_API_KEY", "")
        if not key:
            raise ValueError("OPENAI_API_KEY not set in .env")
        return OpenAIProvider(
            model=model or env.get("OPENAI_MODEL", OpenAIProvider.DEFAULT_MODEL),
            api_key=key,
            seed=seed,
        )
    if p == "gemini":
        key = env.get("GEMINI_API_KEY", "")
        if not key:
            raise ValueError("GEMINI_API_KEY not set in .env")
        return GeminiProvider(
            model=model or env.get("GEMINI_MODEL", GeminiProvider.DEFAULT_MODEL),
            api_key=key,
            seed=seed,
        )

    if p == "groq":
        key = env.get("GROQ_API_KEY", "")
        if not key:
            raise ValueError("GROQ_API_KEY not set in .env")
        return GroqProvider(
            model=model or env.get("GROQ_MODEL", GroqProvider.DEFAULT_MODEL),
            api_key=key,
            seed=seed,
        )
    if p == "mistral":
        key = env.get("MISTRAL_API_KEY", "")
        if not key:
            raise ValueError("MISTRAL_API_KEY not set in .env")
        return MistralProvider(
            model=model or env.get("MISTRAL_MODEL", MistralProvider.DEFAULT_MODEL),
            api_key=key,
            seed=seed,
        )
    if p == "openrouter":
        key = env.get("OPENROUTER_API_KEY", "")
        if not key:
            raise ValueError("OPENROUTER_API_KEY not set in .env")
        return OpenRouterProvider(
            model=model or env.get("OPENROUTER_MODEL", OpenRouterProvider.DEFAULT_MODEL),
            api_key=key,
            seed=seed,
        )

    raise ValueError(
        f"Unknown provider '{provider_name}'. "
        "Choose from: ollama, lmstudio, claude, openai, gemini, groq, mistral, openrouter"
    )
