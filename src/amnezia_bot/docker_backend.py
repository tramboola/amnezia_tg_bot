import json
import subprocess
import time

from .manager import ManagerError

CONTAINER = "amnezia_tg_awg"
LABEL = "amnezia-tg.owner"
OWNER = "v1"


class DockerBackend:
    def __init__(self, image="amnezia-tg-awg:3.1", volume="amnezia_tg_data", runner=subprocess.run):
        self.image = image
        self.volume = volume
        self.runner = runner

    def _run(self, args, required=True):
        try:
            result = self.runner(["docker", *args], capture_output=True, text=True, timeout=60)
        except (OSError, subprocess.TimeoutExpired):
            raise ManagerError("docker_unavailable", "Docker недоступен; проверьте VPS.") from None
        if required and result.returncode:
            # Docker/awg output may contain keys. Expose only a fixed public error.
            raise ManagerError(
                "docker_failed",
                "Операция VPN не выполнена. Проверьте Docker, "
                "образ, /dev/net/tun и занятость UDP-порта на VPS.",
            )
        return result

    def _inspect(self):
        result = self._run(["inspect", CONTAINER], required=False)
        if result.returncode:
            names = self._run(
                ["ps", "-a", "--format", "{{.Names}}", "--filter", f"name=^/{CONTAINER}$"]
            )
            if names.stdout.strip():
                raise ManagerError("inspect_failed", "Не удалось проверить VPN-контейнер.")
            return None
        try:
            info = json.loads(result.stdout)[0]
            labels = info["Config"].get("Labels") or {}
            if labels.get(LABEL) != OWNER:
                raise ManagerError(
                    "foreign_container", "Имя VPN-контейнера занято другим проектом."
                )
            return info
        except (ValueError, KeyError, IndexError, TypeError):
            raise ManagerError("inspect_failed", "Не удалось проверить VPN-контейнер.") from None

    def apply(self, port, path):
        if path.name != "server.conf":
            raise ManagerError("invalid_path", "Некорректный путь серверного конфига.")
        info = self._inspect()
        if info and info["State"]["Running"]:
            bindings = info["HostConfig"].get("PortBindings", {}).get(f"{port}/udp") or []
            if not any(item["HostPort"] == str(port) for item in bindings):
                raise ManagerError("port_mismatch", "Порт контейнера отличается от настроек.")
        else:
            if info:
                self._run(["rm", "-f", CONTAINER])
            self._run(
                [
                    "run",
                    "-d",
                    "--name",
                    CONTAINER,
                    "--label",
                    f"{LABEL}={OWNER}",
                    "--restart",
                    "unless-stopped",
                    "--cap-add",
                    "NET_ADMIN",
                    "--device",
                    "/dev/net/tun:/dev/net/tun",
                    "--read-only",
                    "--security-opt",
                    "no-new-privileges:true",
                    "--tmpfs",
                    "/run:rw,nosuid,noexec,size=8m",
                    "--sysctl",
                    "net.ipv4.ip_forward=1",
                    "--sysctl",
                    "net.ipv6.conf.all.disable_ipv6=0",
                    "--pids-limit",
                    "128",
                    "--memory",
                    "256m",
                    "--cpus",
                    "1",
                    "--log-opt",
                    "max-size=3m",
                    "--log-opt",
                    "max-file=2",
                    "--volume",
                    f"{self.volume}:/data:ro",
                    "-p",
                    f"{port}:{port}/udp",
                    self.image,
                ]
            )
        for _ in range(40):
            ready = self._run(
                ["exec", CONTAINER, "test", "-S", "/run/amneziawg/awg0.sock"], required=False
            )
            if not ready.returncode:
                break
            time.sleep(0.25)
        else:
            raise ManagerError("vpn_not_ready", "AmneziaWG не запустился; проверьте VPS.")
        # Preserve sessions for retained peers and remove missing peers, including
        # the last peer when the desired configuration has no peers.
        self._run(["exec", CONTAINER, "awg", "syncconf", "awg0", "/data/server.conf"])

    def stop(self):
        if self._inspect():
            self._run(["rm", "-f", CONTAINER])

    def status(self):
        info = self._inspect()
        return bool(info and info["State"]["Running"])
