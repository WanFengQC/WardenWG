from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

import paramiko
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.core.config import get_settings
from app.models.device import Device
from app.models.node import Node
from app.models.peer import Peer
from app.models.traffic import DailyTrafficSummary, PeerTrafficSnapshot
from app.services.ssh import build_ssh_client

settings = get_settings()


@dataclass
class DumpPeerRecord:
    public_key: str
    latest_handshake_at: datetime | None
    transfer_rx_total: int
    transfer_tx_total: int


class TrafficCollectorService:
    def _normalize_dt(self, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value
        return value.astimezone(UTC).replace(tzinfo=None)

    def _parse_dump(self, content: str) -> list[DumpPeerRecord]:
        rows = []
        for line in content.splitlines():
            columns = line.strip().split("\t")
            if len(columns) < 8 or columns[0] == settings.wg_config_name:
                continue
            handshake = None
            if columns[4] and columns[4] != "0":
                handshake = self._normalize_dt(datetime.fromtimestamp(int(columns[4]), tz=UTC))
            rows.append(
                DumpPeerRecord(
                    public_key=columns[0],
                    latest_handshake_at=handshake,
                    transfer_rx_total=int(columns[5]),
                    transfer_tx_total=int(columns[6]),
                )
            )
        return rows

    def _fetch_remote_dump(self, node: Node) -> str:
        if settings.app_env == "dev":
            return ""
        client = build_ssh_client(node.ssh_host, node.ssh_port)
        stdin, stdout, stderr = client.exec_command(f"wg show {settings.wg_config_name} dump")
        exit_code = stdout.channel.recv_exit_status()
        output = stdout.read().decode("utf-8", errors="ignore")
        error = stderr.read().decode("utf-8", errors="ignore")
        client.close()
        if exit_code != 0:
            raise RuntimeError(error)
        return output

    def collect_from_node(self, db: Session, node: Node, raw_dump: str | None = None) -> int:
        content = raw_dump if raw_dump is not None else self._fetch_remote_dump(node)
        records = self._parse_dump(content)
        if not records:
            return 0

        peers = {
            peer.public_key: peer
            for peer in db.scalars(
                select(Peer)
                .options(joinedload(Peer.user))
                .where(Peer.node_id == node.id)
            ).all()
        }
        captured_at = datetime.now(UTC).replace(tzinfo=None)
        touched = 0
        for record in records:
            peer = peers.get(record.public_key)
            if not peer:
                continue
            delta_rx = max(record.transfer_rx_total - peer.transfer_rx_total, 0)
            delta_tx = max(record.transfer_tx_total - peer.transfer_tx_total, 0)
            peer.transfer_rx_total = record.transfer_rx_total
            peer.transfer_tx_total = record.transfer_tx_total
            peer.latest_handshake_at = record.latest_handshake_at
            snapshot = PeerTrafficSnapshot(
                peer_id=peer.id,
                device_id=peer.device_id,
                node_id=node.id,
                captured_at=captured_at,
                transfer_rx_total=record.transfer_rx_total,
                transfer_tx_total=record.transfer_tx_total,
                delta_rx_bytes=delta_rx,
                delta_tx_bytes=delta_tx,
                latest_handshake_at=record.latest_handshake_at,
            )
            db.add(snapshot)
            self._upsert_daily_summary(
                db, peer, node, captured_at, delta_rx, delta_tx, record.latest_handshake_at
            )
            touched += 1
        return touched

    def _upsert_daily_summary(
        self,
        db: Session,
        peer: Peer,
        node: Node,
        captured_at: datetime,
        delta_rx: int,
        delta_tx: int,
        handshake_at: datetime | None,
    ) -> None:
        traffic_date = captured_at.date()
        summary = db.scalar(
            select(DailyTrafficSummary).where(
                DailyTrafficSummary.user_id == peer.user_id,
                DailyTrafficSummary.device_id == peer.device_id,
                DailyTrafficSummary.node_id == node.id,
                DailyTrafficSummary.traffic_date == traffic_date,
            )
        )
        if summary is None:
            summary = DailyTrafficSummary(
                user_id=peer.user_id,
                device_id=peer.device_id,
                node_id=node.id,
                traffic_date=traffic_date,
                rx_bytes=0,
                tx_bytes=0,
                total_bytes=0,
            )
            db.add(summary)
        summary.rx_bytes += delta_rx
        summary.tx_bytes += delta_tx
        summary.total_bytes = summary.rx_bytes + summary.tx_bytes
        normalized_handshake = self._normalize_dt(handshake_at)
        summary_handshake = self._normalize_dt(summary.latest_handshake_at)
        if normalized_handshake and (summary_handshake is None or normalized_handshake > summary_handshake):
            summary.latest_handshake_at = normalized_handshake
        peer.user.used_bytes += delta_rx + delta_tx
        peer.device.used_bytes += delta_rx + delta_tx
