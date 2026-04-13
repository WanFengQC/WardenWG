from __future__ import annotations

from pathlib import Path

import paramiko

from app.core.config import get_settings

settings = get_settings()


def build_ssh_client(hostname: str, port: int) -> paramiko.SSHClient:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    private_key_path = Path(settings.ssh_private_key_path) if settings.ssh_private_key_path else None
    if private_key_path and private_key_path.exists():
        pkey = paramiko.Ed25519Key.from_private_key_file(str(private_key_path))
        client.connect(
            hostname=hostname,
            port=port,
            username=settings.ssh_username,
            pkey=pkey,
            timeout=10,
        )
        return client

    if settings.ssh_password:
        client.connect(
            hostname=hostname,
            port=port,
            username=settings.ssh_username,
            password=settings.ssh_password,
            timeout=10,
        )
        return client

    raise RuntimeError("未配置可用的 SSH 认证方式：请提供 SSH 私钥或 SSH_PASSWORD")

