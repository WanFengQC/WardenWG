from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from app.core.config import get_settings
from app.models.device import Device
from app.services.node_meta import node_code, node_compact_name, node_region

settings = get_settings()
jinja_env = Environment(loader=FileSystemLoader(str(settings.template_dir)), autoescape=False)
jinja_env.globals["node_compact_name"] = node_compact_name
jinja_env.globals["node_region"] = node_region
jinja_env.globals["node_code"] = node_code


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
