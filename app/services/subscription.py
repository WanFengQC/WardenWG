from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from app.core.config import get_settings
from app.models.user import User

settings = get_settings()
jinja_env = Environment(loader=FileSystemLoader(str(settings.template_dir)), autoescape=False)


class SubscriptionService:
    def build_nodes_yaml(self, user: User) -> str:
        peers = sorted(user.peers, key=lambda item: item.node.sort_order)
        template = jinja_env.get_template("nodes.yaml.j2")
        return template.render(
            user=user,
            peers=peers,
            wg_interface_mtu=settings.wg_interface_mtu,
            wg_persistent_keepalive=settings.wg_persistent_keepalive,
        )

    def build_main_yaml(self, user: User) -> str:
        template = jinja_env.get_template("main.yaml.j2")
        return template.render(
            user=user,
            nodes_url=f"{settings.subscription_base_url}/sub/{user.subscription_token}/nodes.yaml",
            ruleset_base_url=settings.default_ruleset_base_url.rstrip("/"),
        )

