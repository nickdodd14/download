# Changelog

## 1.0.0
* core/immo/ package: registry, base types, anchors, checksums, handlers for
  ME7, EDC15, EDC16, MED9, MEDC17, MED17.1.62 BCM
* OFF / ON / TOGGLE with exact reversal via sidecar journal
* immo_studio.py tkinter GUI and immo_cli.py CLI
* Learner that derives offsets from a before/after pair
* Unit tests, docs, reverse-engineering notes

### fixes
* ME7 detection no longer counts empty fields as a valid VIN split, which made it
  win ties against EDC15 on 512-byte dumps
* Handlers self-detect when build_plan is called directly without a Detection
