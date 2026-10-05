#!/usr/bin/env python3
"""TCP splice: each accepted connection is a byte pipe to the target.

No protocol awareness. The gateway speaks gRPC (TLS or plaintext) and this
process must not interpret it -- that is what lets the same binary front either
port. One task per direction; either side closing half-closes the other, so a
request/response RPC can still answer after the caller is done sending.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Optional, Tuple

log = logging.getLogger("gateway-proxy")


async def _pump(src: asyncio.StreamReader, dst: asyncio.StreamWriter, label: str) -> None:
    try:
        while True:
            data = await src.read(65536)
            if not data:
                break
            dst.write(data)
            await dst.drain()
    except (ConnectionResetError, BrokenPipeError, asyncio.IncompleteReadError) as e:
        log.debug("%s: %s", label, e)
    finally:
        try:
            dst.write_eof()
        except (NotImplementedError, OSError):
            try:
                dst.close()
            except OSError:
                pass


async def handle(
    client_r: asyncio.StreamReader,
    client_w: asyncio.StreamWriter,
    target: Tuple[str, int],
) -> None:
    peer = client_w.get_extra_info("peername")
    try:
        remote_r, remote_w = await asyncio.open_connection(target[0], target[1])
    except OSError as e:
        log.warning("connect %s:%s failed for %s: %s", target[0], target[1], peer, e)
        client_w.close()
        await client_w.wait_closed()
        return
    log.info("splice %s -> %s:%s", peer, target[0], target[1])
    try:
        await asyncio.gather(
            _pump(client_r, remote_w, "c2t"),
            _pump(remote_r, client_w, "t2c"),
        )
    finally:
        for w in (client_w, remote_w):
            try:
                w.close()
                await w.wait_closed()
            except OSError:
                pass


async def serve(
    listen_port: int,
    target: Tuple[str, int],
    bound: Optional[asyncio.Future] = None,
) -> None:
    server = await asyncio.start_server(
        lambda r, w: handle(r, w, target),
        host="0.0.0.0",
        port=listen_port,
        reuse_address=True,
    )
    sockets = server.sockets or []
    bound_s = ", ".join(str(s.getsockname()) for s in sockets) or str(listen_port)
    if bound is not None and not bound.done():
        port = sockets[0].getsockname()[1] if sockets else listen_port
        bound.set_result(port)
    log.info("listening on %s, forwarding to %s:%s", bound_s, target[0], target[1])
    async with server:
        await server.serve_forever()
