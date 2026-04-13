from ipaddress import ip_network

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.node import Node
from app.models.peer import Peer


def allocate_client_address(db: Session, node: Node) -> str:
    network = ip_network(node.wg_network, strict=True)
    used_addresses = {
        row[0]
        for row in db.execute(select(Peer.client_address).where(Peer.node_id == node.id)).all()
    }

    for host in network.hosts():
        if int(str(host).split(".")[-1]) <= node.reserved_host_octet:
            continue
        candidate = f"{host}/32"
        if candidate not in used_addresses:
            return candidate
    raise ValueError(f"节点 {node.name} 的地址池已耗尽")

