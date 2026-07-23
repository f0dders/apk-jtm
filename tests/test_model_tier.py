"""
Guards the model tier classification logic. Local model tags are written
with a colon before the size by Ollama and LM Studio (e.g. "gemma4:12b"),
whilst the pattern lists are written with hyphens ("gemma4-12b"). A missing
separator normalisation silently made EVERY locally-run model fall through
to "unknown" — every local report then carried the "unclassified model"
disclaimer despite running a known model. This file ensures colon and hyphen
forms classify identically, and verifies tier assignments for representative
model families.
"""
import model_tier


# ── Normalisation ───────────────────────────────────────────────────────────

def test_colon_form_tags_classify_same_as_hyphen_forms():
    """Ollama and LM Studio name models with a colon separator; patterns use
    hyphens. The classify() function normalises the separator before matching.
    Verify colon and hyphen forms produce identical tier assignments.
    """
    pairs = [
        ("gemma4:12b", "gemma4-12b"),
        ("qwen3.5:9b", "qwen3.5-9b"),
        ("llama3.1:8b", "llama3.1-8b"),
        ("deepseek-r1:14b", "deepseek-r1-14b"),
    ]

    for colon_form, hyphen_form in pairs:
        colon_tier = model_tier.classify(colon_form)
        hyphen_tier = model_tier.classify(hyphen_form)
        assert colon_tier == hyphen_tier, (
            f"Mismatch: {colon_form} ({colon_tier}) vs "
            f"{hyphen_form} ({hyphen_tier})"
        )


# ── Representative tags and expected tiers ──────────────────────────────────

def test_gemma_model_families():
    """Gemma 4 frontier models vs capable vs basic variants."""
    assert model_tier.classify("gemma4:12b") == "capable"
    assert model_tier.classify("gemma4:26b") == "frontier"
    assert model_tier.classify("gemma4:31b") == "frontier"
    # Edge variants (on-device) are basic
    assert model_tier.classify("gemma4-e2b") == "basic"
    assert model_tier.classify("gemma4-e4b") == "basic"
    # Gemma 3 is graded by size, same as Gemma 4 — the family name alone says
    # nothing about whether a model can reason its way through a scan.
    assert model_tier.classify("gemma3:27b") == "capable"
    assert model_tier.classify("gemma3:4b") == "basic"


def test_qwen_model_families():
    """Qwen 3.5 and 3.6 series with various sizes."""
    assert model_tier.classify("qwen3.5:9b") == "capable"
    assert model_tier.classify("qwen3.6:27b") == "frontier"
    assert model_tier.classify("qwen3.6:35b") == "frontier"
    # Smaller variants are basic
    assert model_tier.classify("qwen2.5-7b") == "basic"


def test_openai_gpt_oss_models():
    """GPT-OSS models have size-based tiers."""
    assert model_tier.classify("gpt-oss:20b") == "capable"
    assert model_tier.classify("gpt-oss:120b") == "frontier"
    assert model_tier.classify("gpt-oss-120b") == "frontier"


def test_meta_llama_models():
    """Llama 3.1 family with various sizes. The model_tier patterns use
    hyphens between version components (llama-3.1, not llama3.1).
    """
    assert model_tier.classify("llama-3.1:8b") == "basic"
    assert model_tier.classify("llama-3.1-8b") == "basic"
    assert model_tier.classify("llama-3.1-70b") == "capable"
    assert model_tier.classify("llama-3.1-405b") == "frontier"


def test_frontier_cloud_models():
    """Cloud frontier models from major providers."""
    assert model_tier.classify("claude-sonnet-5") == "frontier"
    assert model_tier.classify("gpt-4o") == "frontier"


def test_current_default_models_classify_as_frontier():
    """Regression guard: the app's own hardcoded provider defaults
    (providers.py DEFAULT_MODEL) must never silently show as 'Unknown'."""
    assert model_tier.classify("claude-sonnet-5") == "frontier"
    assert model_tier.classify("gpt-5.5") == "frontier"
    assert model_tier.classify("gemini-2.5-pro") == "frontier"
    assert model_tier.classify("openai/gpt-oss-120b") == "frontier"
    assert model_tier.classify("anthropic/claude-sonnet-5") == "frontier"


def test_shipped_ollama_default_is_not_unknown():
    """The Ollama default is the model most local users actually run, and it is
    the one the separator bug hit hardest: written 'gemma4:12b' it matched
    nothing, so every local report was badged Unknown and told the reader to
    re-run with a better model. Kept in step with server.py's OLLAMA_MODEL
    fallback and static/app.js's DEFAULT_MODELS.ollama.
    """
    tier = model_tier.classify("gemma4:12b")
    assert tier != "unknown", f"the shipped Ollama default classified as {tier}"


# ── Cheap qualifier filtering ───────────────────────────────────────────────

def test_small_local_distills_are_not_badged_frontier():
    """A 14B distillation sharing the name of a large frontier model must not
    be classified as frontier. The model_tier module filters frontier matches
    that have a cheap qualifier in the rest of the slug, which prevents this.
    """
    # DeepSeek R1 family: 671B is frontier, but 14B distil should not be
    assert model_tier.classify("deepseek-r1:671b") == "frontier"
    assert model_tier.classify("deepseek-r1:14b") != "frontier"
    assert model_tier.classify("deepseek-r1-14b") != "frontier"


def test_cheap_cloud_siblings_are_not_badged_frontier():
    """Cheap/fast siblings of frontier models must not be classified as
    frontier, even though their names share a frontier pattern prefix. The
    module checks for cheap qualifiers after each frontier pattern match.
    """
    # GPT-5 is a frontier pattern, but -nano siblings are not frontier
    assert model_tier.classify("gpt-5-nano") != "frontier"
    assert model_tier.classify("gpt-5-nano") == "basic"

    # Gemini-2 is a frontier pattern, but -flash siblings are not frontier
    # (they fall through to capable via the "-flash" pattern in _CAPABLE)
    tier = model_tier.classify("gemini-2.5-flash")
    assert tier != "frontier"
    assert tier == "capable"


# ── Legacy regression tests ─────────────────────────────────────────────────

def test_frontier_model_detected():
    assert model_tier.classify("claude-sonnet-4-6") == "frontier"
    assert model_tier.classify("gpt-4o") == "frontier"


def test_capable_model_detected():
    assert model_tier.classify("claude-haiku-4-5") == "capable"


def test_basic_model_detected():
    assert model_tier.classify("meta-llama/llama-3.1-8b-instruct:free") == "basic"


def test_unknown_model_falls_back_safely():
    assert model_tier.classify("some-random-experimental-model-v2") == "unknown"


def test_classification_is_case_insensitive():
    assert model_tier.classify("CLAUDE-SONNET-4-6") == "frontier"


def test_frontier_checked_before_basic():
    """':free' alone would match _BASIC, but a named frontier model with
    that suffix (as OpenRouter sometimes formats free-tier frontier access)
    must still resolve to frontier since _FRONTIER is checked first."""
    assert model_tier.classify("anthropic/claude-sonnet-4-6:free") == "frontier"


def test_frontier_prefix_does_not_swallow_cheap_siblings():
    """Some _FRONTIER entries are version-prefixes ("gpt-5", "gemini-2.")
    rather than full model names, so they'd otherwise also match that
    generation's cheap/fast siblings. Those must not be badged Frontier."""
    assert model_tier.classify("gpt-5-nano") != "frontier"
    assert model_tier.classify("gemini-2.0-flash-lite") != "frontier"
    assert model_tier.classify("gemini-3.0-flash") != "frontier"
