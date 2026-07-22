"""
Classifies AI models into quality tiers based on known model names.
Only classifies models we're confident about — everything else is 'unknown'.
"""
from __future__ import annotations

# Patterns are matched case-insensitively as substrings of the model ID.
# Order within each tier doesn't matter; first match in tier order wins.

_FRONTIER = [
    # Anthropic
    "claude-opus", "claude-3-opus",
    "claude-sonnet-4", "claude-3-5-sonnet", "claude-3-7-sonnet", "claude-sonnet-4-6",
    "claude-sonnet-5", "claude-opus-4",
    # OpenAI
    "gpt-4o", "gpt-4-turbo", "gpt-4-1106", "gpt-4-0125",
    "gpt-5", "gpt-oss-120b",
    "o1-preview", "o1-mini", "o1-", "o3-",
    # Google
    "gemini-1.5-pro", "gemini-2.", "gemini-3.", "gemini-ultra", "gemini-exp",
    # Meta
    "llama-3.1-405b", "llama-3.3-70b",
    # DeepSeek
    "deepseek-r1", "deepseek-v3",
    # Mistral
    "mistral-large",
    "mixtral-8x22b",
    # Alibaba
    "qwen3.6-27b", "qwen3.6-35b",
]

_CAPABLE = [
    # Anthropic
    "claude-haiku",
    # OpenAI
    "gpt-4o-mini", "gpt-3.5-turbo", "gpt-oss-20b",
    # Google
    "gemini-1.5-flash", "gemini-flash",
    # Meta
    "llama-3.1-70b", "llama-3-70b", "llama-3.3-70b-instruct",
    # Mistral
    "mixtral-8x7b", "mistral-medium", "mistral-small", "mistral-nemo",
    # Cohere
    "command-r-plus", "command-r",
    # Alibaba
    "qwen2.5-72b", "qwen-72b", "qwen3.5-9b",
    # DeepSeek
    "deepseek-chat",
]

_BASIC = [
    # OpenRouter free-tier suffix
    ":free",
    # Small/old Meta models
    "llama-2", "llama-3.2-1b", "llama-3.2-3b",
    "llama-3.1-8b", "llama-3-8b",
    # Small Mistral
    "mistral-7b",
    # Google small
    "gemma-",
    # Microsoft small
    "phi-",
    # Small Qwen
    "qwen2.5-7b", "qwen-7b",
    # Generic small param indicators at end of model slug
    "-1b", "-3b", "-7b", "-8b",
]

# A few _FRONTIER entries are version-prefixes ("gpt-5", "gemini-2.") rather
# than full model names, so they'd also match that generation's cheap/fast
# siblings (e.g. "gpt-5-nano", "gemini-2.0-flash-lite"). Skip the frontier
# match when one of these qualifiers appears after it — such a slug falls
# through to capable/basic/unknown instead of being wrongly badged Frontier.
_FRONTIER_CHEAP_QUALIFIERS = ("-flash", "-nano", "-mini", "-lite")

# (display_label, hex_colour, description_for_disclaimer)
TIER_META: dict[str, tuple[str, str, str]] = {
    "frontier": ("Frontier", "#10b981", ""),
    "capable":  ("Capable",  "#3b82f6", ""),
    "basic":    ("Basic",    "#f59e0b",
                 "This report was written by a lightweight model. The findings above come "
                 "from the scan tools either way, but the interpretation is weaker: a "
                 "frontier model reasons about context far better, and is much more reliable "
                 "at telling a genuine problem from an expected one. Re-run with a more "
                 "capable model for a materially better report."),
    "unknown":  ("Unknown",  "#6b7280",
                 "The model that wrote this report is unclassified — typically a locally-run "
                 "one. The findings above come from the scan tools either way, but the "
                 "interpretation is only as good as the model: a frontier model reasons about "
                 "context far better, and is much more reliable at telling a genuine problem "
                 "from an expected one. Re-run with a known capable model to compare."),
}


def classify(model: str) -> str:
    """Return 'frontier', 'capable', 'basic', or 'unknown'."""
    m = model.lower()
    for pattern in _FRONTIER:
        idx = m.find(pattern)
        if idx == -1:
            continue
        rest = m[idx + len(pattern):]
        if any(q in rest for q in _FRONTIER_CHEAP_QUALIFIERS):
            continue
        return "frontier"
    for pattern in _CAPABLE:
        if pattern in m:
            return "capable"
    for pattern in _BASIC:
        if pattern in m:
            return "basic"
    return "unknown"
