# VAG IMMO STUDIO GAME v1.2.0

## Simulator container changes
- New `VAGGAME2` fixed header (`VAGGAME1` remains readable for migration).
- New fixtures store the ECU model payload as zlib-compressed simulator data instead of appending raw ECU bytes.
- Fixed header now carries simulator state flags (`IMMO enabled`, `credential valid`, `authorized`).
- Header contains raw payload SHA-256, packed-payload CRC32, packed length, and raw length.
- Reader cross-checks fixed-header state against JSON metadata and rejects disagreement.
- Added strict length, CRC, decompression, and SHA-256 verification.
- Added `rewrite_fixture_state()` to change only game/emulator state and re-wrap the unchanged model payload.
- Added CLI `fixture-immo-on` and `fixture-immo-off` commands.
- New writer always emits v2; old v1 fixtures can still be opened.

## Safety / format intent
`.vagfixture` is a simulator container, not a raw ECU image. The source model can be recovered by the emulator, but is never stored at the flash-image boundary in new v2 fixtures.
