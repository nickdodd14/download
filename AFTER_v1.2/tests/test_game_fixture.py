import tempfile
import unittest
import zlib
from pathlib import Path

from core.game_fixture import (
    HEADER, MAGIC, MAGIC_V1, build_fixture, read_fixture, rewrite_fixture_state, write_fixture,
)
from core.simulator import SimulatorState, set_credential, set_immo


class FixtureTests(unittest.TestCase):
    def test_v2_round_trip_recovers_original_model_bytes(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            state = root / "state.json"
            raw = bytes((i * 7) & 0xFF for i in range(4096))
            source = root / "ecu.bin"
            source.write_bytes(raw)
            out = root / "ecu.vagfixture"
            set_credential(False, state)
            set_immo(False, state)
            result = write_fixture(source, out, state_path=state)
            blob = out.read_bytes()
            self.assertTrue(blob.startswith(MAGIC))
            self.assertNotEqual(blob[-len(raw):], raw)
            meta, payload = read_fixture(out)
            self.assertEqual(payload, raw)
            self.assertEqual(meta["format_version"], 2)
            self.assertEqual(meta["payload_encoding"], "zlib")
            self.assertFalse(meta["immo_enabled"])
            self.assertTrue(meta["authorized"])
            self.assertEqual(result["source_size"], len(raw))

    def test_v2_tamper_detected(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "ecu.bin"
            source.write_bytes(b"A" * 4096)
            out = root / "ecu.vagfixture"
            write_fixture(source, out, state_path=root / "state.json")
            blob = bytearray(out.read_bytes())
            blob[-1] ^= 0x01
            out.write_bytes(blob)
            with self.assertRaises(ValueError):
                read_fixture(out)

    def test_header_state_and_metadata_must_match(self):
        raw = b"B" * 4096
        container, _ = build_fixture(raw, "x.bin", SimulatorState(immo_enabled=False, credential_ok=False))
        blob = bytearray(container)
        fields = list(HEADER.unpack_from(blob, 0))
        fields[3] |= 0x1  # lie in fixed header: IMMO enabled
        blob[:HEADER.size] = HEADER.pack(*fields)
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "bad.vagfixture"
            p.write_bytes(blob)
            with self.assertRaises(ValueError):
                read_fixture(p)

    def test_fixture_state_rewrite_does_not_change_model_payload(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            raw = bytes(range(256)) * 16
            source = root / "ecu.bin"
            source.write_bytes(raw)
            out = root / "ecu.vagfixture"
            write_fixture(source, out, state_path=root / "state.json")
            _, before_payload = read_fixture(out)
            result = rewrite_fixture_state(out, immo_enabled=False)
            after_meta, after_payload = read_fixture(out)
            self.assertEqual(before_payload, after_payload)
            self.assertFalse(after_meta["immo_enabled"])
            self.assertTrue(after_meta["authorized"])
            self.assertEqual(result["source_size"], len(raw))

    def test_legacy_v1_fixture_is_readable(self):
        import hashlib, json, struct
        raw = b"legacy" * 100
        meta = {
            "format": "vag-immo-game-fixture",
            "format_version": 1,
            "source_size": len(raw),
            "source_sha256": hashlib.sha256(raw).hexdigest(),
            "immo_enabled": True,
            "credential_ok": False,
            "authorized": False,
        }
        meta_raw = json.dumps(meta).encode("utf-8")
        blob = struct.pack("<8sI", MAGIC_V1, len(meta_raw)) + meta_raw + raw
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "legacy.vagfixture"
            p.write_bytes(blob)
            got_meta, got_payload = read_fixture(p)
            self.assertTrue(got_meta["legacy_container"])
            self.assertEqual(got_payload, raw)


if __name__ == "__main__":
    unittest.main()
