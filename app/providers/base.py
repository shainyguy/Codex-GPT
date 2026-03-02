from dataclasses import dataclass


@dataclass
class LLMUsage:
    prompt_tokens: int
    completion_tokens: int

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens


@dataclass
class LLMResponse:
    content: str
    usage: LLMUsage


class BaseProvider:
    name: str

    async def generate(self, model: str, system_prompt: str, messages: list[dict]) -> LLMResponse:
        raise NotImplementedError
