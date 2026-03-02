from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user
from app.core.database import get_db
from app.core.models import ScheduledTask, User
from app.scheduler.service import schedule_task


router = APIRouter(prefix='/scheduler', tags=['scheduler'])


class TaskCreate(BaseModel):
    agent_id: int
    prompt: str
    run_at: datetime | None = None
    cron_expr: str | None = None


@router.post('/tasks')
async def create_task(payload: TaskCreate, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    task = ScheduledTask(
        user_id=user.id,
        agent_id=payload.agent_id,
        run_at=payload.run_at,
        cron_expr=payload.cron_expr,
        payload={'prompt': payload.prompt},
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)
    schedule_task(task)
    return task


@router.get('/tasks')
async def list_tasks(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    tasks = await db.scalars(select(ScheduledTask).where(ScheduledTask.user_id == user.id).order_by(ScheduledTask.id.desc()))
    return list(tasks)
