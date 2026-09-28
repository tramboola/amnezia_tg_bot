import asyncio
import json

import pytest

from amnezia_bot.rpc import RpcServer


class ManagerStub:
    def __init__(self):
        self.calls = []

    def status(self):
        self.calls.append("status")
        return {"running": True}


@pytest.mark.parametrize(
    "payload",
    [
        {"op": "exec", "args": {"command": "id"}},
        {"op": "status", "args": {"path": "/etc/shadow"}},
        {"op": "status", "args": [], "extra": True},
        {"op": "delete", "args": {"container": "other"}},
        {"op": "__dict__", "args": {}},
    ],
)
async def test_rpc_rejects_non_whitelisted_operations_before_touching_manager(payload):
    manager = ManagerStub()
    response = await RpcServer(manager).dispatch(payload)
    assert response["error"]["code"] == "invalid_request"
    assert manager.calls == []


async def test_real_stream_protocol_returns_only_one_bounded_json_response():
    manager = ManagerStub()
    # Exercise framing with real streams; production binds a Unix socket, never TCP.
    service = RpcServer(manager)
    server = await asyncio.start_server(service.handle, "127.0.0.1", 0)
    try:
        port = server.sockets[0].getsockname()[1]
        reader, writer = await asyncio.open_connection("127.0.0.1", port)
        writer.write(b'{"op":"status","args":{}}\n')
        await writer.drain()
        assert json.loads(await reader.readline()) == {"result": {"running": True}}
        assert await reader.read() == b""
        writer.close()
        await writer.wait_closed()
        assert manager.calls == ["status"]
    finally:
        server.close()
        await server.wait_closed()


async def test_malformed_json_is_rejected_without_traceback_or_input_echo():
    service = RpcServer(ManagerStub())
    response = await service.parse(b"SECRET malformed\n")
    assert response["error"]["code"] == "invalid_request"
    assert "SECRET" not in json.dumps(response)
