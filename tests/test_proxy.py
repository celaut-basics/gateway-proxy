import asyncio
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "service"))

from proxy import serve  # noqa: E402


class SpliceTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.received = asyncio.Queue()

        async def echo(reader, writer):
            data = await reader.read(65536)
            await self.received.put(data)
            writer.write(b"pong:" + data)
            await writer.drain()
            writer.close()
            await writer.wait_closed()

        self.backend = await asyncio.start_server(echo, "127.0.0.1", 0)
        self.backend_port = self.backend.sockets[0].getsockname()[1]
        self.proxy_task = asyncio.create_task(
            serve(0, ("127.0.0.1", self.backend_port))
        )
        # serve() binds 0.0.0.0:listen; we passed 0 so the OS picks. Grab it.
        await asyncio.sleep(0.05)
        # start_server inside serve uses listen_port=0; recover via the task's
        # server. Easier: bind a known port.
        self.proxy_task.cancel()
        try:
            await self.proxy_task
        except (asyncio.CancelledError, Exception):
            pass
        self.listen_port = 18765
        self.proxy_task = asyncio.create_task(
            serve(self.listen_port, ("127.0.0.1", self.backend_port))
        )
        await asyncio.sleep(0.05)

    async def asyncTearDown(self):
        self.proxy_task.cancel()
        try:
            await self.proxy_task
        except (asyncio.CancelledError, Exception):
            pass
        self.backend.close()
        await self.backend.wait_closed()

    async def test_bytes_arrive_at_the_target_and_come_back(self):
        reader, writer = await asyncio.open_connection("127.0.0.1", self.listen_port)
        writer.write(b"ping")
        await writer.drain()
        reply = await asyncio.wait_for(reader.read(65536), timeout=2)
        writer.close()
        await writer.wait_closed()
        self.assertEqual(await self.received.get(), b"ping")
        self.assertEqual(reply, b"pong:ping")


if __name__ == "__main__":
    unittest.main()
