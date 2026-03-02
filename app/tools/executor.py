from datetime import datetime

import httpx


class ToolExecutor:
    async def run(self, tools: dict, prompt: str) -> list[dict]:
        outputs: list[dict] = []
        if tools.get('text_analysis'):
            outputs.append({'tool': 'text_analysis', 'result': {'length': len(prompt), 'words': len(prompt.split())}})
        if webhook := tools.get('webhook_url'):
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(webhook, json={'prompt': prompt, 'ts': datetime.utcnow().isoformat()})
            outputs.append({'tool': 'webhook', 'status': resp.status_code})
        if tools.get('external_api'):
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(tools['external_api'])
            outputs.append({'tool': 'external_api', 'status': resp.status_code})
        return outputs
