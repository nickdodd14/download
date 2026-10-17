# VAGGAME1 -> VAGGAME2 migration

## What changed

`VAGGAME1` used a small magic + JSON-length header and appended the model bytes directly after JSON metadata.

`VAGGAME2` is explicitly a simulator container:

1. 8-byte `VAGGAME2` magic.
2. Fixed binary header with format version, state flags, metadata length, packed/raw sizes, raw SHA-256 and packed CRC32.
3. JSON metadata.
4. zlib-compressed model payload.

The emulator still reconstructs the exact original model payload with `read_fixture()`, but a new `.vagfixture` is not laid out like a raw model/ECU image.

## State bits

The fixed header contains simulator-only flags:

- bit 0: IMMO enabled
- bit 1: simulated credential valid
- bit 2: simulated authorization result
- bit 8: zlib payload encoding

The reader cross-checks these values against JSON metadata and rejects a fixture if they disagree.

## Compatibility

- Writer: always VAGGAME2.
- Reader: VAGGAME2 + legacy VAGGAME1.
- Rewriting a VAGGAME1 fixture with v1.2 automatically migrates it to VAGGAME2.

## New CLI operations

```text
python game_cli.py fixture-immo-off fixture.vagfixture
python game_cli.py fixture-immo-on fixture.vagfixture
```

These rewrite only the simulator container state. The recovered model payload remains byte-identical.
