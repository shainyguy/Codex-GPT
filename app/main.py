from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.router import api_router
from app.core.config import get_settings
from app.core.middleware import RateLimitMiddleware
from app.scheduler.service import start_scheduler


settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    start_scheduler()
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.add_middleware(RateLimitMiddleware, limit=120, period=60)
app.include_router(api_router)
app.mount('/webapp/static', StaticFiles(directory='app/webapp/static'), name='webapp-static')


@app.get('/health')
async def health():
    return {'status': 'ok'}


@app.get('/webapp')
async def webapp_index():
    return FileResponse('app/webapp/templates/index.html')
