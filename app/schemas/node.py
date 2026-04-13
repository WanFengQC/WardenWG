from pydantic import BaseModel


class NodeRead(BaseModel):
    id: int
    name: str
    display_name: str
    public_ip: str
    private_ip: str | None = None
    ssh_host: str
    ssh_port: int
    wg_endpoint_host: str
    wg_port: int
    wg_public_key: str
    wg_network: str
    is_active: bool

    model_config = {"from_attributes": True}


class NodeSeed(BaseModel):
    name: str
    display_name: str
    public_ip: str
    private_ip: str | None = None
    ssh_host: str
    ssh_port: int
    wg_endpoint_host: str
    wg_port: int
    wg_public_key: str
    wg_network: str
    reserved_host_octet: int = 10
    sort_order: int = 100

