# VAG IMMO STUDIO GAME v1.2

This branch uses a simulator-only `.vagfixture` container.

## VAGGAME2

New files begin with the 8-byte magic `VAGGAME2`. The fixed header stores:

- format version and header size
- simulator IMMO/credential/authorization state flags
- metadata length
- compressed payload length
- original model length
- SHA-256 of the original model payload
- CRC32 of the compressed payload

JSON metadata follows the fixed header, followed by a zlib-compressed ECU model payload.

The emulator can recover the original model bytes with `read_fixture()`. The container itself is intentionally not laid out as a raw ECU image.

Legacy `VAGGAME1` fixtures are still readable; any fixture re-written by v1.2 is emitted as `VAGGAME2`.

## CLI

```text
python game_cli.py export-fixture model.bin
python game_cli.py fixture-info model.vagfixture
python game_cli.py fixture-immo-off model.vagfixture
python game_cli.py fixture-immo-on model.vagfixture
```

`fixture-immo-on/off` changes only the simulator container state. The recovered ECU model payload remains byte-identical.
