import json
import subprocess

import pytest

from amnezia_bot.docker_backend import DockerBackend
from amnezia_bot.manager import ManagerError


class DockerRunner:
    def __init__(self, owned=True, running=True):
        self.owned = owned
        self.running = running
        self.exists = True
        self.calls = []

    def __call__(self, args, **kwargs):
        self.calls.append(args)
        if "inspect" in args:
            if not self.exists:
                return subprocess.CompletedProcess(args, 1, "", "No such object")
            container = {
                "Config": {"Labels": {"amnezia-tg.owner": "v1" if self.owned else "other"}},
                "State": {"Running": self.running},
                "HostConfig": {"PortBindings": {"51820/udp": [{"HostPort": "51820"}]}},
            }
            return subprocess.CompletedProcess(args, 0, json.dumps([container]), "")
        if "ps" in args:
            return subprocess.CompletedProcess(args, 0, "", "")
        if "rm" in args:
            self.exists = False
        if "run" in args:
            self.exists = True
            self.running = True
        return subprocess.CompletedProcess(args, 0, "ok", "")


def test_foreign_container_is_never_stopped_or_modified(tmp_path):
    runner = DockerRunner(owned=False)
    backend = DockerBackend(runner=runner)
    for operation in (lambda: backend.apply(51820, tmp_path / "server.conf"), backend.stop):
        with pytest.raises(ManagerError):
            operation()
    assert not any("rm" in call or "exec" in call for call in runner.calls)


def test_live_update_syncs_peers_without_restarting_container(tmp_path):
    runner = DockerRunner()
    backend = DockerBackend(runner=runner)
    backend.apply(51820, tmp_path / "server.conf")
    calls = runner.calls
    assert any(call[-4:] == ["awg", "syncconf", "awg0", "/data/server.conf"] for call in calls)
    assert not any("run" in call for call in calls)


def test_fresh_container_has_tun_and_no_profile_keys_in_command_arguments(tmp_path):
    runner = DockerRunner()
    runner.exists = False
    backend = DockerBackend(runner=runner)
    backend.apply(51820, tmp_path / "server.conf")
    call = next(call for call in runner.calls if "run" in call)
    assert "/dev/net/tun:/dev/net/tun" in call
    assert "51820:51820/udp" in call
    assert "amnezia-tg.owner=v1" in call
    assert "amnezia_tg_data:/data:ro" in call


def test_docker_errors_cannot_leak_command_output(tmp_path):
    def fail(args, **kwargs):
        return subprocess.CompletedProcess(args, 1, "PRIVATE KEY", "BOT TOKEN")

    with pytest.raises(ManagerError) as error:
        DockerBackend(runner=fail).apply(51820, tmp_path / "server.conf")
    assert "PRIVATE KEY" not in str(error.value) and "BOT TOKEN" not in str(error.value)
