from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class Node(Base):
    __tablename__ = "nodes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(128))
    public_ip: Mapped[str] = mapped_column(String(64), unique=True)
    private_ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    ssh_port: Mapped[int] = mapped_column(default=22)
    ssh_host: Mapped[str] = mapped_column(String(128))
    wg_endpoint_host: Mapped[str] = mapped_column(String(128))
    wg_port: Mapped[int] = mapped_column(Integer)
    wg_public_key: Mapped[str] = mapped_column(String(128))
    wg_network: Mapped[str] = mapped_column(String(32))
    reserved_host_octet: Mapped[int] = mapped_column(Integer, default=10)
    sort_order: Mapped[int] = mapped_column(Integer, default=100)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    peers = relationship("Peer", back_populates="node", cascade="all, delete-orphan")
