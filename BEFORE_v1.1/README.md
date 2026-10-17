# VAG IMMO STUDIO v1.0

IMMO OFF / IMMO ON patch engine + GUI + CLI for Bosch VAG ECUs.

Designed to drop into VAG_Bosch_ECU_Offline_Workbench_v0.7 (same core/ package
layout, same stdlib-only style). Also runs standalone.

## Coverage

| Family | Memory | Size | OFF method | Confidence |
|---|---|---|---|---|
| ME7.1 / ME7.5 / ME7.5.10 | 24C04 / 24C08 / 93C86 | 512 / 1024 / 2048 | immo function bytes 0x12 + 0x22 -> 0x02 | VIN-anchored, else low |
| EDC15P / EDC15VM+ | 24C04 | 512 | immo bytes 0x1B0 + 0x1DE -> 0x60 | anchored (VIN @0x140) |
| EDC16 U1/U31/U34/CP34 | 95320 | 4096 | profile offsets, VIN-checked | heuristic + learner |
| MED9.1 / MED9.5.10 | 95020 / 95040 / 95160 | 256 / 512 / 2048 | neutralise IMMO1..IMMO4 blocks | signature-anchored |
| MED17 / MEDC17 | D-Flash | 0x80 blocks | immo byte in block id 0x09 + CS1/CS2 CRC32 | heuristic + learner |
| MED17.1.62 BCM / P1570 | PFLASH | 4 MB | flash patch + PFLASH CRC32 | profile-driven |

Every handler supports OFF, ON and TOGGLE, is dry-run by default and never
overwrites the source file.

## Run

    run_immo_studio.bat          # GUI
    run_immo_cli.bat --help      # CLI
    run_tests.bat                # unit tests (stdlib unittest)

## Safety model

* Source is never written. Default outputs: <name>.immooff.bin, <name>.immoon.bin,
  <name>.immotoggle.bin
* A sidecar journal <output>.immo.json records every original byte so ON
  restores exact pre-patch values even when the original is unknown
* --dry-run prints the plan and writes nothing
* Anything unconfirmed against a real before/after pair is reported as low or
  heuristic, never silently trusted

## Provenance

Geometry reverse-engineered from three shipped tools (string tables + PE layout,
no decompiler):

* Abritus72 Ltd "VAG EDC15 immo bypass" (2005, MFC) - EEPROM 24C04
* Abritus72 Ltd "VAG EDC16 immo bypass" (2005, MFC) - EEPROM 95320
* "E2PA" Build 2.0.0 (C) 2014-2024 Technic - MED9.x, 2k/4k EEPROM + 2048 kB flash

See docs/REVERSE_ENGINEERING_NOTES.md
