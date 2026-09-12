"""Minimal protobuf encoder for the fields gateway-proxy reads.

Mirrors service/config.py: if a fixture encoded here cannot be decoded there,
the decoder is wrong. No library on either side.
"""
from __future__ import annotations


def _varint(n: int) -> bytes:
    out = bytearray()
    while n > 0x7F:
        out.append((n & 0x7F) | 0x80)
        n >>= 7
    out.append(n)
    return bytes(out)


def _tag(field: int, wire: int) -> bytes:
    return _varint((field << 3) | wire)


def _ld(field: int, payload: bytes) -> bytes:
    return _tag(field, 2) + _varint(len(payload)) + payload


def _var(field: int, n: int) -> bytes:
    return _tag(field, 0) + _varint(n)


def uri(ip: str, port: int) -> bytes:
    return _ld(1, ip.encode("utf-8")) + _var(2, port)


def uri_slot(*uris: bytes) -> bytes:
    return b"".join(_ld(2, u) for u in uris)


def instance(*slots: bytes) -> bytes:
    return b"".join(_ld(2, s) for s in slots)


def env_entry(key: str, value: str) -> bytes:
    return _ld(1, key.encode("utf-8")) + _ld(2, value.encode("utf-8"))


def configuration(**env: str) -> bytes:
    return b"".join(_ld(1, env_entry(k, v)) for k, v in env.items())


def configuration_file(gateway: bytes = b"", config: bytes = b"") -> bytes:
    out = b""
    if gateway:
        out += _ld(1, gateway)
    if config:
        out += _ld(2, config)
    return out
