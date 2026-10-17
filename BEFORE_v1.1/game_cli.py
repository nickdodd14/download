#!/usr/bin/env python3
"""CLI for the software-only game immobilizer and fixture container."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from core import immo
from core.game_fixture import inspect_raw, read_fixture, write_fixture
from core.simulator import load_state, set_credential, set_immo


def emit(obj) -> int:
    print(json.dumps(obj, indent=2, sort_keys=True))
    return 0


def cmd_status(args):
    return emit(load_state(args.state).to_dict())


def cmd_on(args):
    return emit(set_immo(True, args.state).to_dict())


def cmd_off(args):
    return emit(set_immo(False, args.state).to_dict())


def cmd_cred_ok(args):
    return emit(set_credential(True, args.state).to_dict())


def cmd_cred_bad(args):
    return emit(set_credential(False, args.state).to_dict())


def cmd_detect(args):
    p = Path(args.file)
    data = p.read_bytes()
    return emit({**inspect_raw(data, p.name), "size": len(data)})


def cmd_export(args):
    return emit(write_fixture(args.file, args.output, state_path=args.state,
                              family_override=args.family))


def cmd_info(args):
    meta, payload = read_fixture(args.file)
    return emit({**meta, "verified_payload_bytes": len(payload)})


def cmd_families(args):
    return emit(immo.supported_families())


def build_parser():
    p = argparse.ArgumentParser(
        prog="game_cli",
        description="VAG IMMO STUDIO game/simulator state + fixture tooling")
    p.add_argument("--state", help="alternate simulator_state.json path")
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("status").set_defaults(func=cmd_status)
    sub.add_parser("immo-on").set_defaults(func=cmd_on)
    sub.add_parser("immo-off").set_defaults(func=cmd_off)
    sub.add_parser("credential-ok").set_defaults(func=cmd_cred_ok)
    sub.add_parser("credential-bad").set_defaults(func=cmd_cred_bad)
    sub.add_parser("families").set_defaults(func=cmd_families)

    d = sub.add_parser("detect")
    d.add_argument("file")
    d.set_defaults(func=cmd_detect)

    e = sub.add_parser("export-fixture")
    e.add_argument("file")
    e.add_argument("-o", "--output")
    e.add_argument("-f", "--family")
    e.set_defaults(func=cmd_export)

    i = sub.add_parser("fixture-info")
    i.add_argument("file")
    i.set_defaults(func=cmd_info)
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except Exception as exc:
        raise SystemExit("error: %s" % exc)


if __name__ == "__main__":
    raise SystemExit(main())
