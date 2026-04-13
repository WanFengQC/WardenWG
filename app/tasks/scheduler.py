from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy import select

from app.core.config import get_settings
from app.db.database import SessionLocal
from app.models.node import Node
from app.services.traffic import TrafficCollectorService

settings = get_settings()
traffic_service = TrafficCollectorService()
scheduler = BackgroundScheduler(timezone=settings.timezone)


def collect_traffic_job() -> None:
    db = SessionLocal()
    try:
        nodes = db.scalars(select(Node).where(Node.is_active.is_(True))).all()
        for node in nodes:
            traffic_service.collect_from_node(db, node)
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def start_scheduler() -> None:
    if scheduler.running:
        return
    scheduler.add_job(
        collect_traffic_job,
        "interval",
        minutes=settings.traffic_collection_interval_minutes,
        id="collect-traffic",
        replace_existing=True,
    )
    scheduler.start()


def stop_scheduler() -> None:
    if scheduler.running:
        scheduler.shutdown(wait=False)

