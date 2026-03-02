from fastapi import APIRouter

from app.api.routes import agents, auth, billing, scheduler, ws


api_router = APIRouter(prefix='/api/v1')
api_router.include_router(auth.router)
api_router.include_router(agents.router)
api_router.include_router(billing.router)
api_router.include_router(scheduler.router)
api_router.include_router(ws.router)
