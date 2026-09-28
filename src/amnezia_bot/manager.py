import copy
import ipaddress
import json
import re
from pathlib import Path
from threading import RLock

from .profiles import client_config, new_device, new_server, server_config
from .storage import atomic_write, save_json


class ManagerError(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


def validate_name(name):
    if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,31}", name):
        raise ManagerError("invalid_name", "Имя: 1–32 латинских буквы, цифры, _ или -.")


def validate_endpoint(host, port):
    try:
        address = ipaddress.IPv4Address(host)
    except (ValueError, TypeError, ipaddress.AddressValueError):
        raise ManagerError("invalid_host", "Введите публичный IPv4 сервера.") from None
    if address.is_unspecified or address.is_loopback or address.is_multicast:
        raise ManagerError("invalid_host", "Введите публичный IPv4 сервера.")
    if type(port) is not int or not 1 <= port <= 65535:
        raise ManagerError("invalid_port", "UDP-порт должен быть от 1 до 65535.")
    return str(address)


class Manager:
    def __init__(self, path: Path, backend):
        self.path = Path(path)
        self.path.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.backend = backend
        self.lock = RLock()
        self.state_path = self.path / "state.json"
        self.runtime_path = self.path / "server.conf"
        self.applied_config = None
        self.state = {"version": 1, "server": None, "started": False, "devices": []}
        if self.state_path.exists():
            try:
                self.state = json.loads(self.state_path.read_text(encoding="utf-8"))
                if (
                    self.state["version"] != 1
                    or type(self.state["devices"]) is not list
                    or type(self.state["started"]) is not bool
                ):
                    raise ValueError
                if self.state["server"]:
                    server_config(self.state["server"], self.state["devices"])
            except (ValueError, KeyError, TypeError):
                raise ManagerError(
                    "state_invalid", "Хранилище повреждено; нужен администратор VPS."
                )

    def _commit(self, state):
        save_json(self.state_path, state)
        self.state = state

    def _server(self):
        if not self.state["server"]:
            raise ManagerError("not_configured", "Сначала настройте сервер.")
        return self.state["server"]

    def _device(self, device_id):
        for device in self.state["devices"]:
            if device["id"] == device_id:
                if device["revoked"]:
                    raise ManagerError("revoked", "Доступ устройства отозван.")
                return device
        raise ManagerError("not_found", "Устройство не найдено.")

    def reconcile(self):
        with self.lock:
            server = self.state["server"]
            if not server:
                self.backend.stop()
                atomic_write(self.runtime_path, "")
                return
            config = server_config(server, self.state["devices"])
            atomic_write(self.runtime_path, config)
            if self.state["started"]:
                if config != self.applied_config or not self.backend.status():
                    self.backend.apply(server["port"], self.runtime_path)
                    self.applied_config = config
            else:
                self.backend.stop()
                self.applied_config = None

    def start(self, host=None, port=51820):
        with self.lock:
            state = copy.deepcopy(self.state)
            if state["server"]:
                server = state["server"]
                if host is not None and (host != server["host"] or port != server["port"]):
                    raise ManagerError(
                        "endpoint_fixed", "Для смены адреса удалите сервер и конфиги."
                    )
            else:
                host = validate_endpoint(host, port)
                state["server"] = new_server(host, port)
            state["started"] = True
            self._commit(state)
            self.reconcile()
            return self.status()

    def stop(self):
        with self.lock:
            state = copy.deepcopy(self.state)
            state["started"] = False
            self._commit(state)
            self.reconcile()
            return self.status()

    def status(self):
        with self.lock:
            server = self.state["server"]
            running = self.backend.status()
            pending = running != self.state["started"]
            if server and self.state["started"]:
                pending = pending or (
                    server_config(server, self.state["devices"]) != self.applied_config
                )
            return {
                "configured": bool(server),
                "desired_running": self.state["started"],
                "running": running,
                "pending_changes": pending,
                "host": server["host"] if server else None,
                "port": server["port"] if server else None,
                "devices": len(self.list()),
            }

    def list(self):
        with self.lock:
            return [
                {key: device[key] for key in ("id", "name", "address", "created_at")}
                for device in self.state["devices"]
                if not device["revoked"]
            ]

    def create(self, name):
        with self.lock:
            validate_name(name)
            self._server()
            for device in self.state["devices"]:
                if device["name"] == name and not device["revoked"]:
                    return self.download(device["id"])
            used = {d["address"] for d in self.state["devices"] if not d["revoked"]}
            address = next(
                (f"10.8.0.{i}" for i in range(2, 255) if f"10.8.0.{i}" not in used), None
            )
            if not address:
                raise ManagerError("address_exhausted", "Достигнут лимит 253 устройств.")
            device = new_device(name, address)
            state = copy.deepcopy(self.state)
            state["devices"].append(device)
            self._commit(state)
            return self.download(device["id"])

    def download(self, device_id):
        with self.lock:
            device = self._device(device_id)
            server = self._server()
            self.reconcile()
            return {
                "id": device["id"],
                "name": device["name"],
                "config": client_config(server, device),
            }

    def revoke(self, device_id):
        with self.lock:
            state = copy.deepcopy(self.state)
            found = False
            for device in state["devices"]:
                if device["id"] == device_id:
                    found = True
                    device["revoked"] = True
                    device.pop("private_key", None)
                    device.pop("preshared_key", None)
            if not found:
                raise ManagerError("not_found", "Устройство не найдено.")
            self._commit(state)
            self.reconcile()
            return {"revoked": True}

    def delete(self):
        with self.lock:
            # Persist stop intent before removal; a crash must never resurrect old peers.
            # Retain identity until removal succeeds so failed deletion remains recoverable.
            state = copy.deepcopy(self.state)
            state["started"] = False
            self._commit(state)
            self.backend.stop()
            self._commit({"version": 1, "server": None, "started": False, "devices": []})
            atomic_write(self.runtime_path, "")
            return {"deleted": True}
