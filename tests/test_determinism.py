"""
Regenerating a report on unchanged scan data used to produce wildly different
output, because no provider pinned a sampling seed. These guard the seed
reaching each provider, the graceful degradation when a backend refuses it, and
the context-overflow guard that stops a silently truncated prompt being written
up as a confident report.
"""
import pytest

import providers
import server


# ── Seed derivation ─────────────────────────────────────────────────────────

def test_seed_is_stable_for_the_same_apk():
    md5 = "0123456789abcdef0123456789abcdef"
    assert providers.seed_for_hash(md5) == providers.seed_for_hash(md5)


def test_seed_differs_between_apks():
    assert providers.seed_for_hash("aaaaaaaa" + "0" * 24) != \
           providers.seed_for_hash("bbbbbbbb" + "0" * 24)


def test_seed_falls_back_when_no_hash_is_available():
    assert providers.seed_for_hash(None) == providers.DEFAULT_SEED
    assert providers.seed_for_hash("") == providers.DEFAULT_SEED
    assert providers.seed_for_hash("zzzzzzzz") == providers.DEFAULT_SEED


# ── Seed reaches the provider ───────────────────────────────────────────────

class _FakeCompletions:
    def __init__(self, reject_seed=False):
        self.reject_seed = reject_seed
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if self.reject_seed and "seed" in kwargs:
            from openai import BadRequestError
            raise BadRequestError(
                message="Unrecognized request argument supplied: seed",
                response=_FakeResponse(), body=None,
            )
        return iter(())


class _FakeResponse:
    status_code = 400
    headers: dict = {}
    request = None

    def json(self):
        return {"error": {"message": "Unrecognized request argument supplied: seed"}}


class _FakeClient:
    def __init__(self, reject_seed=False):
        self.chat = type("chat", (), {})()
        self.chat.completions = _FakeCompletions(reject_seed)


def test_openai_compatible_providers_send_seed_and_zero_temperature():
    provider = providers.GroqProvider(model="m", api_key="k", seed=1234)
    client = _FakeClient()
    providers._create_completion(provider, client, "user text", "system text")

    kwargs = client.chat.completions.calls[0]
    assert kwargs["seed"] == 1234
    assert kwargs["temperature"] == 0.0
    assert kwargs["messages"][0] == {"role": "system", "content": "system text"}
    assert kwargs["messages"][1] == {"role": "user", "content": "user text"}
    assert provider.seed_applied is True


def test_seed_rejection_retries_without_it_rather_than_failing():
    """Not every OpenAI-compatible backend accepts seed; losing the scan over it
    would be worse than losing reproducibility."""
    provider = providers.OpenRouterProvider(model="m", api_key="k", seed=99)
    client = _FakeClient(reject_seed=True)
    providers._create_completion(provider, client, "u", None)

    assert len(client.chat.completions.calls) == 2
    assert "seed" in client.chat.completions.calls[0]
    assert "seed" not in client.chat.completions.calls[1]
    # Recorded honestly so the UI never claims reproducibility it didn't get.
    assert provider.seed_applied is False


def test_unrelated_bad_request_is_not_swallowed():
    class _AlwaysFails(_FakeCompletions):
        def create(self, **kwargs):
            from openai import BadRequestError
            raise BadRequestError(message="context length exceeded",
                                  response=_FakeResponse(), body=None)

    provider = providers.GroqProvider(model="m", api_key="k", seed=1)
    client = _FakeClient()
    client.chat.completions = _AlwaysFails()

    from openai import BadRequestError
    with pytest.raises(BadRequestError):
        providers._create_completion(provider, client, "u", None)


def test_ollama_pins_seed_temperature_and_top_p(monkeypatch):
    captured = {}

    class _FakeOllamaClient:
        def __init__(self, host=None):
            pass

        def chat(self, **kwargs):
            captured.update(kwargs)
            return iter(())

    import sys, types
    fake = types.ModuleType("ollama")
    fake.Client = _FakeOllamaClient
    monkeypatch.setitem(sys.modules, "ollama", fake)

    provider = providers.OllamaProvider(model="m", seed=4242, num_ctx=8192)
    list(provider.stream("user text", "system text"))

    assert captured["options"]["seed"] == 4242
    assert captured["options"]["temperature"] == 0.0
    assert captured["options"]["top_p"] == 1.0
    assert captured["options"]["num_ctx"] == 8192
    assert captured["messages"][0]["role"] == "system"
    assert provider.seed_applied is True


def test_claude_never_sends_sampling_parameters():
    """temperature is rejected outright on current Claude models, and there is
    no seed at all — sending either is a 400 on the provider's own default."""
    provider = providers.ClaudeProvider(model="claude-sonnet-5", api_key="k", seed=7)
    assert provider.seed_applied is False
    assert providers.CLAUDE_MAX_TOKENS > 4096


# ── Context overflow ────────────────────────────────────────────────────────

class _ProviderWithWindow:
    def __init__(self, num_ctx):
        self.num_ctx = num_ctx


def test_overflow_guard_aborts_rather_than_warning():
    message = server._context_overflow(_ProviderWithWindow(512), "word " * 5000)
    assert message is not None
    assert "context window" in message


def test_overflow_guard_passes_a_prompt_that_fits():
    assert server._context_overflow(_ProviderWithWindow(32768), "word " * 100) is None


def test_overflow_guard_ignores_providers_with_no_declared_window():
    class _NoWindow:
        pass
    assert server._context_overflow(_NoWindow(), "word " * 100000) is None


def test_token_estimate_is_not_an_under_count():
    """chars/4 alone under-counts identifier-dense text, and under-counting is
    what lets an over-long prompt slip through."""
    dense = "android.permission.ACCESS_BACKGROUND_LOCATION " * 200
    assert server._estimate_tokens(dense) >= len(dense) / 4


# ── Prompt fingerprint ──────────────────────────────────────────────────────

def test_fingerprint_detects_a_changed_prompt():
    a = server._prompt_fingerprint("evidence A")
    assert a == server._prompt_fingerprint("evidence A")
    assert a != server._prompt_fingerprint("evidence B")
