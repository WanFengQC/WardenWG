from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.core.config import get_settings
from app.core.security import generate_token
from app.models.node import Node
from app.models.peer import Peer
from app.models.user import User
from app.schemas.user import UserCreate
from app.services.ip_allocator import allocate_client_address
from app.services.keygen import generate_wireguard_keypair

settings = get_settings()


class UserService:
    def create_user(self, db: Session, payload: UserCreate) -> User:
        existing = db.scalar(select(User).where(User.username == payload.username))
        if existing:
            raise ValueError("用户名已存在")

        user = User(
            username=payload.username,
            subscription_token=generate_token(24),
            is_active=True,
            expires_at=payload.expires_at,
            total_quota_bytes=payload.total_quota_bytes,
            remark=payload.remark,
        )
        db.add(user)
        db.flush()

        nodes = db.scalars(select(Node).where(Node.is_active.is_(True)).order_by(Node.sort_order)).all()
        if not nodes:
            raise ValueError("没有可用节点，请先初始化节点信息")

        for node in nodes:
            private_key, public_key = generate_wireguard_keypair()
            peer = Peer(
                user_id=user.id,
                node_id=node.id,
                name=f"{payload.username}-{node.name}",
                client_address=allocate_client_address(db, node),
                private_key=private_key,
                public_key=public_key,
                allowed_ips="0.0.0.0/0, ::/0",
                persistent_keepalive=settings.wg_persistent_keepalive,
            )
            db.add(peer)

        db.flush()
        return self.get_user_by_id(db, user.id)

    def get_user_by_id(self, db: Session, user_id: int) -> User:
        user = db.scalar(
            select(User)
            .options(joinedload(User.peers).joinedload(Peer.node))
            .where(User.id == user_id)
        )
        if user is None:
            raise ValueError("用户不存在")
        return user

    def get_user_by_token(self, db: Session, token: str) -> User:
        user = db.scalar(
            select(User)
            .options(joinedload(User.peers).joinedload(Peer.node))
            .where(User.subscription_token == token)
        )
        if user is None:
            raise ValueError("订阅不存在")
        return user

    def list_users(self, db: Session) -> list[User]:
        return db.scalars(
            select(User)
            .options(joinedload(User.peers).joinedload(Peer.node))
            .order_by(User.id.desc())
        ).unique().all()

    def set_user_status(self, db: Session, user_id: int, is_active: bool) -> User:
        user = self.get_user_by_id(db, user_id)
        user.is_active = is_active
        user.updated_at = datetime.now(UTC).replace(tzinfo=None)
        db.flush()
        return user

    def validate_subscription_user(self, user: User) -> None:
        if not user.is_active:
            raise ValueError("用户已禁用")
        if user.expires_at and user.expires_at < datetime.now(UTC).replace(tzinfo=None):
            raise ValueError("用户已过期")
        if user.total_quota_bytes is not None and user.used_bytes >= user.total_quota_bytes:
            raise ValueError("用户流量已耗尽")
