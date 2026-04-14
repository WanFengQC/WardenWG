from secrets import token_urlsafe

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.device import Device
from app.models.node import Node
from app.models.traffic import DailyTrafficSummary
from app.routers.deps import AdminAuth
from app.schemas.common import MessageResponse, TrafficSummaryItem
from app.schemas.user import DeviceCreate, DeviceRead, DeviceSubscriptionInfo, UserCreate, UserRead
from app.services.traffic_queries import get_device_traffic_rows, get_user_traffic_rows
from app.services.users import UserService

router = APIRouter(prefix="/users", tags=["users"])
device_router = APIRouter(prefix="/devices", tags=["devices"])
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


@router.post("/{user_id}/devices", response_model=DeviceRead, dependencies=[AdminAuth], status_code=201)
def create_device(user_id: int, payload: DeviceCreate, db: Session = Depends(get_db)) -> DeviceRead:
    try:
        device = user_service.create_device(db, user_id, payload)
        db.commit()
        return device
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


@router.get("/{user_id}/traffic", response_model=list[TrafficSummaryItem], dependencies=[AdminAuth])
def get_user_traffic(user_id: int, db: Session = Depends(get_db)) -> list[TrafficSummaryItem]:
    try:
        user_service.get_user_by_id(db, user_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    rows = get_user_traffic_rows(db, user_id)
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
        return MessageResponse(message="user token rotated")
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@device_router.get("/{device_id}", response_model=DeviceRead, dependencies=[AdminAuth])
def get_device(device_id: int, db: Session = Depends(get_db)) -> DeviceRead:
    try:
        return user_service.get_device_by_id(db, device_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@device_router.get("/{device_id}/subscription", response_model=DeviceSubscriptionInfo, dependencies=[AdminAuth])
def get_device_subscription(device_id: int, db: Session = Depends(get_db)) -> DeviceSubscriptionInfo:
    try:
        device = user_service.get_device_by_id(db, device_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return DeviceSubscriptionInfo(
        username=device.user.username,
        device_name=device.name,
        subscription_token=device.subscription_token,
        main_yaml_url=f"/sub/{device.subscription_token}/main.yaml",
        nodes_yaml_url=f"/sub/{device.subscription_token}/nodes.yaml",
    )


@device_router.get("/{device_id}/traffic", response_model=list[TrafficSummaryItem], dependencies=[AdminAuth])
def get_device_traffic(device_id: int, db: Session = Depends(get_db)) -> list[TrafficSummaryItem]:
    try:
        user_service.get_device_by_id(db, device_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    rows = get_device_traffic_rows(db, device_id)
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


@device_router.post("/{device_id}/enable", response_model=DeviceRead, dependencies=[AdminAuth])
def enable_device(device_id: int, db: Session = Depends(get_db)) -> DeviceRead:
    try:
        device = user_service.set_device_status(db, device_id, True)
        db.commit()
        return device
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@device_router.post("/{device_id}/disable", response_model=DeviceRead, dependencies=[AdminAuth])
def disable_device(device_id: int, db: Session = Depends(get_db)) -> DeviceRead:
    try:
        device = user_service.set_device_status(db, device_id, False)
        db.commit()
        return device
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@device_router.post("/{device_id}/rotate-token", response_model=MessageResponse, dependencies=[AdminAuth])
def rotate_device_token(device_id: int, db: Session = Depends(get_db)) -> MessageResponse:
    try:
        device = user_service.get_device_by_id(db, device_id)
        device.subscription_token = token_urlsafe(24)
        db.commit()
        return MessageResponse(message="device token rotated")
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(exc)) from exc

