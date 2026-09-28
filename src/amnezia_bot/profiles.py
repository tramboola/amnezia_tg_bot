import base64
import ipaddress
import secrets
from datetime import UTC, datetime
from uuid import uuid4

from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey


def random_key():
    return base64.b64encode(secrets.token_bytes(32)).decode("ascii")


def keypair():
    key = X25519PrivateKey.generate()
    return (
        base64.b64encode(key.private_bytes_raw()).decode("ascii"),
        base64.b64encode(key.public_key().public_bytes_raw()).decode("ascii"),
    )


def new_server(host, port):
    private, public = keypair()
    parameters = {
        "Jc": "7",
        "Jmin": "20",
        "Jmax": "750",
        "S1": "64",
        "S2": "128",
        "S3": "32",
        "S4": "32",
        "HeaderProtectionKey": random_key(),
        "ContentPaddingAddition": "32-128",
        "RekeyAfterTime": "110-130",
        "RekeyTimeout": "4-7",
        "RejectAfterTime": "170-190",
        "KeepaliveTimeout": "8-12",
        "MaxHandshakeAttempts": "12-18",
    }
    for index in range(1, 5):
        lower = (index - 1) * 1_000_000_000 + secrets.randbelow(800_000_000) + 1
        parameters[f"H{index}"] = f"{lower}-{lower + 100_000}"
    return {
        "host": host,
        "port": port,
        "private_key": private,
        "public_key": public,
        "parameters": parameters,
    }


def new_device(name, address):
    private, public = keypair()
    return {
        "id": uuid4().hex,
        "name": name,
        "address": address,
        "private_key": private,
        "public_key": public,
        "preshared_key": random_key(),
        "created_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "revoked": False,
    }


def parameter_lines(server):
    return [f"{key} = {value}" for key, value in server["parameters"].items()]


def ipv6_address(device):
    return str(ipaddress.IPv6Address("fd42:8::") + int(device["address"].split(".")[-1]))


def server_config(server, devices):
    lines = [
        "[Interface]",
        f"PrivateKey = {server['private_key']}",
        f"ListenPort = {server['port']}",
        *parameter_lines(server),
    ]
    for device in devices:
        if not device["revoked"]:
            lines += [
                "",
                "[Peer]",
                f"PublicKey = {device['public_key']}",
                f"PresharedKey = {device['preshared_key']}",
                f"AllowedIPs = {device['address']}/32, {ipv6_address(device)}/128",
            ]
    return "\n".join(lines) + "\n"


def client_config(server, device):
    lines = [
        "[Interface]",
        f"PrivateKey = {device['private_key']}",
        f"Address = {device['address']}/32, {ipv6_address(device)}/128",
        "DNS = 1.1.1.1, 1.0.0.1",
        "MTU = 1280",
        *parameter_lines(server),
        "",
        "[Peer]",
        f"PublicKey = {server['public_key']}",
        f"PresharedKey = {device['preshared_key']}",
        f"Endpoint = {server['host']}:{server['port']}",
        "AllowedIPs = 0.0.0.0/0, ::/0",
        "PersistentKeepalive = 20-30",
    ]
    return "\n".join(lines) + "\n"
