import configparser
import json

import pytest

from amnezia_bot.manager import Manager, ManagerError


class MemoryVpn:
    def __init__(self):
        self.running = False
        self.config = ""
        self.fail = False

    def apply(self, port, path):
        if self.fail:
            raise ManagerError("vpn_failed", "VPN недоступен")
        self.config = path.read_text()
        self.running = True

    def stop(self):
        if self.fail:
            raise ManagerError("vpn_failed", "VPN недоступен")
        self.running = False

    def status(self):
        return self.running


def parsed(text):
    result = configparser.ConfigParser(interpolation=None)
    result.read_string(text)
    return result


@pytest.fixture
def setup(tmp_path):
    vpn = MemoryVpn()
    manager = Manager(tmp_path, vpn)
    manager.start("203.0.113.5", 51820)
    return manager, vpn, tmp_path


def test_profiles_have_unique_keys_addresses_and_matching_awg_parameters(setup):
    manager, vpn, _ = setup
    a = parsed(manager.create("alice-phone")["config"])
    b = parsed(manager.create("alice-laptop")["config"])
    server = parsed(vpn.config.split("[Peer]")[0])
    assert a["Interface"]["PrivateKey"] != b["Interface"]["PrivateKey"]
    assert a["Interface"]["Address"] != b["Interface"]["Address"]
    assert a["Peer"]["PresharedKey"] != b["Peer"]["PresharedKey"]
    assert a["Peer"]["Endpoint"] == "203.0.113.5:51820"
    assert a["Peer"]["AllowedIPs"] == "0.0.0.0/0, ::/0"
    for key in ("H1", "H2", "H3", "H4", "S1", "S2", "S3", "S4", "HeaderProtectionKey"):
        assert a["Interface"][key] == b["Interface"][key] == server["Interface"][key]
    assert a["Interface"]["PrivateKey"] not in vpn.config


def test_retry_creation_and_reload_preserve_the_exact_profile(setup):
    manager, vpn, path = setup
    first = manager.create("alice-phone")
    assert manager.create("alice-phone") == first
    restored = Manager(path, vpn)
    assert restored.download(first["id"]) == first
    assert len(restored.list()) == 1
    metadata = json.dumps(restored.status()) + json.dumps(restored.list())
    assert parsed(first["config"])["Interface"]["PrivateKey"] not in metadata
    assert first["config"] not in metadata


def test_revocation_is_durable_even_if_live_apply_fails(setup):
    manager, vpn, path = setup
    device = manager.create("alice-phone")
    vpn.fail = True
    with pytest.raises(ManagerError):
        manager.revoke(device["id"])
    restored = Manager(path, vpn)
    with pytest.raises(ManagerError, match="отозван"):
        restored.download(device["id"])
    vpn.fail = False
    restored.reconcile()
    assert "[Peer]" not in vpn.config
    assert restored.list() == []
    restored.stop()
    restored.start()
    assert "[Peer]" not in vpn.config


def test_failed_creation_retries_without_allocating_another_device(setup):
    manager, vpn, path = setup
    vpn.fail = True
    with pytest.raises(ManagerError):
        manager.create("alice-phone")
    vpn.fail = False
    restored = Manager(path, vpn)
    result = restored.create("alice-phone")
    assert len(restored.list()) == 1
    assert restored.download(result["id"]) == result


def test_stop_preserves_devices_and_delete_failure_preserves_identity(setup):
    manager, vpn, path = setup
    device = manager.create("alice-phone")
    manager.stop()
    restored = Manager(path, vpn)
    assert restored.download(device["id"]) == device
    assert not vpn.running
    vpn.fail = True
    with pytest.raises(ManagerError):
        restored.delete()
    vpn.fail = False
    restored.start()
    assert restored.download(device["id"]) == device
    restored.delete()
    assert not restored.status()["configured"]
    assert restored.list() == []


@pytest.mark.parametrize("name", ["../bad", "bad\n[Peer]", "", "x" * 33])
def test_invalid_device_names_cannot_change_state(setup, name):
    manager, _, _ = setup
    with pytest.raises(ManagerError):
        manager.create(name)
    assert manager.list() == []


def test_existing_devices_prevent_silent_endpoint_changes(setup):
    manager, _, _ = setup
    manager.create("alice")
    with pytest.raises(ManagerError):
        manager.start("203.0.113.6", 51821)


def test_corrupt_state_is_not_silently_replaced(tmp_path):
    (tmp_path / "state.json").write_text("broken")
    with pytest.raises(ManagerError):
        Manager(tmp_path, MemoryVpn())
    assert (tmp_path / "state.json").read_text() == "broken"


def test_status_distinguishes_pending_revocation_from_applied_state(setup):
    manager, vpn, _ = setup
    device = manager.create("alice")
    vpn.fail = True
    with pytest.raises(ManagerError):
        manager.revoke(device["id"])
    assert manager.status()["pending_changes"]
    vpn.fail = False
    manager.reconcile()
    assert not manager.status()["pending_changes"]


def test_ipv6_full_tunnel_has_an_address_and_padding_fits_1500_byte_path(setup):
    manager, _, _ = setup
    profile = parsed(manager.create("alice")["config"])
    assert "fd42:8::" in profile["Interface"]["Address"]
    mtu = int(profile["Interface"]["MTU"])
    padding = int(profile["Interface"]["ContentPaddingAddition"].split("-")[-1])
    # IPv4 UDP 28 + WG transport header/tag 32 + S4 nonce + maximum content padding.
    assert mtu + 28 + 32 + int(profile["Interface"]["S4"]) + padding <= 1500


def test_delete_cannot_restart_old_peers_after_final_state_write_fails(setup, monkeypatch):
    manager, vpn, path = setup
    device = manager.create("alice")
    real_commit = manager._commit

    def fail_erasure(state):
        if state["server"] is None:
            raise OSError("disk unavailable")
        real_commit(state)

    monkeypatch.setattr(manager, "_commit", fail_erasure)
    with pytest.raises(OSError):
        manager.delete()
    restored = Manager(path, vpn)
    restored.reconcile()
    assert not vpn.running
    assert not restored.status()["desired_running"]
    assert restored.download(device["id"]) == device
    restored.delete()
    assert not restored.status()["configured"]


def test_delete_does_not_touch_live_container_when_stop_intent_cannot_be_saved(setup, monkeypatch):
    manager, vpn, _ = setup
    manager.create("alice")

    def fail_commit(state):
        raise OSError("disk unavailable")

    monkeypatch.setattr(manager, "_commit", fail_commit)
    with pytest.raises(OSError):
        manager.delete()
    assert vpn.running
