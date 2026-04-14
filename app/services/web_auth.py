from __future__ import annotations

import hashlib
import hmac
import os
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models.device import Device
from app.models.login_ip_block import LoginIPBlock
from app.models.user import User
from app.models.web_account import WebAccount, WebAccountRole
from app.schemas.user import UserCreate
from app.services.users import UserService


@dataclass
class AuthResult:
    ok: bool
    reason: str | None = None
    account: WebAccount | None = None
    user: User | None = None
    device: Device | None = None


class WebAuthService:
    MAX_LOGIN_FAILURES = 3
    ADMIN_DEFAULT_USERNAME = "wfqc6"
    ADMIN_DEFAULT_PASSWORD = "wfqc6@123"
    USER_DEFAULT_USERNAME = "ringtion"
    USER_DEFAULT_PASSWORD = "ringtion@123"

    def __init__(self, user_service: UserService):
        self.user_service = user_service

    def _hash_password(self, password: str) -> str:
        iterations = 100_000
        salt = os.urandom(16).hex()
        digest = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            bytes.fromhex(salt),
            iterations,
        ).hex()
        return f"pbkdf2_sha256${iterations}${salt}${digest}"

    def _verify_password(self, password: str, stored_hash: str) -> bool:
        try:
            algorithm, iter_s, salt, digest = stored_hash.split("$", 3)
            if algorithm != "pbkdf2_sha256":
                return False
            iterations = int(iter_s)
        except ValueError:
            return False
        candidate = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            bytes.fromhex(salt),
            iterations,
        ).hex()
        return hmac.compare_digest(candidate, digest)

    def is_ip_blocked(self, db: Session, ip: str) -> bool:
        record = db.scalar(select(LoginIPBlock).where(LoginIPBlock.ip_address == ip))
        return bool(record and record.is_blocked)

    def record_failed_login(self, db: Session, ip: str) -> None:
        record = db.scalar(select(LoginIPBlock).where(LoginIPBlock.ip_address == ip))
        now = datetime.now(UTC).replace(tzinfo=None)
        if record is None:
            record = LoginIPBlock(ip_address=ip, failed_attempts=1, is_blocked=False, updated_at=now)
            db.add(record)
            return
        record.failed_attempts += 1
        record.updated_at = now
        if record.failed_attempts >= self.MAX_LOGIN_FAILURES:
            record.is_blocked = True

    def clear_failed_login(self, db: Session, ip: str) -> None:
        record = db.scalar(select(LoginIPBlock).where(LoginIPBlock.ip_address == ip))
        if record is None:
            return
        record.failed_attempts = 0
        record.is_blocked = False
        record.updated_at = datetime.now(UTC).replace(tzinfo=None)

    def authenticate_admin(self, db: Session, username: str, password: str) -> AuthResult:
        account = db.scalar(
            select(WebAccount).where(
                WebAccount.username == username,
                WebAccount.role == WebAccountRole.ADMIN,
            )
        )
        if account is None:
            return AuthResult(ok=False, reason="invalid_credentials")
        if not self._verify_password(password, account.password_hash):
            return AuthResult(ok=False, reason="invalid_credentials")
        return AuthResult(ok=True, account=account)

    def authenticate_user(self, db: Session, username: str, password: str) -> AuthResult:
        account = db.scalar(
            select(WebAccount)
            .options(joinedload(WebAccount.user).joinedload(User.devices))
            .where(
                WebAccount.username == username,
                WebAccount.role == WebAccountRole.USER,
            )
        )
        if account is None or account.user is None:
            return AuthResult(ok=False, reason="invalid_credentials")
        if not self._verify_password(password, account.password_hash):
            return AuthResult(ok=False, reason="invalid_credentials")

        user = account.user
        devices = sorted(user.devices, key=lambda item: item.id)
        active_device = next((item for item in devices if item.is_active), None)
        if active_device is None:
            return AuthResult(ok=False, reason="device_not_available")
        try:
            self.user_service.validate_device_subscription(active_device)
        except ValueError:
            return AuthResult(ok=False, reason="device_not_available")
        return AuthResult(ok=True, account=account, user=user, device=active_device)

    def ensure_default_accounts(self, db: Session) -> None:
        admin = db.scalar(
            select(WebAccount).where(
                WebAccount.username == self.ADMIN_DEFAULT_USERNAME,
                WebAccount.role == WebAccountRole.ADMIN,
            )
        )
        if admin is None:
            db.add(
                WebAccount(
                    username=self.ADMIN_DEFAULT_USERNAME,
                    role=WebAccountRole.ADMIN,
                    password_hash=self._hash_password(self.ADMIN_DEFAULT_PASSWORD),
                )
            )

        user = db.scalar(select(User).where(User.username == self.USER_DEFAULT_USERNAME))
        if user is None:
            user = self.user_service.create_user(
                db,
                UserCreate(
                    username=self.USER_DEFAULT_USERNAME,
                    initial_device_name="default",
                ),
            )

        normal_account = db.scalar(
            select(WebAccount).where(
                WebAccount.username == self.USER_DEFAULT_USERNAME,
                WebAccount.role == WebAccountRole.USER,
            )
        )
        if normal_account is None:
            db.add(
                WebAccount(
                    username=self.USER_DEFAULT_USERNAME,
                    role=WebAccountRole.USER,
                    password_hash=self._hash_password(self.USER_DEFAULT_PASSWORD),
                    user_id=user.id,
                )
            )
