import base64

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import x25519


def _to_wireguard_base64(raw: bytes) -> str:
    return base64.b64encode(raw).decode("ascii")


def generate_wireguard_keypair() -> tuple[str, str]:
    private_key = x25519.X25519PrivateKey.generate()
    private_raw = private_key.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_raw = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return _to_wireguard_base64(private_raw), _to_wireguard_base64(public_raw)

