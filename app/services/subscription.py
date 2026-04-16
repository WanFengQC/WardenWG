from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from app.core.config import get_settings
from app.models.device import Device
from app.models.node import Node
from app.services.node_meta import node_code, node_compact_name, node_region

settings = get_settings()
jinja_env = Environment(loader=FileSystemLoader(str(settings.template_dir)), autoescape=False)
jinja_env.globals["node_compact_name"] = node_compact_name
jinja_env.globals["node_region"] = node_region
jinja_env.globals["node_code"] = node_code


def amnezia_option_for_node(node: Node) -> dict[str, int | str] | None:
    enabled_nodes = {item.strip() for item in settings.amnezia_nodes.split(",") if item.strip()}
    if node.name not in enabled_nodes:
        return None
    return {
        "jc": settings.amnezia_jc,
        "jmin": settings.amnezia_jmin,
        "jmax": settings.amnezia_jmax,
        "s1": settings.amnezia_s1,
        "s2": settings.amnezia_s2,
        "h1": settings.amnezia_h1,
        "h2": settings.amnezia_h2,
        "h3": settings.amnezia_h3,
        "h4": settings.amnezia_h4,
    }


jinja_env.globals["amnezia_option_for_node"] = amnezia_option_for_node


class SubscriptionService:
    def build_nodes_yaml(self, device: Device) -> str:
        peers = sorted(device.peers, key=lambda item: item.node.sort_order)
        template = jinja_env.get_template("nodes.yaml.j2")
        return template.render(
            user=device.user,
            device=device,
            peers=peers,
            wg_interface_mtu=settings.wg_interface_mtu,
            wg_persistent_keepalive=settings.wg_persistent_keepalive,
        )

    def build_main_yaml(self, device: Device) -> str:
        template = jinja_env.get_template("main.yaml.j2")
        return template.render(
            user=device.user,
            device=device,
            nodes_url=f"{settings.subscription_base_url}/sub/{device.subscription_token}/nodes.yaml",
            ruleset_base_url=settings.default_ruleset_base_url.rstrip("/"),
        )
