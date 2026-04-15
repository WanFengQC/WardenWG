from __future__ import annotations

from datetime import datetime, timezone
from secrets import token_urlsafe

from fastapi import APIRouter, Depends, Form, Query, Request, Response, status
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.database import get_db
from app.models.node import Node
from app.models.user import User
from app.models.web_account import WebAccount
from app.schemas.user import DeviceCreate, UserCreate
from app.services.node_sync import NodeSyncService
from app.services.sessions import session_store
from app.services.node_meta import node_code, node_compact_name, node_region, node_short_label_from_name
from app.services.traffic import TrafficCollectorService
from app.services.traffic_queries import get_device_traffic_rows
from app.services.users import UserService
from app.services.web_auth import WebAuthService

settings = get_settings()
templates = Jinja2Templates(directory=str(settings.template_dir))
router = APIRouter(tags=["web"])

user_service = UserService()
web_auth_service = WebAuthService(user_service)
traffic_service = TrafficCollectorService()
node_sync_service = NodeSyncService()

ADMIN_COOKIE = "wardenwg_admin_session"
USER_COOKIE = "wardenwg_user_session"
ADMIN_BASE_PATH = settings.admin_web_path.strip() or "/console"
if not ADMIN_BASE_PATH.startswith("/"):
    ADMIN_BASE_PATH = f"/{ADMIN_BASE_PATH}"
ADMIN_BASE_PATH = ADMIN_BASE_PATH.rstrip("/") or "/console"
ADMIN_LOGIN_PATH = f"{ADMIN_BASE_PATH}/login"


def _format_bytes(value: int) -> str:
    units = ["B", "KB", "MB", "GB", "TB"]
    size = float(value)
    for unit in units:
        if size < 1024 or unit == units[-1]:
            return f"{size:.2f} {unit}"
        size /= 1024
    return f"{value} B"


def _format_date_utc(value: datetime | None) -> str:
    if not value:
        return "-"
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).strftime("%Y-%m-%d")


def _format_datetime_seconds_utc(value: datetime | None) -> str:
    if not value:
        return "-"
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


templates.env.filters["filesize"] = _format_bytes
templates.env.filters["datetime"] = _format_date_utc
templates.env.filters["datetime_seconds"] = _format_datetime_seconds_utc
templates.env.globals["node_compact_name"] = node_compact_name
templates.env.globals["node_region"] = node_region
templates.env.globals["node_code"] = node_code
templates.env.globals["admin_base_path"] = ADMIN_BASE_PATH

def _get_admin_session(request: Request) -> str | None:
    token = request.cookies.get(ADMIN_COOKIE)
    record = session_store.get(token, "admin")
    return record.subject if record else None


def _get_user_session(request: Request) -> str | None:
    token = request.cookies.get(USER_COOKIE)
    record = session_store.get(token, "user")
    return record.subject if record else None


def _redirect(url: str, status_code: int = status.HTTP_303_SEE_OTHER) -> RedirectResponse:
    return RedirectResponse(url=url, status_code=status_code)


def _client_ip(request: Request) -> str:
    xff = request.headers.get("x-forwarded-for", "").strip()
    if xff:
        return xff.split(",")[0].strip()
    xri = request.headers.get("x-real-ip", "").strip()
    if xri:
        return xri
    return request.client.host if request.client else "unknown"


@router.get("/")
def index() -> RedirectResponse:
    return _redirect("/portal/login")


@router.get(ADMIN_LOGIN_PATH)
def admin_login_page(request: Request) -> Response:
    return templates.TemplateResponse(request, "admin_login.html", {"error": None})


@router.post(ADMIN_LOGIN_PATH)
def admin_login(
    request: Request,
    username: str = Form(default=""),
    password: str = Form(default=""),
    db: Session = Depends(get_db),
) -> Response:
    client_ip = _client_ip(request)
    if web_auth_service.is_ip_blocked(db, client_ip):
        return templates.TemplateResponse(
            request,
            "admin_login.html",
            {"error": "用户名或密码错误"},
            status_code=403,
        )

    result = web_auth_service.authenticate_admin(db, username.strip(), password)
    if not result.ok:
        web_auth_service.record_failed_login(db, client_ip)
        db.commit()
        return templates.TemplateResponse(
            request,
            "admin_login.html",
            {"error": "用户名或密码错误"},
            status_code=400,
        )

    web_auth_service.clear_failed_login(db, client_ip)
    db.commit()
    token = session_store.create(subject=result.account.username if result.account else "admin", role="admin")
    response = _redirect(ADMIN_BASE_PATH)
    response.set_cookie(
        ADMIN_COOKIE,
        token,
        httponly=True,
        samesite="lax",
        secure=settings.app_env == "prod",
        max_age=43200,
    )
    return response


@router.post(f"{ADMIN_BASE_PATH}/logout")
def admin_logout(request: Request) -> RedirectResponse:
    session_store.delete(request.cookies.get(ADMIN_COOKIE))
    response = _redirect(ADMIN_LOGIN_PATH)
    response.delete_cookie(ADMIN_COOKIE)
    return response


@router.get(ADMIN_BASE_PATH)
def admin_dashboard(request: Request, db: Session = Depends(get_db)) -> Response:
    if not _get_admin_session(request):
        return _redirect(ADMIN_LOGIN_PATH)

    users = user_service.list_users(db)
    nodes = db.scalars(select(Node).order_by(Node.sort_order.asc())).all()
    total_users = db.scalar(select(func.count(User.id))) or 0
    active_users = db.scalar(select(func.count(User.id)).where(User.is_active.is_(True))) or 0
    total_devices = sum(len(user.devices) for user in users)
    total_used = sum(user.used_bytes for user in users)
    return templates.TemplateResponse(
        request,
        "admin_dashboard.html",
        {
            "users": users,
            "nodes": nodes,
            "total_users": total_users,
            "active_users": active_users,
            "total_devices": total_devices,
            "total_used": total_used,
            "subscription_base_url": settings.subscription_base_url,
            "now": datetime.now(),
            "error": request.query_params.get("error"),
        },
    )


@router.post(f"{ADMIN_BASE_PATH}/users")
def admin_create_user(
    request: Request,
    username: str = Form(...),
    initial_device_name: str = Form(default="default"),
    remark: str = Form(default=""),
    total_quota_gb: str = Form(default=""),
    device_limit: str = Form(default="5"),
    expires_at: str = Form(default=""),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    if not _get_admin_session(request):
        return _redirect(ADMIN_LOGIN_PATH)
    try:
        quota_bytes = None
        if total_quota_gb.strip():
            quota_bytes = int(float(total_quota_gb) * 1024 * 1024 * 1024)
        limit = 5
        if device_limit.strip():
            limit = int(device_limit)
        expire_dt = None
        if expires_at.strip():
            expire_dt = datetime.fromisoformat(expires_at)

        user_service.create_user(
            db,
            UserCreate(
                username=username.strip(),
                initial_device_name=initial_device_name.strip() or "default",
                remark=remark.strip() or None,
                total_quota_bytes=quota_bytes,
                device_limit=limit,
                expires_at=expire_dt,
            ),
        )
        db.commit()
        return _redirect(ADMIN_BASE_PATH)
    except ValueError as exc:
        db.rollback()
        return _redirect(f"{ADMIN_BASE_PATH}?error={str(exc)}")


@router.post(f"{ADMIN_BASE_PATH}/users/{user_id}/limits")
def admin_update_user_limits(
    user_id: int,
    request: Request,
    device_limit: str = Form(default="5"),
    total_quota_gb: str = Form(default=""),
    expires_at: str = Form(default=""),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    if not _get_admin_session(request):
        return _redirect(ADMIN_LOGIN_PATH)
    try:
        limit = int(device_limit.strip() or "5")
        quota_bytes = None
        if total_quota_gb.strip():
            quota_bytes = int(float(total_quota_gb) * 1024 * 1024 * 1024)
        expire_dt = None
        if expires_at.strip():
            expire_dt = datetime.fromisoformat(expires_at)
        user_service.update_user_limits(
            db,
            user_id,
            device_limit=limit,
            expires_at=expire_dt,
            total_quota_bytes=quota_bytes,
        )
        db.commit()
        return _redirect(ADMIN_BASE_PATH)
    except ValueError as exc:
        db.rollback()
        return _redirect(f"{ADMIN_BASE_PATH}?error={str(exc)}")


@router.post(f"{ADMIN_BASE_PATH}/users/{user_id}/devices")
def admin_create_device(
    user_id: int,
    request: Request,
    name: str = Form(...),
    remark: str = Form(default=""),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    if not _get_admin_session(request):
        return _redirect(ADMIN_LOGIN_PATH)
    try:
        user_service.create_device(db, user_id, DeviceCreate(name=name.strip(), remark=remark.strip() or None))
        db.commit()
        return _redirect(ADMIN_BASE_PATH)
    except ValueError as exc:
        db.rollback()
        return _redirect(f"{ADMIN_BASE_PATH}?error={str(exc)}")


@router.post(f"{ADMIN_BASE_PATH}/users/{user_id}/toggle")
def admin_toggle_user(user_id: int, request: Request, db: Session = Depends(get_db)) -> RedirectResponse:
    if not _get_admin_session(request):
        return _redirect(ADMIN_LOGIN_PATH)
    try:
        user = user_service.get_user_by_id(db, user_id)
        user_service.set_user_status(db, user_id, not user.is_active)
        node_sync_service.sync_all_nodes(db)
        db.commit()
        return _redirect(ADMIN_BASE_PATH)
    except Exception as exc:
        db.rollback()
        return _redirect(f"{ADMIN_BASE_PATH}?error={str(exc)}")


@router.post(f"{ADMIN_BASE_PATH}/users/{user_id}/delete")
def admin_delete_user(user_id: int, request: Request, db: Session = Depends(get_db)) -> RedirectResponse:
    if not _get_admin_session(request):
        return _redirect(ADMIN_LOGIN_PATH)
    try:
        user_service.delete_user(db, user_id)
        db.execute(delete(WebAccount).where(WebAccount.user_id == user_id))
        node_sync_service.sync_all_nodes(db)
        db.commit()
        return _redirect(ADMIN_BASE_PATH)
    except ValueError as exc:
        db.rollback()
        return _redirect(f"{ADMIN_BASE_PATH}?error={str(exc)}")


@router.post(f"{ADMIN_BASE_PATH}/devices/{device_id}/toggle")
def admin_toggle_device(device_id: int, request: Request, db: Session = Depends(get_db)) -> RedirectResponse:
    if not _get_admin_session(request):
        return _redirect(ADMIN_LOGIN_PATH)
    try:
        device = user_service.get_device_by_id(db, device_id)
        user_service.set_device_status(db, device_id, not device.is_active)
        node_sync_service.sync_all_nodes(db)
        db.commit()
        return _redirect(ADMIN_BASE_PATH)
    except Exception as exc:
        db.rollback()
        return _redirect(f"{ADMIN_BASE_PATH}?error={str(exc)}")


@router.post(f"{ADMIN_BASE_PATH}/devices/{device_id}/delete")
def admin_delete_device(device_id: int, request: Request, db: Session = Depends(get_db)) -> RedirectResponse:
    if not _get_admin_session(request):
        return _redirect(ADMIN_LOGIN_PATH)
    try:
        device = user_service.get_device_by_id(db, device_id)
        user = user_service.get_user_by_id(db, device.user_id)
        user_service.delete_device(db, user.id, device.id)
        node_sync_service.sync_all_nodes(db)
        db.commit()
        return _redirect(ADMIN_BASE_PATH)
    except ValueError as exc:
        db.rollback()
        return _redirect(f"{ADMIN_BASE_PATH}?error={str(exc)}")


@router.post(f"{ADMIN_BASE_PATH}/devices/{device_id}/rotate-token")
def admin_rotate_device_token(device_id: int, request: Request, db: Session = Depends(get_db)) -> RedirectResponse:
    if not _get_admin_session(request):
        return _redirect(ADMIN_LOGIN_PATH)
    device = user_service.get_device_by_id(db, device_id)
    device.subscription_token = token_urlsafe(24)
    db.commit()
    return _redirect(ADMIN_BASE_PATH)


@router.post(f"{ADMIN_BASE_PATH}/tasks/collect-traffic")
def admin_collect_traffic(request: Request, db: Session = Depends(get_db)) -> RedirectResponse:
    if not _get_admin_session(request):
        return _redirect(ADMIN_LOGIN_PATH)
    nodes = db.scalars(select(Node).where(Node.is_active.is_(True))).all()
    for node in nodes:
        traffic_service.collect_from_node(db, node)
    db.commit()
    return _redirect(ADMIN_BASE_PATH)


@router.post(f"{ADMIN_BASE_PATH}/tasks/sync-peers")
def admin_sync_peers(request: Request, db: Session = Depends(get_db)) -> RedirectResponse:
    if not _get_admin_session(request):
        return _redirect(ADMIN_LOGIN_PATH)
    node_sync_service.sync_all_nodes(db)
    db.commit()
    return _redirect(ADMIN_BASE_PATH)


@router.get("/portal/login")
def portal_login_page(request: Request) -> Response:
    return templates.TemplateResponse(request, "portal_login.html", {"error": None})


@router.post("/portal/login")
def portal_login(
    request: Request,
    username: str = Form(default=""),
    password: str = Form(default=""),
    db: Session = Depends(get_db),
) -> Response:
    client_ip = _client_ip(request)
    if web_auth_service.is_ip_blocked(db, client_ip):
        return templates.TemplateResponse(
            request,
            "portal_login.html",
            {"error": "用户名或密码错误"},
            status_code=400,
        )

    result = web_auth_service.authenticate_user(db, username.strip(), password)
    if not result.ok or result.device is None:
        web_auth_service.record_failed_login(db, client_ip)
        db.commit()
        return templates.TemplateResponse(
            request,
            "portal_login.html",
            {"error": "用户名或密码错误"},
            status_code=400,
        )

    web_auth_service.clear_failed_login(db, client_ip)
    db.commit()
    session_token = session_store.create(subject=result.device.subscription_token, role="user")
    response = _redirect("/portal")
    response.set_cookie(
        USER_COOKIE,
        session_token,
        httponly=True,
        samesite="lax",
        secure=settings.app_env == "prod",
        max_age=43200,
    )
    return response


@router.post("/portal/logout")
def portal_logout(request: Request) -> RedirectResponse:
    session_store.delete(request.cookies.get(USER_COOKIE))
    response = _redirect("/portal/login")
    response.delete_cookie(USER_COOKIE)
    return response


@router.post("/portal/devices")
def portal_create_device(
    request: Request,
    name: str = Form(...),
    remark: str = Form(default=""),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    session_subject = _get_user_session(request)
    if not session_subject:
        return _redirect("/portal/login")
    try:
        device = user_service.get_device_by_token(db, session_subject)
        user_service.validate_device_subscription(device)
        created = user_service.create_device(
            db,
            device.user_id,
            DeviceCreate(name=name.strip(), remark=remark.strip() or None),
        )
        db.commit()
        return _redirect(f"/portal?device_id={created.id}")
    except ValueError as exc:
        db.rollback()
        return _redirect(f"/portal?error={str(exc)}")


@router.post("/portal/devices/{device_id}/delete")
def portal_delete_device(
    device_id: int,
    request: Request,
    db: Session = Depends(get_db),
) -> RedirectResponse:
    session_subject = _get_user_session(request)
    if not session_subject:
        return _redirect("/portal/login")
    try:
        seed_device = user_service.get_device_by_token(db, session_subject)
        user_service.validate_device_subscription(seed_device)
        user = user_service.get_user_by_id(db, seed_device.user_id)
        target = next((item for item in user.devices if item.id == device_id), None)
        if target is None:
            return _redirect("/portal?error=设备不存在")
        deleting_session_device = seed_device.id == target.id
        user_service.delete_device(db, user.id, target.id)
        node_sync_service.sync_all_nodes(db)
        db.commit()

        if deleting_session_device:
            refreshed_user = user_service.get_user_by_id(db, user.id)
            replacement = next((item for item in refreshed_user.devices if item.is_active), None)
            if replacement is None and refreshed_user.devices:
                replacement = refreshed_user.devices[0]
            if replacement is None:
                session_store.delete(request.cookies.get(USER_COOKIE))
                response = _redirect("/portal/login")
                response.delete_cookie(USER_COOKIE)
                return response
            session_store.delete(request.cookies.get(USER_COOKIE))
            new_token = session_store.create(subject=replacement.subscription_token, role="user")
            response = _redirect(f"/portal?device_id={replacement.id}")
            response.set_cookie(
                USER_COOKIE,
                new_token,
                httponly=True,
                samesite="lax",
                secure=settings.app_env == "prod",
                max_age=43200,
            )
            return response
        return _redirect("/portal")
    except ValueError as exc:
        db.rollback()
        return _redirect(f"/portal?error={str(exc)}")


@router.get("/portal")
def portal_home(
    request: Request,
    token: str | None = Query(default=None),
    device_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
) -> Response:
    if token:
        try:
            device = user_service.get_device_by_token(db, token)
            user_service.validate_device_subscription(device)
            session_token = session_store.create(subject=device.subscription_token, role="user")
            response = _redirect("/portal")
            response.set_cookie(
                USER_COOKIE,
                session_token,
                httponly=True,
                samesite="lax",
                secure=settings.app_env == "prod",
                max_age=43200,
            )
            return response
        except ValueError:
            return _redirect("/portal/login")

    session_subject = _get_user_session(request)
    if not session_subject:
        return _redirect("/portal/login")

    try:
        seed_device = user_service.get_device_by_token(db, session_subject)
        user_service.validate_device_subscription(seed_device)
    except ValueError:
        session_store.delete(request.cookies.get(USER_COOKIE))
        return _redirect("/portal/login")

    user = user_service.get_user_by_id(db, seed_device.user_id)
    devices = sorted(user.devices, key=lambda item: item.id)
    current_device = next((item for item in devices if item.id == device_id), None) if device_id else None
    show_device_detail = current_device is not None

    summaries = []
    if current_device is not None:
        rows = get_device_traffic_rows(db, current_device.id)
        summaries = [
            {
                "traffic_date": summary.traffic_date,
                "node_name": node_short_label_from_name(node_name),
                "rx_bytes": summary.rx_bytes,
                "tx_bytes": summary.tx_bytes,
                "total_bytes": summary.total_bytes,
                "latest_handshake_at": summary.latest_handshake_at,
            }
            for summary, node_name in rows
        ]

    device_summaries: dict[int, list[dict[str, object]]] = {}
    for item in devices:
        item_rows = get_device_traffic_rows(db, item.id)
        device_summaries[item.id] = [
            {
                "traffic_date": summary.traffic_date,
                "node_name": node_short_label_from_name(node_name),
                "rx_bytes": summary.rx_bytes,
                "tx_bytes": summary.tx_bytes,
                "total_bytes": summary.total_bytes,
                "latest_handshake_at": summary.latest_handshake_at,
            }
            for summary, node_name in item_rows
        ]

    total_used_bytes = sum(item.used_bytes for item in devices)
    return templates.TemplateResponse(
        request,
        "portal_home.html",
        {
            "user": user,
            "device": current_device,
            "devices": devices,
            "show_device_detail": show_device_detail,
            "summaries": summaries,
            "device_summaries": device_summaries,
            "total_used_bytes": total_used_bytes,
            "subscription_base_url": settings.subscription_base_url,
            "portal_error": request.query_params.get("error"),
        },
    )

