from datetime import date, datetime

from pydantic import BaseModel


class MessageResponse(BaseModel):
    message: str


class TrafficSummaryItem(BaseModel):
    traffic_date: date
    node_name: str
    rx_bytes: int
    tx_bytes: int
    total_bytes: int
    latest_handshake_at: datetime | None = None

