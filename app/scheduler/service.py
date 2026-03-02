from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from sqlalchemy import select

from app.agents.service import run_agent
from app.core.database import AsyncSessionLocal
from app.core.models import ScheduledTask


scheduler = AsyncIOScheduler(timezone='UTC')


async def execute_task(task_id: int) -> None:
    async with AsyncSessionLocal() as db:
        task = await db.scalar(select(ScheduledTask).where(ScheduledTask.id == task_id, ScheduledTask.active.is_(True)))
        if not task:
            return
        prompt = task.payload.get('prompt', '')
        await run_agent(db, task.user_id, task.agent_id, prompt)


def schedule_task(task: ScheduledTask) -> None:
    if task.cron_expr:
        scheduler.add_job(execute_task, trigger=CronTrigger.from_crontab(task.cron_expr), args=[task.id], id=f'task-{task.id}', replace_existing=True)
    elif task.run_at:
        scheduler.add_job(execute_task, trigger=DateTrigger(run_date=task.run_at), args=[task.id], id=f'task-{task.id}', replace_existing=True)


def start_scheduler() -> None:
    if not scheduler.running:
        scheduler.start()
