from secrets import token_urlsafe

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.node import Node
from app.models.traffic import DailyTrafficSummary
from app.routers.deps import AdminAuth
from app.schemas.common import MessageResponse, TrafficSummaryItem
from app.schemas.user import UserCreate, UserRead, UserSubscriptionInfo
from app.services.users import UserService

router = APIRouter(prefix="/users", tags=["users"])
user_service = UserService()


@router.post("", response_model=UserRead, dependencies=[AdminAuth], status_code=201)
def create_user(payload: UserCreate, db: Session = Depends(get_db)) -> UserRead:
    try:
        user = user_service.create_user(db, payload)
        db.commit()
        db.refresh(user)
        return user
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("", response_model=list[UserRead], dependencies=[AdminAuth])
def list_users(db: Session = Depends(get_db)) -> list[UserRead]:
    return user_service.list_users(db)


@router.get("/{user_id}", response_model=UserRead, dependencies=[AdminAuth])
def get_user(user_id: int, db: Session = Depends(get_db)) -> UserRead:
    try:
        return user_service.get_user_by_id(db, user_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{user_id}/enable", response_model=UserRead, dependencies=[AdminAuth])
def enable_user(user_id: int, db: Session = Depends(get_db)) -> UserRead:
    try:
        user = user_service.set_user_status(db, user_id, True)
        db.commit()
        return user
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{user_id}/disable", response_model=UserRead, dependencies=[AdminAuth])
def disable_user(user_id: int, db: Session = Depends(get_db)) -> UserRead:
    try:
        user = user_service.set_user_status(db, user_id, False)
        db.commit()
        return user
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{user_id}/subscription", response_model=UserSubscriptionInfo, dependencies=[AdminAuth])
def get_user_subscription(user_id: int, db: Session = Depends(get_db)) -> UserSubscriptionInfo:
    try:
        user = user_service.get_user_by_id(db, user_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return UserSubscriptionInfo(
        username=user.username,
        subscription_token=user.subscription_token,
        main_yaml_url=f"/sub/{user.subscription_token}/main.yaml",
        nodes_yaml_url=f"/sub/{user.subscription_token}/nodes.yaml",
    )


@router.get("/{user_id}/traffic", response_model=list[TrafficSummaryItem], dependencies=[AdminAuth])
def get_user_traffic(user_id: int, db: Session = Depends(get_db)) -> list[TrafficSummaryItem]:
    try:
        user_service.get_user_by_id(db, user_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    rows = db.execute(
        select(DailyTrafficSummary, Node.name)
        .join(Node, Node.id == DailyTrafficSummary.node_id)
        .where(DailyTrafficSummary.user_id == user_id)
        .order_by(DailyTrafficSummary.traffic_date.desc(), Node.sort_order.asc())
    ).all()
    return [
        TrafficSummaryItem(
            traffic_date=summary.traffic_date,
            node_name=node_name,
            rx_bytes=summary.rx_bytes,
            tx_bytes=summary.tx_bytes,
            total_bytes=summary.total_bytes,
            latest_handshake_at=summary.latest_handshake_at,
        )
        for summary, node_name in rows
    ]


@router.post("/{user_id}/rotate-token", response_model=MessageResponse, dependencies=[AdminAuth])
def rotate_user_token(user_id: int, db: Session = Depends(get_db)) -> MessageResponse:
    try:
        user = user_service.get_user_by_id(db, user_id)
        user.subscription_token = token_urlsafe(24)
        db.commit()
        return MessageResponse(message="subscription token rotated")
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(exc)) from exc

