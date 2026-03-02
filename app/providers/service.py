from fastapi import HTTPException

from app.core.config import get_settings
from app.providers.base import BaseProvider, LLMResponse
from app.providers.http_providers import (
    AnthropicProvider,
    CohereProvider,
    DeepSeekProvider,
    GigaChatProvider,
    GoogleGeminiProvider,
    MistralProvider,
    OpenAIProvider,
    YandexGPTProvider,
)


class ProviderService:
    def __init__(self) -> None:
        s = get_settings()
        self.providers: dict[str, BaseProvider] = {
            'openai': OpenAIProvider(s.openai_api_key),
            'anthropic': AnthropicProvider(s.anthropic_api_key),
            'gemini': GoogleGeminiProvider(s.gemini_api_key),
            'mistral': MistralProvider(s.mistral_api_key),
            'cohere': CohereProvider(s.cohere_api_key),
            'deepseek': DeepSeekProvider(s.deepseek_api_key),
            'yandexgpt': YandexGPTProvider(s.yandex_api_key, s.yandex_folder_id),
            'gigachat': GigaChatProvider(s.gigachat_api_key),
        }

    async def generate(self, provider_name: str, model: str, system_prompt: str, messages: list[dict]) -> LLMResponse:
        provider = self.providers.get(provider_name)
        if not provider:
            raise HTTPException(status_code=400, detail='Unknown provider')
        return await provider.generate(model=model, system_prompt=system_prompt, messages=messages)
