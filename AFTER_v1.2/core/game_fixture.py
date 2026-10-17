"""Game-only ECU fixture container.

VAGGAME2 format (writer default):
    fixed header  simulator-only magic/version/state/integrity fields
    JSON metadata
    zlib-compressed ECU model payload

The payload is compressed and wrapped, so a .vagfixture is not a raw ECU image.
The original model bytes are recovered only by read_fixture() for emulator use.

Legacy VAGGAME1 fixtures remain readable for migration, but new files are always
written as VAGGAME2.
"""
from __future__ import annotations

import hashlib
import json
import os
import struct
import tempfile
import time
import zlib
from pathlib import Path
from typing import Optional, Tuple

from core import immo
from core.simulator import DEFAULT_STATE_PATH, SimulatorState, load_state, save_state

MAGIC_V1 = b"VAGGAME1"
HEADER_V1 = struct.Struct("<8sI")

MAGIC = b"VAGGAME2"
FORMAT_VERSION = 2
# magic, version, header_size, flags, meta_len, packed_len, raw_len,
# raw_sha256, packed_crc32
HEADER = struct.Struct("<8sHHIIII32sI")
MAX_META = 1024 * 1024
MAX_PAYLOAD = 128 * 1024 * 1024

FLAG_IMMO_ENABLED = 0x00000001
FLAG_CREDENTIAL_OK = 0x00000002
FLAG_AUTHORIZED = 0x00000004
FLAG_ZLIB_PAYLOAD = 0x00000100


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def inspect_raw(data: bytes, filename: str = "") -> dict:
    found = immo.detect(data, filename)
    if found is None:
        return {"family": "unknown", "display_name": "Unknown ECU", "confidence": "none", "detection": None}
    d = found.to_dict()
    return {"family": d["family"], "display_name": d["display_name"],
            "confidence": d["confidence"], "detection": d}


def _atomic_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(payload)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp_name, path)
    finally:
        try:
            if os.path.exists(tmp_name):
                os.unlink(tmp_name)
        except OSError:
            pass


def _flags_for(state: SimulatorState) -> int:
    flags = FLAG_ZLIB_PAYLOAD
    if state.immo_enabled:
        flags |= FLAG_IMMO_ENABLED
    if state.credential_ok:
        flags |= FLAG_CREDENTIAL_OK
    if state.authorized:
        flags |= FLAG_AUTHORIZED
    return flags


def _state_from_flags(flags: int) -> dict:
    return {
        "immo_enabled": bool(flags & FLAG_IMMO_ENABLED),
        "credential_ok": bool(flags & FLAG_CREDENTIAL_OK),
        "authorized": bool(flags & FLAG_AUTHORIZED),
    }


def build_fixture(raw: bytes, filename: str, state: SimulatorState,
                  family_override: Optional[str] = None) -> Tuple[bytes, dict]:
    if len(raw) > MAX_PAYLOAD:
        raise ValueError("fixture payload is too large")

    ident = inspect_raw(raw, filename)
    if family_override:
        handler = immo.handler_for(family_override)
        if handler is None:
            raise ValueError("unknown family override %r" % family_override)
        ident["family"] = handler.family
        ident["display_name"] = handler.display_name
        ident["confidence"] = "override"

    digest = hashlib.sha256(raw).digest()
    packed = zlib.compress(raw, level=9)
    flags = _flags_for(state)
    packed_crc32 = zlib.crc32(packed) & 0xFFFFFFFF

    meta = {
        "format": "vag-immo-game-fixture",
        "format_version": FORMAT_VERSION,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "source_name": filename,
        "source_size": len(raw),
        "source_sha256": digest.hex(),
        "family": ident["family"],
        "display_name": ident["display_name"],
        "detection_confidence": ident["confidence"],
        "immo_enabled": state.immo_enabled,
        "credential_ok": state.credential_ok,
        "authorized": state.authorized,
        "state_revision": state.revision,
        "payload_encoding": "zlib",
        "payload_policy": "simulator container; raw ECU model bytes are compressed and are not stored as a flashable image",
    }
    meta_raw = json.dumps(meta, separators=(",", ":"), sort_keys=True).encode("utf-8")
    if len(meta_raw) > MAX_META:
        raise ValueError("metadata too large")

    header = HEADER.pack(
        MAGIC,
        FORMAT_VERSION,
        HEADER.size,
        flags,
        len(meta_raw),
        len(packed),
        len(raw),
        digest,
        packed_crc32,
    )
    return header + meta_raw + packed, meta


def write_fixture(source, output=None, *, state_path=None,
                  family_override: Optional[str] = None) -> dict:
    src = Path(source)
    raw = src.read_bytes()
    state = load_state(state_path or DEFAULT_STATE_PATH)
    container, meta = build_fixture(raw, src.name, state, family_override)
    out = Path(output) if output else src.with_name(src.stem + ".vagfixture")
    if out.resolve() == src.resolve():
        raise ValueError("fixture output cannot overwrite source")
    _atomic_bytes(out, container)

    state.fixture_name = src.name
    state.fixture_family = meta["family"]
    state.fixture_sha256 = meta["source_sha256"]
    state.fixture_size = len(raw)
    state.revision += 1
    save_state(state, state_path or DEFAULT_STATE_PATH)

    return {"output": str(out), "container_size": len(container), **meta}


def _read_v1(blob: bytes) -> Tuple[dict, bytes]:
    if len(blob) < HEADER_V1.size:
        raise ValueError("file is too small to be a VAGGAME1 fixture")
    magic, meta_len = HEADER_V1.unpack_from(blob, 0)
    if magic != MAGIC_V1:
        raise ValueError("not a VAGGAME1 fixture")
    if meta_len <= 0 or meta_len > MAX_META:
        raise ValueError("invalid VAGGAME1 metadata length")
    start = HEADER_V1.size
    end = start + meta_len
    if end > len(blob):
        raise ValueError("truncated VAGGAME1 metadata")
    try:
        meta = json.loads(blob[start:end].decode("utf-8"))
    except Exception as exc:
        raise ValueError("invalid VAGGAME1 metadata: %s" % exc) from exc
    payload = blob[end:]
    if len(payload) != int(meta.get("source_size", -1)):
        raise ValueError("VAGGAME1 payload size mismatch")
    if sha256(payload) != meta.get("source_sha256"):
        raise ValueError("VAGGAME1 payload hash mismatch")
    meta = dict(meta)
    meta["legacy_container"] = True
    return meta, payload


def _read_v2(blob: bytes) -> Tuple[dict, bytes]:
    if len(blob) < HEADER.size:
        raise ValueError("file is too small to be a VAGGAME2 fixture")
    (magic, version, header_size, flags, meta_len, packed_len, raw_len,
     raw_digest, packed_crc32) = HEADER.unpack_from(blob, 0)
    if magic != MAGIC:
        raise ValueError("not a VAGGAME2 fixture")
    if version != FORMAT_VERSION:
        raise ValueError("unsupported VAGGAME2 format version %d" % version)
    if header_size != HEADER.size:
        raise ValueError("invalid VAGGAME2 header size")
    if not (flags & FLAG_ZLIB_PAYLOAD):
        raise ValueError("unsupported VAGGAME2 payload encoding")
    if meta_len <= 0 or meta_len > MAX_META:
        raise ValueError("invalid VAGGAME2 metadata length")
    if raw_len < 0 or raw_len > MAX_PAYLOAD or packed_len < 0 or packed_len > MAX_PAYLOAD:
        raise ValueError("invalid VAGGAME2 payload length")

    meta_start = header_size
    meta_end = meta_start + meta_len
    packed_end = meta_end + packed_len
    if packed_end != len(blob):
        raise ValueError("VAGGAME2 container length mismatch")
    try:
        meta = json.loads(blob[meta_start:meta_end].decode("utf-8"))
    except Exception as exc:
        raise ValueError("invalid VAGGAME2 metadata: %s" % exc) from exc

    packed = blob[meta_end:packed_end]
    if (zlib.crc32(packed) & 0xFFFFFFFF) != packed_crc32:
        raise ValueError("VAGGAME2 packed payload CRC mismatch")
    try:
        payload = zlib.decompress(packed)
    except zlib.error as exc:
        raise ValueError("VAGGAME2 payload decompression failed: %s" % exc) from exc
    if len(payload) != raw_len:
        raise ValueError("VAGGAME2 raw payload size mismatch")
    if hashlib.sha256(payload).digest() != raw_digest:
        raise ValueError("VAGGAME2 raw payload hash mismatch")

    header_state = _state_from_flags(flags)
    for key, value in header_state.items():
        if bool(meta.get(key)) != value:
            raise ValueError("VAGGAME2 state mismatch between fixed header and metadata: %s" % key)
    if int(meta.get("source_size", -1)) != raw_len:
        raise ValueError("VAGGAME2 metadata source size mismatch")
    if meta.get("source_sha256") != raw_digest.hex():
        raise ValueError("VAGGAME2 metadata source hash mismatch")

    return meta, payload


def read_fixture(path) -> Tuple[dict, bytes]:
    p = Path(path)
    blob = p.read_bytes()
    if blob.startswith(MAGIC):
        return _read_v2(blob)
    if blob.startswith(MAGIC_V1):
        return _read_v1(blob)
    raise ValueError("not a VAG game fixture (expected VAGGAME2 or legacy VAGGAME1)")


def rewrite_fixture_state(path, *, immo_enabled: Optional[bool] = None,
                          credential_ok: Optional[bool] = None,
                          output=None) -> dict:
    """Change only simulator state in a .vagfixture and emit VAGGAME2.

    The recovered model payload is not modified; it is re-wrapped with a new
    simulator-only header and metadata state.
    """
    src = Path(path)
    meta, payload = read_fixture(src)
    state = SimulatorState(
        immo_enabled=bool(meta.get("immo_enabled", True)),
        credential_ok=bool(meta.get("credential_ok", False)),
        revision=max(0, int(meta.get("state_revision", 0) or 0)) + 1,
    )
    if immo_enabled is not None:
        state.immo_enabled = bool(immo_enabled)
    if credential_ok is not None:
        state.credential_ok = bool(credential_ok)

    container, new_meta = build_fixture(
        payload,
        str(meta.get("source_name", src.stem)),
        state,
        family_override=(str(meta.get("family")) if meta.get("family") not in (None, "", "unknown") else None),
    )
    out = Path(output) if output else src
    _atomic_bytes(out, container)
    return {"output": str(out), "container_size": len(container), **new_meta}
