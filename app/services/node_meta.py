from __future__ import annotations

from app.models.node import Node

# 可按需扩充；未命中则使用未知地区。
NODE_REGION_MAP: dict[str, str] = {
    "node-206": "美国",
    "node-100": "美国",
    "node-101": "法国",
}


def node_region(node: Node) -> str:
    return NODE_REGION_MAP.get(node.name, "未知")


def node_code(node: Node) -> str:
    return node.name.split("-")[-1] if "-" in node.name else node.name


def node_compact_name(node: Node, username: str, device_name: str) -> str:
    return f"{node_region(node)}{node_code(node)}-{username}-{device_name}"
