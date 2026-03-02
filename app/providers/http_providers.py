import base64

import httpx

from app.providers.base import BaseProvider, LLMResponse, LLMUsage


class OpenAIProvider(BaseProvider):
    name = 'openai'

    def __init__(self, api_key: str):
        self.api_key = api_key

    async def generate(self, model: str, system_prompt: str, messages: list[dict]) -> LLMResponse:
        payload = {
            'model': model,
            'messages': [{'role': 'system', 'content': system_prompt}, *messages],
        }
        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.post(
                'https://api.openai.com/v1/chat/completions',
                headers={'Authorization': f'Bearer {self.api_key}'},
                json=payload,
            )
            r.raise_for_status()
            data = r.json()
        usage = data.get('usage', {})
        return LLMResponse(data['choices'][0]['message']['content'], LLMUsage(usage.get('prompt_tokens', 0), usage.get('completion_tokens', 0)))


class AnthropicProvider(BaseProvider):
    name = 'anthropic'

    def __init__(self, api_key: str):
        self.api_key = api_key

    async def generate(self, model: str, system_prompt: str, messages: list[dict]) -> LLMResponse:
        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.post(
                'https://api.anthropic.com/v1/messages',
                headers={'x-api-key': self.api_key, 'anthropic-version': '2023-06-01'},
                json={'model': model, 'max_tokens': 1024, 'system': system_prompt, 'messages': messages},
            )
            r.raise_for_status()
            data = r.json()
        usage = data.get('usage', {})
        content = ''.join(part.get('text', '') for part in data.get('content', []))
        return LLMResponse(content, LLMUsage(usage.get('input_tokens', 0), usage.get('output_tokens', 0)))


class GoogleGeminiProvider(BaseProvider):
    name = 'gemini'

    def __init__(self, api_key: str):
        self.api_key = api_key

    async def generate(self, model: str, system_prompt: str, messages: list[dict]) -> LLMResponse:
        contents = [{'role': m['role'], 'parts': [{'text': m['content']}]} for m in messages]
        url = f'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={self.api_key}'
        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.post(url, json={'system_instruction': {'parts': [{'text': system_prompt}]}, 'contents': contents})
            r.raise_for_status()
            data = r.json()
        text = data['candidates'][0]['content']['parts'][0]['text']
        usage = data.get('usageMetadata', {})
        return LLMResponse(text, LLMUsage(usage.get('promptTokenCount', 0), usage.get('candidatesTokenCount', 0)))


class MistralProvider(OpenAIProvider):
    name = 'mistral'

    async def generate(self, model: str, system_prompt: str, messages: list[dict]) -> LLMResponse:
        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.post(
                'https://api.mistral.ai/v1/chat/completions',
                headers={'Authorization': f'Bearer {self.api_key}'},
                json={'model': model, 'messages': [{'role': 'system', 'content': system_prompt}, *messages]},
            )
            r.raise_for_status()
            data = r.json()
        usage = data.get('usage', {})
        return LLMResponse(data['choices'][0]['message']['content'], LLMUsage(usage.get('prompt_tokens', 0), usage.get('completion_tokens', 0)))


class CohereProvider(BaseProvider):
    name = 'cohere'

    def __init__(self, api_key: str):
        self.api_key = api_key

    async def generate(self, model: str, system_prompt: str, messages: list[dict]) -> LLMResponse:
        chat_history = [{'role': m['role'].upper(), 'message': m['content']} for m in messages[:-1]]
        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.post(
                'https://api.cohere.com/v1/chat',
                headers={'Authorization': f'Bearer {self.api_key}'},
                json={
                    'model': model,
                    'preamble': system_prompt,
                    'chat_history': chat_history,
                    'message': messages[-1]['content'] if messages else '',
                },
            )
            r.raise_for_status()
            data = r.json()
        billed = data.get('meta', {}).get('billed_units', {})
        return LLMResponse(data.get('text', ''), LLMUsage(billed.get('input_tokens', 0), billed.get('output_tokens', 0)))


class DeepSeekProvider(OpenAIProvider):
    name = 'deepseek'

    async def generate(self, model: str, system_prompt: str, messages: list[dict]) -> LLMResponse:
        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.post(
                'https://api.deepseek.com/chat/completions',
                headers={'Authorization': f'Bearer {self.api_key}'},
                json={'model': model, 'messages': [{'role': 'system', 'content': system_prompt}, *messages]},
            )
            r.raise_for_status()
            data = r.json()
        usage = data.get('usage', {})
        return LLMResponse(data['choices'][0]['message']['content'], LLMUsage(usage.get('prompt_tokens', 0), usage.get('completion_tokens', 0)))


class YandexGPTProvider(BaseProvider):
    name = 'yandexgpt'

    def __init__(self, api_key: str, folder_id: str):
        self.api_key = api_key
        self.folder_id = folder_id

    async def generate(self, model: str, system_prompt: str, messages: list[dict]) -> LLMResponse:
        payload = {
            'modelUri': f'gpt://{self.folder_id}/{model}',
            'completionOptions': {'stream': False, 'temperature': 0.6, 'maxTokens': '1000'},
            'messages': [{'role': 'system', 'text': system_prompt}] + [{'role': m['role'], 'text': m['content']} for m in messages],
        }
        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.post(
                'https://llm.api.cloud.yandex.net/foundationModels/v1/completion',
                headers={'Authorization': f'Api-Key {self.api_key}'},
                json=payload,
            )
            r.raise_for_status()
            data = r.json()
        alt = data['result']['alternatives'][0]['message']['text']
        usage = data.get('result', {}).get('usage', {})
        return LLMResponse(alt, LLMUsage(usage.get('inputTextTokens', 0), usage.get('completionTokens', 0)))


class GigaChatProvider(BaseProvider):
    name = 'gigachat'

    def __init__(self, api_key: str):
        self.api_key = api_key

    async def _token(self) -> str:
        auth = base64.b64encode(f'{self.api_key}:'.encode()).decode()
        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.post('https://ngw.devices.sberbank.ru:9443/api/v2/oauth', headers={'Authorization': f'Basic {auth}', 'RqUID': 'agenthub'}, data={'scope': 'GIGACHAT_API_PERS'})
            r.raise_for_status()
            return r.json()['access_token']

    async def generate(self, model: str, system_prompt: str, messages: list[dict]) -> LLMResponse:
        token = await self._token()
        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.post(
                'https://gigachat.devices.sberbank.ru/api/v1/chat/completions',
                headers={'Authorization': f'Bearer {token}'},
                json={'model': model, 'messages': [{'role': 'system', 'content': system_prompt}, *messages]},
            )
            r.raise_for_status()
            data = r.json()
        usage = data.get('usage', {})
        return LLMResponse(data['choices'][0]['message']['content'], LLMUsage(usage.get('prompt_tokens', 0), usage.get('completion_tokens', 0)))
