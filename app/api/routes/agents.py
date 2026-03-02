from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.schemas import AgentCreate, AgentResponse, AgentRunRequest
from app.agents.service import create_agent, list_agents, run_agent
from app.auth.deps import get_current_user
from app.core.database import get_db
from app.core.models import User


router = APIRouter(prefix='/agents', tags=['agents'])


@router.post('')
async def create(payload: AgentCreate, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return await create_agent(db, user.id, payload)


@router.get('')
async def get_all(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return await list_agents(db, user.id)


@router.post('/{agent_id}/run', response_model=AgentResponse)
async def run(agent_id: int, payload: AgentRunRequest, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await run_agent(db, user.id, agent_id, payload.text)
    return AgentResponse(answer=result.content, spent_tokens=result.usage.total_tokens)
