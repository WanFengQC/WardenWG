from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class Peer(Base):
    __tablename__ = "peers"
    __table_args__ = (
        UniqueConstraint("node_id", "public_key", name="uq_peer_node_public_key"),
        UniqueConstraint("node_id", "client_address", name="uq_peer_node_client_address"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    node_id: Mapped[int] = mapped_column(ForeignKey("nodes.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(128), index=True)
    client_address: Mapped[str] = mapped_column(String(32))
    private_key: Mapped[str] = mapped_column(String(128))
    public_key: Mapped[str] = mapped_column(String(128), index=True)
    preshared_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    allowed_ips: Mapped[str] = mapped_column(String(128), default="0.0.0.0/0, ::/0")
    persistent_keepalive: Mapped[int] = mapped_column(Integer, default=25)
    latest_handshake_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    transfer_rx_total: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    transfer_tx_total: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    user = relationship("User", back_populates="peers")
    node = relationship("Node", back_populates="peers")
    snapshots = relationship("PeerTrafficSnapshot", back_populates="peer", cascade="all, delete-orphan")

