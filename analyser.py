from typing import Iterator

from prompts import Prompt
from providers import OllamaProvider, LMStudioProvider, ClaudeProvider, OpenAIProvider, GeminiProvider

Provider = OllamaProvider | LMStudioProvider | ClaudeProvider | OpenAIProvider | GeminiProvider


def stream_analyse(prompt: Prompt, provider: Provider) -> Iterator[str]:
    yield from provider.stream(prompt.user, prompt.system)
