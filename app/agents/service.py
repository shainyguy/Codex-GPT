from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.billing.service import debit_tokens, ensure_subscription_access
from app.core.models import Agent, AgentMemory
from app.providers.service import ProviderService
from app.tools.executor import ToolExecutor


provider_service = ProviderService()
tool_executor = ToolExecutor()


async def create_agent(db: AsyncSession, user_id: int, payload) -> Agent:
    await ensure_subscription_access(db, user_id)
    agent = Agent(
        user_id=user_id,
        name=payload.name,
        system_prompt=payload.system_prompt,
        model_name=f'{payload.provider}:{payload.model}',
        token_limit=payload.token_limit,
        tools=payload.tools,
        memory_enabled=payload.memory_enabled,
        behavior=payload.behavior,
    )
    db.add(agent)
    await db.commit()
    await db.refresh(agent)
    return agent


async def list_agents(db: AsyncSession, user_id: int) -> list[Agent]:
    rows = await db.scalars(select(Agent).where(Agent.user_id == user_id).order_by(Agent.id.desc()))
    return list(rows)


async def run_agent(db: AsyncSession, user_id: int, agent_id: int, text: str):
    agent = await db.scalar(select(Agent).where(Agent.id == agent_id, Agent.user_id == user_id))
    if not agent:
        raise HTTPException(status_code=404, detail='Agent not found')

    memory_msgs = []
    if agent.memory_enabled:
        history = await db.scalars(select(AgentMemory).where(AgentMemory.agent_id == agent.id, AgentMemory.user_id == user_id).order_by(AgentMemory.id.desc()).limit(10))
        memory_msgs = [{'role': m.role, 'content': m.message} for m in reversed(list(history))]

    tool_outputs = await tool_executor.run(agent.tools, text)
    user_content = text
    if tool_outputs:
        user_content += f'\n\nTool context: {tool_outputs}'

    model_provider, model = agent.model_name.split(':', maxsplit=1)
    response = await provider_service.generate(model_provider, model, agent.system_prompt, [*memory_msgs, {'role': 'user', 'content': user_content}])

    if response.usage.total_tokens > agent.token_limit:
        raise HTTPException(status_code=400, detail='Token limit exceeded for agent')

    await debit_tokens(db, user_id, agent.id, agent.model_name, response.usage.prompt_tokens, response.usage.completion_tokens)

    if agent.memory_enabled:
        db.add_all([
            AgentMemory(agent_id=agent.id, user_id=user_id, role='user', message=text),
            AgentMemory(agent_id=agent.id, user_id=user_id, role='assistant', message=response.content),
        ])
    await db.commit()

    return response
