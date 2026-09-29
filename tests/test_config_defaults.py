"""
GET /api/config used to carry its own hard-coded model defaults, separate
from the DEFAULT_MODEL constants in providers.py. They drifted: a fresh
install's Settings page offered gpt-4o, gemini-1.5-pro and Groq's retired
llama-3.3-70b-versatile, and saving the page wrote them into .env. The
Settings page must offer exactly the model a scan would use.
"""
import pytest

import providers
import server


@pytest.mark.parametrize("key, provider_cls", [
    ("ollama_model", providers.OllamaProvider),
    ("claude_model", providers.ClaudeProvider),
    ("openai_model", providers.OpenAIProvider),
    ("gemini_model", providers.GeminiProvider),
    ("groq_model", providers.GroqProvider),
    ("mistral_model", providers.MistralProvider),
    ("openrouter_model", providers.OpenRouterProvider),
])
async def test_settings_default_matches_provider_default(tmp_path, monkeypatch, key, provider_cls):
    monkeypatch.setattr(server, "ENV_PATH", tmp_path / ".env")  # no config yet
    config = await server.get_config()
    assert config[key] == provider_cls.DEFAULT_MODEL


def test_ollama_fallback_is_the_recommended_model():
    provider = providers.build_provider("ollama", model=None, env={})
    assert provider.model == providers.OllamaProvider.DEFAULT_MODEL
