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
            writer.write_eof()
            writer.close()
            await writer.wait_closed()

        self.backend = await asyncio.start_server(echo, "127.0.0.1", 0)
        self.backend_port = self.backend.sockets[0].getsockname()[1]
        bound = asyncio.get_running_loop().create_future()
        self.proxy_task = asyncio.create_task(
            serve(0, ("127.0.0.1", self.backend_port), bound=bound)
        )
        self.listen_port = await asyncio.wait_for(bound, timeout=2)

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
        writer.write_eof()
        reply = await asyncio.wait_for(reader.read(65536), timeout=2)
        writer.close()
        await writer.wait_closed()
        self.assertEqual(await self.received.get(), b"ping")
        self.assertEqual(reply, b"pong:ping")

    async def test_a_closed_target_does_not_hang_the_client(self):
        bound = asyncio.get_running_loop().create_future()
        task = asyncio.create_task(serve(0, ("127.0.0.1", 1), bound=bound))
        port = await asyncio.wait_for(bound, timeout=2)
        try:
            reader, writer = await asyncio.open_connection("127.0.0.1", port)
            data = await asyncio.wait_for(reader.read(16), timeout=2)
            self.assertEqual(data, b"")
            writer.close()
            await writer.wait_closed()
        finally:
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass


if __name__ == "__main__":
    unittest.main()
