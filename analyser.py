from typing import Iterator
from providers import OllamaProvider, LMStudioProvider, ClaudeProvider, OpenAIProvider, GeminiProvider

Provider = OllamaProvider | LMStudioProvider | ClaudeProvider | OpenAIProvider | GeminiProvider


def stream_analyse(prompt: str, provider: Provider) -> Iterator[str]:
    yield from provider.stream(prompt)
