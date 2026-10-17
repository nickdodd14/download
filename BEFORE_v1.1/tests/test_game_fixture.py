import tempfile
import unittest
from pathlib import Path

from core.game_fixture import read_fixture, write_fixture
from core.simulator import set_credential, set_immo


class FixtureTests(unittest.TestCase):
    def test_fixture_embeds_original_bytes_unchanged(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            state = root / "state.json"
            raw = bytes((i * 7) & 0xFF for i in range(512))
            source = root / "ecu.bin"
            source.write_bytes(raw)
            out = root / "ecu.vagfixture"
            set_credential(False, state)
            set_immo(False, state)
            result = write_fixture(source, out, state_path=state)
            meta, payload = read_fixture(out)
            self.assertEqual(payload, raw)
            self.assertFalse(meta["immo_enabled"])
            self.assertTrue(meta["authorized"])
            self.assertEqual(result["source_size"], len(raw))

    def test_fixture_tamper_detected(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            state = root / "state.json"
            source = root / "ecu.bin"
            source.write_bytes(b"A" * 512)
            out = root / "ecu.vagfixture"
            write_fixture(source, out, state_path=state)
            blob = bytearray(out.read_bytes())
            blob[-1] ^= 0x01
            out.write_bytes(blob)
            with self.assertRaises(ValueError):
                read_fixture(out)


if __name__ == "__main__":
    unittest.main()
