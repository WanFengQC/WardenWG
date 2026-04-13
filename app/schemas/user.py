from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.node import NodeRead


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    expires_at: datetime | None = None
    total_quota_bytes: int | None = None
    remark: str | None = None


class PeerRead(BaseModel):
    id: int
    name: str
    client_address: str
    public_key: str
    allowed_ips: str
    latest_handshake_at: datetime | None = None
    transfer_rx_total: int
    transfer_tx_total: int
    node: NodeRead

    model_config = {"from_attributes": True}


class UserRead(BaseModel):
    id: int
    username: str
    subscription_token: str
    is_active: bool
    expires_at: datetime | None = None
    total_quota_bytes: int | None = None
    used_bytes: int
    remark: str | None = None
    created_at: datetime
    peers: list[PeerRead] = []

    model_config = {"from_attributes": True}


class UserSubscriptionInfo(BaseModel):
    username: str
    subscription_token: str
    main_yaml_url: str
    nodes_yaml_url: str

