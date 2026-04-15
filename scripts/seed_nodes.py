from app.db.database import SessionLocal
from app.models.node import Node

SEED_NODES = [
    {
        "name": "node-a",
        "display_name": "WardenWG-A",
        "public_ip": "203.0.113.10",
        "private_ip": "10.0.0.10",
        "ssh_host": "203.0.113.10",
        "ssh_port": 22,
        "wg_endpoint_host": "203.0.113.10",
        "wg_port": 52010,
        "wg_public_key": "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=",
        "wg_network": "10.66.10.0/24",
        "reserved_host_octet": 10,
        "sort_order": 10,
    },
    {
        "name": "node-b",
        "display_name": "WardenWG-B",
        "public_ip": "198.51.100.20",
        "private_ip": "10.0.0.20",
        "ssh_host": "198.51.100.20",
        "ssh_port": 22,
        "wg_endpoint_host": "198.51.100.20",
        "wg_port": 52020,
        "wg_public_key": "BBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB=",
        "wg_network": "10.66.20.0/24",
        "reserved_host_octet": 10,
        "sort_order": 20,
    },
    {
        "name": "node-c",
        "display_name": "WardenWG-C",
        "public_ip": "192.0.2.30",
        "private_ip": "10.0.0.30",
        "ssh_host": "192.0.2.30",
        "ssh_port": 22,
        "wg_endpoint_host": "192.0.2.30",
        "wg_port": 52030,
        "wg_public_key": "CCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCC=",
        "wg_network": "10.66.30.0/24",
        "reserved_host_octet": 10,
        "sort_order": 30,
    },
]


def main() -> None:
    db = SessionLocal()
    try:
        if db.query(Node).count() > 0:
            print("nodes already exist")
            return
        db.add_all([Node(**payload) for payload in SEED_NODES])
        db.commit()
        print("seeded nodes:", len(SEED_NODES))
    finally:
        db.close()


if __name__ == "__main__":
    main()
