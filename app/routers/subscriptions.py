from urllib.parse import quote

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.database import get_db
from app.models.subscription_log import SubscriptionAccessLog
from app.services.subscription import SubscriptionService
from app.services.users import UserService

router = APIRouter(prefix="/sub", tags=["subscriptions"])
user_service = UserService()
subscription_service = SubscriptionService()
settings = get_settings()


def _load_subscription_user(db: Session, token: str):
    try:
        user = user_service.get_user_by_token(db, token)
        user_service.validate_subscription_user(user)
        return user
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


def _write_access_log(
    db: Session,
    user_id: int,
    token: str,
    resource: str,
    request: Request,
    user_agent: str | None,
) -> None:
    db.add(
        SubscriptionAccessLog(
            user_id=user_id,
            token=token,
            resource=resource,
            client_ip=request.client.host if request.client else None,
            user_agent=user_agent,
        )
    )
    db.commit()


def _build_subscription_headers(user, filename: str) -> dict[str, str]:
    upload = sum(peer.transfer_tx_total for peer in user.peers)
    download = sum(peer.transfer_rx_total for peer in user.peers)
    total = user.total_quota_bytes if user.total_quota_bytes is not None else download + upload
    expire = int(user.expires_at.timestamp()) if user.expires_at else 0
    display_name = settings.subscription_display_name.strip() or "WFQC8"
    encoded_filename = quote(filename)
    return {
        "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}",
        "Profile-Update-Interval": "24",
        "Profile-Web-Page-Url": f"{settings.subscription_base_url}/portal?token={user.subscription_token}",
        "Subscription-Userinfo": (
            f"upload={upload}; download={download}; total={total}; expire={expire}"
        ),
        "X-Profile-Name": display_name,
    }


@router.get("/{token}/main.yaml")
def get_main_yaml(
    token: str,
    request: Request,
    user_agent: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> Response:
    user = _load_subscription_user(db, token)
    body = subscription_service.build_main_yaml(user)
    _write_access_log(db, user.id, token, "main.yaml", request, user_agent)
    filename = f"{settings.subscription_display_name or 'WFQC8'}.yaml"
    return Response(
        content=body,
        media_type="text/yaml; charset=utf-8",
        headers=_build_subscription_headers(user, filename),
    )


@router.get("/{token}/nodes.yaml")
def get_nodes_yaml(
    token: str,
    request: Request,
    user_agent: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> Response:
    user = _load_subscription_user(db, token)
    body = subscription_service.build_nodes_yaml(user)
    _write_access_log(db, user.id, token, "nodes.yaml", request, user_agent)
    filename = f"{settings.subscription_display_name or 'WFQC8'}-nodes.yaml"
    return Response(
        content=body,
        media_type="text/yaml; charset=utf-8",
        headers=_build_subscription_headers(user, filename),
    )
