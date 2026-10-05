#!/usr/bin/env python3
"""Read what nodo wrote into ``/__config__``.

The file is a ``celaut.ConfigurationFile`` protobuf. We do not take a protobuf
library into the image: the only fields this service needs are a handful of
strings and integers, and the wire format for those is short enough to decode
here. If nodo ever reorders the message this will fail closed rather than talk
to the wrong place.

    ConfigurationFile
      1  Instance gateway
           2  repeated Uri_Slot uri_slot
                2  repeated Uri uri
                     1  string ip
                     2  int32  port
      2  Configuration config
           1  repeated BytesKeyValue environment_variables
                (each entry: 1 key string, 2 optional bytes value)
"""
from __future__ import annotations

import os
from typing import Dict, Iterable, Iterator, List, Optional, Tuple

DEFAULT_CONFIG_PATH = "/__config__"

_VARINT = 0
_LEN = 2


class ConfigError(Exception):
    """The file was there and could not be read as a gateway address."""


def _read_varint(buf: bytes, i: int) -> Tuple[int, int]:
    shift = 0
    n = 0
    while True:
        if i >= len(buf):
            raise ConfigError("truncated varint")
        b = buf[i]
        i += 1
        n |= (b & 0x7F) << shift
        if b < 0x80:
            return n, i
        shift += 7
        if shift > 70:
            raise ConfigError("varint too long")


def _fields(buf: bytes) -> Iterator[Tuple[int, int, object, int]]:
    """Yield ``(field_number, wire_type, payload, next_index)`` over ``buf``."""
    i = 0
    n = len(buf)
    while i < n:
        tag, i = _read_varint(buf, i)
        field, wire = tag >> 3, tag & 7
        if wire == _VARINT:
            value, i = _read_varint(buf, i)
            yield field, wire, value, i
        elif wire == _LEN:
            length, i = _read_varint(buf, i)
            end = i + length
            if end > n:
                raise ConfigError("truncated length-delimited field")
            yield field, wire, buf[i:end], end
            i = end
        else:
            raise ConfigError(f"unsupported wire type {wire} on field {field}")


def _subfields(buf: bytes) -> Iterable[Tuple[int, int, object]]:
    for field, wire, payload, _ in _fields(buf):
        yield field, wire, payload


def gateway_uris(buf: bytes) -> List[Tuple[str, int]]:
    """``(ip, port)`` for every URI on the gateway instance, in file order."""
    uris: List[Tuple[str, int]] = []
    for field, wire, payload in _subfields(buf):
        if field != 1 or wire != _LEN:
            continue
        for ifield, iwire, ipayload in _subfields(payload):
            if ifield != 2 or iwire != _LEN:
                continue
            for ufield, uwire, upayload in _subfields(ipayload):
                if ufield != 2 or uwire != _LEN:
                    continue
                ip: Optional[str] = None
                port: Optional[int] = None
                for f, w, v in _subfields(upayload):
                    if f == 1 and w == _LEN:
                        ip = v.decode("utf-8")
                    elif f == 2 and w == _VARINT:
                        port = int(v)
                if ip and port:
                    uris.append((ip, port))
    return uris


def environment_variables(buf: bytes) -> Dict[str, str]:
    """``Configuration.environment_variables``, decoded as UTF-8 text."""
    env: Dict[str, str] = {}
    for field, wire, payload in _subfields(buf):
        if field != 2 or wire != _LEN:
            continue
        for f, w, v in _subfields(payload):
            if f != 1 or w != _LEN:
                continue
            key = value = None
            for ef, ew, ev in _subfields(v):
                if ef == 1 and ew == _LEN:
                    key = ev.decode("utf-8")
                elif ef == 2 and ew == _LEN:
                    value = ev.decode("utf-8", errors="replace")
            if key is not None and value is not None:
                env[key] = value
    return env


def load(path: str = DEFAULT_CONFIG_PATH) -> Tuple[List[Tuple[str, int]], Dict[str, str]]:
    if not os.path.isfile(path):
        return [], {}
    with open(path, "rb") as handle:
        buf = handle.read()
    if not buf:
        return [], {}
    return gateway_uris(buf), environment_variables(buf)


def merged_env(config_env: Dict[str, str]) -> Dict[str, str]:
    """Process env wins over ``__config__``, so a shell test can override."""
    merged = dict(config_env)
    merged.update({k: v for k, v in os.environ.items() if v is not None})
    return merged


def resolve_target(
    env: Dict[str, str],
    uris: List[Tuple[str, int]],
) -> Tuple[str, int]:
    """Where this process forwards to.

    Order, each one winning outright if it is set:

    1. ``TARGET=host:port`` -- a complete override, for pointing at a different
       node (typically *our* gateway, when this instance is running on a peer).
    2. ``TARGET_HOST`` / ``TARGET_PORT`` -- either piece, the other falling back
       to the first URI in ``__config__.gateway``.
    3. That URI itself -- the host node's plaintext gateway, which is what a
       service is always allowed to reach.
    """
    target = (env.get("TARGET") or "").strip()
    if target:
        host, sep, port_s = target.rpartition(":")
        if not sep or not host or not port_s:
            raise ConfigError("TARGET must be host:port, got %r" % (target,))
        return host.strip("[]"), int(port_s)

    if not uris:
        raise ConfigError(
            "no TARGET and no gateway URI in __config__: nothing to forward to"
        )
    default_host, default_port = uris[0]
    host = (env.get("TARGET_HOST") or "").strip() or default_host
    port_s = (env.get("TARGET_PORT") or "").strip()
    port = int(port_s) if port_s else default_port
    return host, port


def resolve_listen_port(env: Dict[str, str]) -> int:
    raw = (env.get("LISTEN_PORT") or "").strip()
    return int(raw) if raw else 4040
