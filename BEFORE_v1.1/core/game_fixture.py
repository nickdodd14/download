"""Game-only ECU fixture container.

Format:
    8 bytes   magic b'VAGGAME1'
    4 bytes   little-endian JSON metadata length
    N bytes   UTF-8 JSON metadata
    remainder original ECU payload, byte-for-byte unchanged

The custom header/extension intentionally makes this a simulator fixture rather
than a raw ECU image.
"""
from __future__ import annotations

import hashlib
import json
import os
import struct
import tempfile
import time
from pathlib import Path
from typing import Optional, Tuple

from core import immo
from core.simulator import DEFAULT_STATE_PATH, SimulatorState, load_state, save_state

MAGIC = b"VAGGAME1"
HEADER = struct.Struct("<8sI")
FORMAT_VERSION = 1
MAX_META = 1024 * 1024


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


def build_fixture(raw: bytes, filename: str, state: SimulatorState,
                  family_override: Optional[str] = None) -> Tuple[bytes, dict]:
    ident = inspect_raw(raw, filename)
    if family_override:
        handler = immo.handler_for(family_override)
        if handler is None:
            raise ValueError("unknown family override %r" % family_override)
        ident["family"] = handler.family
        ident["display_name"] = handler.display_name
        ident["confidence"] = "override"

    digest = sha256(raw)
    meta = {
        "format": "vag-immo-game-fixture",
        "format_version": FORMAT_VERSION,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "source_name": filename,
        "source_size": len(raw),
        "source_sha256": digest,
        "family": ident["family"],
        "display_name": ident["display_name"],
        "detection_confidence": ident["confidence"],
        "immo_enabled": state.immo_enabled,
        "credential_ok": state.credential_ok,
        "authorized": state.authorized,
        "state_revision": state.revision,
        "payload_policy": "original ECU bytes are embedded unchanged; state lives in metadata",
    }
    meta_raw = json.dumps(meta, separators=(",", ":"), sort_keys=True).encode("utf-8")
    if len(meta_raw) > MAX_META:
        raise ValueError("metadata too large")
    container = HEADER.pack(MAGIC, len(meta_raw)) + meta_raw + raw
    return container, meta


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

    # Attach the selected raw fixture to the persistent game state.
    state.fixture_name = src.name
    state.fixture_family = meta["family"]
    state.fixture_sha256 = meta["source_sha256"]
    state.fixture_size = len(raw)
    state.revision += 1
    save_state(state, state_path or DEFAULT_STATE_PATH)

    return {"output": str(out), "container_size": len(container), **meta}


def read_fixture(path) -> Tuple[dict, bytes]:
    p = Path(path)
    blob = p.read_bytes()
    if len(blob) < HEADER.size:
        raise ValueError("file is too small to be a VAG game fixture")
    magic, meta_len = HEADER.unpack_from(blob, 0)
    if magic != MAGIC:
        raise ValueError("not a VAG game fixture")
    if meta_len <= 0 or meta_len > MAX_META:
        raise ValueError("invalid fixture metadata length")
    start = HEADER.size
    end = start + meta_len
    if end > len(blob):
        raise ValueError("truncated fixture metadata")
    try:
        meta = json.loads(blob[start:end].decode("utf-8"))
    except Exception as exc:
        raise ValueError("invalid fixture metadata: %s" % exc) from exc
    payload = blob[end:]
    if len(payload) != int(meta.get("source_size", -1)):
        raise ValueError("fixture payload size mismatch")
    if sha256(payload) != meta.get("source_sha256"):
        raise ValueError("fixture payload hash mismatch")
    return meta, payload
