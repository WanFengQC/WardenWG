from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

import paramiko
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.node import Node
from app.models.peer import Peer
from app.models.user import User
from app.services.ssh import build_ssh_client

settings = get_settings()


@dataclass
class SyncResult:
    node_name: str
    peer_count: int
    mode: str


class NodeSyncService:
    def render_peer_block(self, peer: Peer) -> str:
        return (
            "[Peer]\n"
            f"# managed-by=wardenwg user={peer.user.username} peer_id={peer.id}\n"
            f"PublicKey = {peer.public_key}\n"
            f"AllowedIPs = {peer.client_address}\n"
        )

    def render_full_config(self, node: Node, peers: list[Peer]) -> str:
        header = (
            "# 该片段仅用于说明管理面写入的 peer 区块。\n"
            "# MVP 阶段建议保留现有 Interface 段和 NAT 规则，只替换 managed peers 部分。\n"
            "# managed-by=wardenwg begin\n"
        )
        body = "\n".join(self.render_peer_block(peer) for peer in peers)
        footer = "\n# managed-by=wardenwg end\n"
        return f"{header}{body}{footer}"

    def sync_node(self, db: Session, node: Node) -> SyncResult:
        peers = (
            db.query(Peer)
            .filter(Peer.node_id == node.id)
            .join(User, User.id == Peer.user_id)
            .filter(User.is_active.is_(True))
            .all()
        )
        config_snippet = self.render_full_config(node, peers)

        if settings.app_env == "dev":
            for peer in peers:
                peer.last_synced_at = datetime.now(UTC).replace(tzinfo=None)
            db.flush()
            return SyncResult(node_name=node.name, peer_count=len(peers), mode="dry-run")

        client = build_ssh_client(node.ssh_host, node.ssh_port)
        sftp = client.open_sftp()
        remote_tmp = f"/tmp/{node.name}-{settings.wg_config_name}.managed.conf"
        with sftp.open(remote_tmp, "w") as remote_file:
            remote_file.write(config_snippet)
        sftp.close()
        stdin, stdout, stderr = client.exec_command(
            "python3 /usr/local/bin/wardenwg-merge-peers "
            f"{settings.wg_config_name} {remote_tmp}"
        )
        exit_code = stdout.channel.recv_exit_status()
        client.close()
        if exit_code != 0:
            raise RuntimeError(stderr.read().decode("utf-8", errors="ignore"))
        for peer in peers:
            peer.last_synced_at = datetime.now(UTC).replace(tzinfo=None)
        db.flush()
        return SyncResult(node_name=node.name, peer_count=len(peers), mode="remote-merge")

    def sync_all_nodes(self, db: Session) -> list[SyncResult]:
        nodes = db.query(Node).filter(Node.is_active.is_(True)).order_by(Node.sort_order).all()
        return [self.sync_node(db, node) for node in nodes]
