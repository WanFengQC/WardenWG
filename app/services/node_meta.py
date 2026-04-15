from __future__ import annotations

from app.models.node import Node

# 可按需扩充；未命中则使用未知地区。
NODE_REGION_MAP: dict[str, tuple[str, str]] = {
    "node-206": ("US", "美国"),
    "node-100": ("US", "美国"),
    "node-101": ("FR", "法国"),
}


def country_flag(country_code: str | None) -> str:
    if not country_code:
        return "🏳️"
    code = country_code.strip().upper()
    if len(code) != 2 or not code.isalpha():
        return "🏳️"
    base = 127397
    return chr(ord(code[0]) + base) + chr(ord(code[1]) + base)


def node_region(node: Node) -> str:
    _, region = NODE_REGION_MAP.get(node.name, ("", "未知"))
    return region


def node_flag(node: Node) -> str:
    country_code, _ = NODE_REGION_MAP.get(node.name, ("", "未知"))
    return country_flag(country_code)


def node_display_with_region(node: Node) -> str:
    return f"{node_flag(node)} {node_region(node)} · {node.display_name}"
