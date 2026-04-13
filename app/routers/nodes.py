from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.node import Node
from app.routers.deps import AdminAuth
from app.schemas.node import NodeRead, NodeSeed

router = APIRouter(prefix="/nodes", tags=["nodes"])


@router.get("", response_model=list[NodeRead], dependencies=[AdminAuth])
def list_nodes(db: Session = Depends(get_db)) -> list[NodeRead]:
    return db.scalars(select(Node).order_by(Node.sort_order.asc())).all()


@router.post("/seed", response_model=list[NodeRead], dependencies=[AdminAuth])
def seed_nodes(payload: list[NodeSeed], db: Session = Depends(get_db)) -> list[NodeRead]:
    if db.scalar(select(Node.id)):
        raise HTTPException(status_code=400, detail="nodes already initialized")
    nodes = [Node(**item.model_dump()) for item in payload]
    db.add_all(nodes)
    db.commit()
    return nodes

