from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.device import Device
from app.models.node import Node
from app.models.traffic import DailyTrafficSummary


def get_user_traffic_rows(db: Session, user_id: int) -> list[tuple[DailyTrafficSummary, str]]:
    return db.execute(
        select(DailyTrafficSummary, Node.name)
        .join(Node, Node.id == DailyTrafficSummary.node_id)
        .where(DailyTrafficSummary.user_id == user_id)
        .order_by(DailyTrafficSummary.traffic_date.desc(), Node.sort_order.asc())
    ).all()


def get_device_traffic_rows(db: Session, device_id: int) -> list[tuple[DailyTrafficSummary, str]]:
    return db.execute(
        select(DailyTrafficSummary, Node.name)
        .join(Node, Node.id == DailyTrafficSummary.node_id)
        .where(DailyTrafficSummary.device_id == device_id)
        .order_by(DailyTrafficSummary.traffic_date.desc(), Node.sort_order.asc())
    ).all()
