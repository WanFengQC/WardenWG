from app.db.database import SessionLocal
from app.models.node import Node

SEED_NODES = [
    {
        "name": "node-206",
        "display_name": "WardenWG-206",
        "public_ip": "147.224.34.115",
        "private_ip": "10.0.0.206",
        "ssh_host": "147.224.34.115",
        "ssh_port": 5522,
        "wg_endpoint_host": "147.224.34.115",
        "wg_port": 45221,
        "wg_public_key": "yZnmLpTh4HdzTezlqMo/EsnEc0rHkiq6KYxGDGFGsxE=",
        "wg_network": "10.66.1.0/24",
        "reserved_host_octet": 10,
        "sort_order": 10,
    },
    {
        "name": "node-100",
        "display_name": "WardenWG-100",
        "public_ip": "155.248.198.225",
        "private_ip": "10.0.0.100",
        "ssh_host": "155.248.198.225",
        "ssh_port": 5522,
        "wg_endpoint_host": "155.248.198.225",
        "wg_port": 46317,
        "wg_public_key": "7dCWWTbH7PFHMxurmTVXO3TkzfHID+DmmgiUO8vd0F0=",
        "wg_network": "10.66.2.0/24",
        "reserved_host_octet": 10,
        "sort_order": 20,
    },
    {
        "name": "node-101",
        "display_name": "WardenWG-101",
        "public_ip": "163.192.1.132",
        "private_ip": "10.0.0.101",
        "ssh_host": "163.192.1.132",
        "ssh_port": 5522,
        "wg_endpoint_host": "163.192.1.132",
        "wg_port": 47653,
        "wg_public_key": "4BeDVqguUwoKj804xjLjaNA4fHK60HguwtrcX8tei3o=",
        "wg_network": "10.66.3.0/24",
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

