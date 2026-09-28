import asyncio
import json
import logging
import os
from pathlib import Path

from .docker_backend import DockerBackend
from .manager import Manager, ManagerError

LIMIT = 262_144
OPERATIONS = {
    "status": (set(), set()),
    "list": (set(), set()),
    "start": (set(), {"host", "port"}),
    "stop": (set(), set()),
    "create": ({"name"}, {"name"}),
    "download": ({"device_id"}, {"device_id"}),
    "revoke": ({"device_id"}, {"device_id"}),
    "delete": (set(), set()),
}
LOG = logging.getLogger(__name__)


def invalid_request():
    return {"error": {"code": "invalid_request", "message": "Некорректный запрос менеджеру."}}


class RpcServer:
    def __init__(self, manager):
        self.manager = manager
        self.lock = asyncio.Lock()

    async def dispatch(self, payload):
        if type(payload) is not dict or set(payload) != {"op", "args"}:
            return invalid_request()
        operation, args = payload["op"], payload["args"]
        if not isinstance(operation, str) or operation not in OPERATIONS or type(args) is not dict:
            return invalid_request()
        required, allowed = OPERATIONS[operation]
        if not required <= set(args) <= allowed:
            return invalid_request()
        if any(type(value) not in (str, int) for value in args.values()):
            return invalid_request()
        try:
            async with self.lock:
                result = await asyncio.to_thread(getattr(self.manager, operation), **args)
            return {"result": result}
        except ManagerError as error:
            return {"error": {"code": error.code, "message": str(error)}}
        except Exception:
            LOG.error("Manager operation failed (%s); details suppressed", operation)
            return {
                "error": {
                    "code": "internal_error",
                    "message": "Ошибка менеджера; изменение могло сохраниться. Проверьте статус.",
                }
            }

    async def parse(self, raw):
        if len(raw) > LIMIT or not raw.endswith(b"\n"):
            return invalid_request()
        try:
            payload = json.loads(raw)
        except (ValueError, UnicodeError):
            return invalid_request()
        return await self.dispatch(payload)

    async def handle(self, reader, writer):
        try:
            try:
                raw = await asyncio.wait_for(reader.readline(), timeout=5)
                response = await self.parse(raw)
            except (ValueError, asyncio.TimeoutError):
                response = invalid_request()
            writer.write(json.dumps(response, ensure_ascii=False).encode() + b"\n")
            await writer.drain()
        except (ConnectionError, OSError):
            pass
        finally:
            writer.close()
            await writer.wait_closed()


class ManagerClient:
    def __init__(self, socket_path):
        self.socket_path = str(socket_path)

    async def call(self, operation, **args):
        writer = None
        try:
            async with asyncio.timeout(180):
                reader, writer = await asyncio.open_unix_connection(self.socket_path, limit=LIMIT)
                writer.write(json.dumps({"op": operation, "args": args}).encode() + b"\n")
                await writer.drain()
                response = json.loads(await reader.readline())
                if "error" in response:
                    error = response["error"]
                    raise ManagerError(error["code"], error["message"])
                return response["result"]
        except (OSError, TimeoutError, ValueError, KeyError):
            raise ManagerError(
                "manager_unavailable",
                "Менеджер недоступен. Повторите запрос; изменение могло сохраниться.",
            ) from None
        finally:
            if writer:
                writer.close()
                await writer.wait_closed()


async def repair_loop(manager):
    while True:
        try:
            await asyncio.to_thread(manager.reconcile)
        except Exception:
            LOG.warning("VPN reconciliation pending; retry in 10 seconds (details suppressed)")
        await asyncio.sleep(10)


async def serve():
    os.umask(0o077)
    manager = Manager(
        Path(os.environ.get("DATA_DIR", "/data")),
        DockerBackend(
            image=os.environ.get("VPN_IMAGE", "amnezia-tg-awg:3.1"),
            volume=os.environ.get("VPN_DATA_VOLUME", "amnezia_tg_data"),
        ),
    )
    socket_path = Path(os.environ.get("MANAGER_SOCKET", "/run/manager/manager.sock"))
    socket_path.parent.mkdir(parents=True, exist_ok=True)
    os.chown(socket_path.parent, 0, 10001)
    os.chmod(socket_path.parent, 0o750)
    socket_path.unlink(missing_ok=True)
    server = await asyncio.start_unix_server(
        RpcServer(manager).handle, str(socket_path), limit=LIMIT
    )
    os.chown(socket_path, 0, 10001)
    os.chmod(socket_path, 0o660)
    repair = asyncio.create_task(repair_loop(manager))
    try:
        async with server:
            await server.serve_forever()
    finally:
        repair.cancel()
        socket_path.unlink(missing_ok=True)


def main():
    logging.basicConfig(level=logging.WARNING)
    asyncio.run(serve())
