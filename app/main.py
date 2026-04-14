from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.config import get_settings
from app.db.database import Base, engine
from app.db.database import SessionLocal
from app import models  # noqa: F401
from app.routers import nodes, subscriptions, tasks, users
from app.services.users import UserService
from app.services.web_auth import WebAuthService
from app.tasks.scheduler import start_scheduler, stop_scheduler
from app.web import router as web_router

settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        WebAuthService(UserService()).ensure_default_accounts(db)
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
    start_scheduler()
    yield
    stop_scheduler()


app = FastAPI(title=settings.app_name, debug=settings.debug, lifespan=lifespan)
app.include_router(users.router, prefix=settings.api_prefix)
app.include_router(users.device_router, prefix=settings.api_prefix)
app.include_router(nodes.router, prefix=settings.api_prefix)
app.include_router(tasks.router, prefix=settings.api_prefix)
app.include_router(subscriptions.router)
app.include_router(web_router)


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}
