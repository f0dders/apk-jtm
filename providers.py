"""
AI provider abstractions. Each provider implements stream(prompt) -> Iterator[str].

Local:  OllamaProvider, LMStudioProvider
Cloud:  ClaudeProvider, OpenAIProvider, GeminiProvider,
        GroqProvider, MistralProvider, OpenRouterProvider
"""

from __future__ import annotations
from typing import Iterator


class OllamaProvider:
    name = "ollama"

    def __init__(self, model: str, base_url: str = "http://localhost:11434"):
        self.model = model
        self.base_url = base_url

    def stream(self, prompt: str) -> Iterator[str]:
        import ollama
        client = ollama.Client(host=self.base_url)
        for chunk in client.chat(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            stream=True,
            options={"temperature": 0.2, "num_ctx": 16384},
        ):
            content = chunk["message"]["content"]
            if content:
                yield content


class LMStudioProvider:
    """LM Studio exposes an OpenAI-compatible API."""
    name = "lmstudio"

    def __init__(self, model: str, base_url: str = "http://localhost:1234"):
        self.model = model
        self.base_url = base_url.rstrip("/")

    def stream(self, prompt: str) -> Iterator[str]:
        from openai import OpenAI
        client = OpenAI(base_url=f"{self.base_url}/v1", api_key="lm-studio")
        stream = client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            stream=True,
            temperature=0.2,
        )
        for chunk in stream:
            content = chunk.choices[0].delta.content
            if content:
                yield content


class ClaudeProvider:
    name = "claude"
    DEFAULT_MODEL = "claude-sonnet-4-6"

    def __init__(self, model: str, api_key: str):
        self.model = model or self.DEFAULT_MODEL
        self.api_key = api_key

    def stream(self, prompt: str) -> Iterator[str]:
        import anthropic
        client = anthropic.Anthropic(api_key=self.api_key)
        with client.messages.stream(
            model=self.model,
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        ) as stream:
            for text in stream.text_stream:
                yield text


class OpenAIProvider:
    name = "openai"
    DEFAULT_MODEL = "gpt-4o"

    def __init__(self, model: str, api_key: str):
        self.model = model or self.DEFAULT_MODEL
        self.api_key = api_key

    def stream(self, prompt: str) -> Iterator[str]:
        from openai import OpenAI
        client = OpenAI(api_key=self.api_key)
        stream = client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            stream=True,
            temperature=0.2,
        )
        for chunk in stream:
            content = chunk.choices[0].delta.content
            if content:
                yield content


class GeminiProvider:
    name = "gemini"
    DEFAULT_MODEL = "gemini-1.5-pro"

    def __init__(self, model: str, api_key: str):
        self.model = model or self.DEFAULT_MODEL
        self.api_key = api_key

    def stream(self, prompt: str) -> Iterator[str]:
        import google.generativeai as genai
        genai.configure(api_key=self.api_key)
        model = genai.GenerativeModel(self.model)
        response = model.generate_content(
            prompt,
            stream=True,
            generation_config={"temperature": 0.2},
        )
        for chunk in response:
            if chunk.text:
                yield chunk.text


class GroqProvider:
    """Groq — ultra-fast inference via LPU hardware. OpenAI-compatible API."""
    name = "groq"
    DEFAULT_MODEL = "llama-3.3-70b-versatile"

    def __init__(self, model: str, api_key: str):
        self.model = model or self.DEFAULT_MODEL
        self.api_key = api_key

    def stream(self, prompt: str) -> Iterator[str]:
        from openai import OpenAI
        client = OpenAI(base_url="https://api.groq.com/openai/v1", api_key=self.api_key)
        stream = client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            stream=True,
            temperature=0.2,
        )
        for chunk in stream:
            content = chunk.choices[0].delta.content
            if content:
                yield content


class MistralProvider:
    """Mistral AI — strong European provider with a code-focused model (Codestral)."""
    name = "mistral"
    DEFAULT_MODEL = "mistral-large-latest"

    def __init__(self, model: str, api_key: str):
        self.model = model or self.DEFAULT_MODEL
        self.api_key = api_key

    def stream(self, prompt: str) -> Iterator[str]:
        from openai import OpenAI
        client = OpenAI(base_url="https://api.mistral.ai/v1", api_key=self.api_key)
        stream = client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            stream=True,
            temperature=0.2,
        )
        for chunk in stream:
            content = chunk.choices[0].delta.content
            if content:
                yield content


class OpenRouterProvider:
    """OpenRouter — one API key, 100+ models from every major provider."""
    name = "openrouter"
    DEFAULT_MODEL = "anthropic/claude-sonnet-4-6"

    def __init__(self, model: str, api_key: str):
        self.model = model or self.DEFAULT_MODEL
        self.api_key = api_key

    def stream(self, prompt: str) -> Iterator[str]:
        from openai import OpenAI, RateLimitError
        import httpx
        import time
        import json as _json

        client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=self.api_key,
            timeout=httpx.Timeout(connect=15.0, read=120.0, write=15.0, pool=5.0),
            default_headers={
                "HTTP-Referer": "https://github.com/apk-analyser",
                "X-Title": "APK Security Analyser",
            },
        )

        max_retries = 3
        for attempt in range(max_retries):
            try:
                stream = client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                    stream=True,
                    temperature=0.2,
                )
                for chunk in stream:
                    content = chunk.choices[0].delta.content
                    if content:
                        yield content
                return
            except RateLimitError as e:
                # Extract retry_after from OpenRouter's metadata if present
                wait = 35  # safe default
                try:
                    body = _json.loads(e.response.text)
                    wait = int(body["error"]["metadata"].get("retry_after_seconds", 35)) + 2
                except Exception:
                    pass
                if attempt < max_retries - 1:
                    yield f"\n\n⏳ Rate limited by upstream provider — retrying in {wait}s (attempt {attempt + 1}/{max_retries})…\n\n"
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
) -> (OllamaProvider | LMStudioProvider | ClaudeProvider | OpenAIProvider |
      GeminiProvider | GroqProvider | MistralProvider | OpenRouterProvider):
    """Factory — builds the right provider from name + env config."""
    p = provider_name.lower()

    if p == "ollama":
        return OllamaProvider(
            model=model or env.get("OLLAMA_MODEL", "qwen2.5-coder:32b"),
            base_url=env.get("OLLAMA_URL", "http://localhost:11434"),
        )
    if p == "lmstudio":
        return LMStudioProvider(
            model=model or env.get("LM_STUDIO_MODEL", "local-model"),
            base_url=env.get("LM_STUDIO_URL", "http://localhost:1234"),
        )
    if p == "claude":
        key = env.get("ANTHROPIC_API_KEY", "")
        if not key:
            raise ValueError("ANTHROPIC_API_KEY not set in .env")
        return ClaudeProvider(
            model=model or env.get("CLAUDE_MODEL", ClaudeProvider.DEFAULT_MODEL),
            api_key=key,
        )
    if p == "openai":
        key = env.get("OPENAI_API_KEY", "")
        if not key:
            raise ValueError("OPENAI_API_KEY not set in .env")
        return OpenAIProvider(
            model=model or env.get("OPENAI_MODEL", OpenAIProvider.DEFAULT_MODEL),
            api_key=key,
        )
    if p == "gemini":
        key = env.get("GEMINI_API_KEY", "")
        if not key:
            raise ValueError("GEMINI_API_KEY not set in .env")
        return GeminiProvider(
            model=model or env.get("GEMINI_MODEL", GeminiProvider.DEFAULT_MODEL),
            api_key=key,
        )

    if p == "groq":
        key = env.get("GROQ_API_KEY", "")
        if not key:
            raise ValueError("GROQ_API_KEY not set in .env")
        return GroqProvider(
            model=model or env.get("GROQ_MODEL", GroqProvider.DEFAULT_MODEL),
            api_key=key,
        )
    if p == "mistral":
        key = env.get("MISTRAL_API_KEY", "")
        if not key:
            raise ValueError("MISTRAL_API_KEY not set in .env")
        return MistralProvider(
            model=model or env.get("MISTRAL_MODEL", MistralProvider.DEFAULT_MODEL),
            api_key=key,
        )
    if p == "openrouter":
        key = env.get("OPENROUTER_API_KEY", "")
        if not key:
            raise ValueError("OPENROUTER_API_KEY not set in .env")
        return OpenRouterProvider(
            model=model or env.get("OPENROUTER_MODEL", OpenRouterProvider.DEFAULT_MODEL),
            api_key=key,
        )

    raise ValueError(
        f"Unknown provider '{provider_name}'. "
        "Choose from: ollama, lmstudio, claude, openai, gemini, groq, mistral, openrouter"
    )
