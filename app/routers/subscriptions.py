from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.subscription_log import SubscriptionAccessLog
from app.services.subscription import SubscriptionService
from app.services.users import UserService

router = APIRouter(prefix="/sub", tags=["subscriptions"])
user_service = UserService()
subscription_service = SubscriptionService()


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
    return Response(content=body, media_type="text/yaml; charset=utf-8")


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
    return Response(content=body, media_type="text/yaml; charset=utf-8")

