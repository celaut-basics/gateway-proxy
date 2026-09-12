#!/usr/bin/env python3
"""PID 1 of the gateway-proxy service."""
from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

# The image copies this directory to /service; a local test imports from cwd.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import (  # noqa: E402
    ConfigError,
    load,
    merged_env,
    resolve_listen_port,
    resolve_target,
)
from proxy import serve  # noqa: E402


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%H:%M:%S",
    )
    uris, config_env = load()
    env = merged_env(config_env)
    try:
        target = resolve_target(env, uris)
        listen = resolve_listen_port(env)
    except (ConfigError, ValueError) as e:
        logging.error("%s", e)
        return 1
    try:
        asyncio.run(serve(listen, target))
    except KeyboardInterrupt:
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
