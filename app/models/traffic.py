from datetime import date, datetime

from sqlalchemy import BigInteger, Date, DateTime, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class PeerTrafficSnapshot(Base):
    __tablename__ = "peer_traffic_snapshots"
    __table_args__ = (UniqueConstraint("peer_id", "captured_at", name="uq_peer_snapshot_time"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    peer_id: Mapped[int] = mapped_column(ForeignKey("peers.id", ondelete="CASCADE"), index=True)
    device_id: Mapped[int] = mapped_column(ForeignKey("devices.id", ondelete="CASCADE"), index=True)
    node_id: Mapped[int] = mapped_column(ForeignKey("nodes.id", ondelete="CASCADE"), index=True)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    transfer_rx_total: Mapped[int] = mapped_column(BigInteger, nullable=False)
    transfer_tx_total: Mapped[int] = mapped_column(BigInteger, nullable=False)
    delta_rx_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    delta_tx_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    latest_handshake_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    peer = relationship("Peer", back_populates="snapshots")


class DailyTrafficSummary(Base):
    __tablename__ = "daily_traffic_summaries"
    __table_args__ = (
        UniqueConstraint("user_id", "device_id", "node_id", "traffic_date", name="uq_daily_summary"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    device_id: Mapped[int] = mapped_column(ForeignKey("devices.id", ondelete="CASCADE"), index=True)
    node_id: Mapped[int] = mapped_column(ForeignKey("nodes.id", ondelete="CASCADE"), index=True)
    traffic_date: Mapped[date] = mapped_column(Date, index=True)
    rx_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    tx_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    total_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    latest_handshake_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    user = relationship("User", back_populates="summaries")
    device = relationship("Device", back_populates="summaries")
