"""
model_tier.classify() is deliberately conservative — an unrecognised model
must fall back to 'unknown' rather than guess, since the tier badge is a
trust signal shown directly to non-technical users.
"""
import model_tier


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
