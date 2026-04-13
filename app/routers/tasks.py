from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.node import Node
from app.routers.deps import AdminAuth
from app.schemas.common import MessageResponse
from app.services.node_sync import NodeSyncService
from app.services.traffic import TrafficCollectorService

router = APIRouter(prefix="/tasks", tags=["tasks"], dependencies=[AdminAuth])
traffic_service = TrafficCollectorService()
node_sync_service = NodeSyncService()


@router.post("/collect-traffic", response_model=MessageResponse)
def collect_traffic(db: Session = Depends(get_db)) -> MessageResponse:
    nodes = db.scalars(select(Node).where(Node.is_active.is_(True))).all()
    total = 0
    try:
        for node in nodes:
            total += traffic_service.collect_from_node(db, node)
        db.commit()
        return MessageResponse(message=f"collected {total} peer snapshots")
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/sync-peers", response_model=MessageResponse)
def sync_peers(db: Session = Depends(get_db)) -> MessageResponse:
    try:
        results = node_sync_service.sync_all_nodes(db)
        db.commit()
        summary = ", ".join(f"{item.node_name}:{item.peer_count}({item.mode})" for item in results)
        return MessageResponse(message=f"sync completed: {summary}")
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(exc)) from exc

