from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "WardenWG"
    app_env: str = "dev"
    debug: bool = False
    database_url: str = "sqlite:///./wardenwg.db"
    timezone: str = "UTC"
    manager_base_url: str = "https://sub.example.com"
    subscription_base_url: str = "https://sub.example.com"
    subscription_display_name: str = "WFQC8"
    admin_web_path: str = "/console"
    api_prefix: str = "/api/v1"
    admin_api_key: str = "change-me"
    wg_config_name: str = "wg0"
    wg_interface_mtu: int = 1420
    wg_persistent_keepalive: int = 25
    ssh_port: int = 22
    ssh_username: str = "root"
    ssh_private_key_path: str = "/run/secrets/wardenwg_ssh_key"
    ssh_password: str | None = None
    traffic_collection_interval_minutes: int = 5
    default_ruleset_base_url: str = (
        "https://raw.githubusercontent.com/MetaCubeX/meta-rules-dat/meta/geo"
    )
    template_dir: Path = Field(default_factory=lambda: Path(__file__).resolve().parents[1] / "templates")

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")


@lru_cache
def get_settings() -> Settings:
    return Settings()
