from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Form, Query, Request, Response, status
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.database import get_db
from app.models.node import Node
from app.models.user import User
from app.schemas.user import UserCreate
from app.services.node_sync import NodeSyncService
from app.services.sessions import session_store
from app.services.traffic import TrafficCollectorService
from app.services.traffic_queries import get_user_traffic_rows
from app.services.users import UserService

settings = get_settings()
templates = Jinja2Templates(directory=str(settings.template_dir))
router = APIRouter(tags=["web"])

user_service = UserService()
traffic_service = TrafficCollectorService()
node_sync_service = NodeSyncService()

ADMIN_COOKIE = "wardenwg_admin_session"
USER_COOKIE = "wardenwg_user_session"


def _format_bytes(value: int) -> str:
    units = ["B", "KB", "MB", "GB", "TB"]
    size = float(value)
    for unit in units:
        if size < 1024 or unit == units[-1]:
            return f"{size:.2f} {unit}"
        size /= 1024
    return f"{value} B"


templates.env.filters["filesize"] = _format_bytes
templates.env.filters["datetime"] = lambda value: value.strftime("%Y-%m-%d %H:%M:%S") if value else "-"


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


@router.get("/")
def index() -> RedirectResponse:
    return _redirect("/admin")


@router.get("/admin/login")
def admin_login_page(request: Request) -> Response:
    return templates.TemplateResponse(request, "admin_login.html", {"error": None})


@router.post("/admin/login")
def admin_login(request: Request, admin_api_key: str = Form(...)) -> Response:
    if admin_api_key != settings.admin_api_key:
        return templates.TemplateResponse(
            request,
            "admin_login.html",
            {"error": "管理密钥错误"},
            status_code=400,
        )
    token = session_store.create(subject="admin", role="admin")
    response = _redirect("/admin")
    response.set_cookie(
        ADMIN_COOKIE,
        token,
        httponly=True,
        samesite="lax",
        secure=settings.app_env == "prod",
        max_age=43200,
    )
    return response


@router.post("/admin/logout")
def admin_logout(request: Request) -> RedirectResponse:
    session_store.delete(request.cookies.get(ADMIN_COOKIE))
    response = _redirect("/admin/login")
    response.delete_cookie(ADMIN_COOKIE)
    return response


@router.get("/admin")
def admin_dashboard(request: Request, db: Session = Depends(get_db)) -> Response:
    if not _get_admin_session(request):
        return _redirect("/admin/login")

    users = user_service.list_users(db)
    nodes = db.scalars(select(Node).order_by(Node.sort_order.asc())).all()
    total_users = db.scalar(select(func.count(User.id))) or 0
    active_users = db.scalar(select(func.count(User.id)).where(User.is_active.is_(True))) or 0
    total_used = sum(user.used_bytes for user in users)
    return templates.TemplateResponse(
        request,
        "admin_dashboard.html",
        {
            "users": users,
            "nodes": nodes,
            "total_users": total_users,
            "active_users": active_users,
            "total_used": total_used,
            "subscription_base_url": settings.subscription_base_url,
            "now": datetime.now(),
            "error": request.query_params.get("error"),
        },
    )


@router.post("/admin/users")
def admin_create_user(
    request: Request,
    username: str = Form(...),
    remark: str = Form(default=""),
    total_quota_gb: str = Form(default=""),
    expires_at: str = Form(default=""),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    if not _get_admin_session(request):
        return _redirect("/admin/login")
    try:
        quota_bytes = None
        if total_quota_gb.strip():
            quota_bytes = int(float(total_quota_gb) * 1024 * 1024 * 1024)
        expire_dt = None
        if expires_at.strip():
            expire_dt = datetime.fromisoformat(expires_at)

        payload = UserCreate(
            username=username.strip(),
            remark=remark.strip() or None,
            total_quota_bytes=quota_bytes,
            expires_at=expire_dt,
        )
        user_service.create_user(db, payload)
        db.commit()
        return _redirect("/admin")
    except ValueError as exc:
        db.rollback()
        return _redirect(f"/admin?error={str(exc)}")


@router.post("/admin/users/{user_id}/toggle")
def admin_toggle_user(user_id: int, request: Request, db: Session = Depends(get_db)) -> RedirectResponse:
    if not _get_admin_session(request):
        return _redirect("/admin/login")
    user = user_service.get_user_by_id(db, user_id)
    user_service.set_user_status(db, user_id, not user.is_active)
    db.commit()
    return _redirect("/admin")


@router.post("/admin/users/{user_id}/rotate-token")
def admin_rotate_token(user_id: int, request: Request, db: Session = Depends(get_db)) -> RedirectResponse:
    if not _get_admin_session(request):
        return _redirect("/admin/login")
    user = user_service.get_user_by_id(db, user_id)
    user.subscription_token = __import__("secrets").token_urlsafe(24)
    db.commit()
    return _redirect("/admin")


@router.post("/admin/tasks/collect-traffic")
def admin_collect_traffic(request: Request, db: Session = Depends(get_db)) -> RedirectResponse:
    if not _get_admin_session(request):
        return _redirect("/admin/login")
    nodes = db.scalars(select(Node).where(Node.is_active.is_(True))).all()
    for node in nodes:
        traffic_service.collect_from_node(db, node)
    db.commit()
    return _redirect("/admin")


@router.post("/admin/tasks/sync-peers")
def admin_sync_peers(request: Request, db: Session = Depends(get_db)) -> RedirectResponse:
    if not _get_admin_session(request):
        return _redirect("/admin/login")
    node_sync_service.sync_all_nodes(db)
    db.commit()
    return _redirect("/admin")


@router.get("/portal/login")
def portal_login_page(request: Request) -> Response:
    return templates.TemplateResponse(request, "portal_login.html", {"error": None})


@router.post("/portal/login")
def portal_login(request: Request, token: str = Form(...), db: Session = Depends(get_db)) -> Response:
    try:
        user = user_service.get_user_by_token(db, token.strip())
        user_service.validate_subscription_user(user)
    except ValueError:
        return templates.TemplateResponse(
            request,
            "portal_login.html",
            {"error": "订阅令牌无效或用户不可用"},
            status_code=400,
        )
    session_token = session_store.create(subject=user.subscription_token, role="user")
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


@router.get("/portal")
def portal_home(
    request: Request,
    token: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> Response:
    if token:
        try:
            user = user_service.get_user_by_token(db, token)
            user_service.validate_subscription_user(user)
            session_token = session_store.create(subject=user.subscription_token, role="user")
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

    token = _get_user_session(request)
    if not token:
        return _redirect("/portal/login")

    try:
        user = user_service.get_user_by_token(db, token)
        user_service.validate_subscription_user(user)
    except ValueError:
        session_store.delete(request.cookies.get(USER_COOKIE))
        return _redirect("/portal/login")

    rows = get_user_traffic_rows(db, user.id)
    summaries = [
        {
            "traffic_date": summary.traffic_date,
            "node_name": node_name,
            "rx_bytes": summary.rx_bytes,
            "tx_bytes": summary.tx_bytes,
            "total_bytes": summary.total_bytes,
            "latest_handshake_at": summary.latest_handshake_at,
        }
        for summary, node_name in rows
    ]
    main_yaml_url = f"{settings.subscription_base_url}/sub/{user.subscription_token}/main.yaml"
    nodes_yaml_url = f"{settings.subscription_base_url}/sub/{user.subscription_token}/nodes.yaml"
    return templates.TemplateResponse(
        request,
        "portal_home.html",
        {
            "user": user,
            "summaries": summaries,
            "main_yaml_url": main_yaml_url,
            "nodes_yaml_url": nodes_yaml_url,
        },
    )
