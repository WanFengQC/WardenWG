from __future__ import annotations

from app.models.node import Node

NODE_REGION_MAP: dict[str, str] = {
    "node-206": "美国",
    "node-100": "美国",
    "node-101": "美国",
}

REGION_FLAG_MAP: dict[str, str] = {
    "美国": "🇺🇸",
    "法国": "🇫🇷",
    "日本": "🇯🇵",
    "新加坡": "🇸🇬",
    "香港": "🇭🇰",
    "未知": "🏳️",
}


def node_region(node: Node) -> str:
    return NODE_REGION_MAP.get(node.name, "未知")


def node_flag(node: Node) -> str:
    return REGION_FLAG_MAP.get(node_region(node), "🏳️")


def node_code(node: Node) -> str:
    return node.name.split("-")[-1] if "-" in node.name else node.name


def node_compact_name(node: Node, username: str, device_name: str) -> str:
    return f"{node_flag(node)}{node_region(node)}-{node_code(node)}-{username}-{device_name}"


def node_short_label_from_name(node_name: str) -> str:
    region = NODE_REGION_MAP.get(node_name, "未知")
    flag = REGION_FLAG_MAP.get(region, "🏳️")
    code = node_name.split("-")[-1] if "-" in node_name else node_name
    return f"{flag}{region}-{code}"
