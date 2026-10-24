#!/usr/bin/env python3
"""
Tangerine Linux v1 — entry point.

GUI :  python3 main.py
CLI :  python3 main.py --convert FILE FORMAT   (mis. --convert contoh.pdf JPG)
       python3 main.py --formats FILE           (lihat isi wheel untuk file itu)
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from tangerine.converters import ConversionError, convert_many, formats_for


def cli(argv: list[str]) -> int | None:
    """Return exit code kalau mode CLI, None kalau harus buka GUI."""
    parser = argparse.ArgumentParser(prog="tangerine-linux")
    parser.add_argument("--convert", nargs=2, metavar=("FILE", "FORMAT"))
    parser.add_argument("--formats", metavar="FILE")
    args = parser.parse_args(argv)
    if args.formats:
        f = Path(args.formats)
        print(f"{f.name}: wheel = {formats_for(f)}")
        return 0
    if args.convert:
        src, fmt = Path(args.convert[0]), args.convert[1]
        try:
            for out in convert_many([src], fmt):
                print(f"OK -> {out}")
        except ConversionError as e:
            print(f"GAGAL: {e}", file=sys.stderr)
            return 1
        return 0
    return None


if __name__ == "__main__":
    code = cli(sys.argv[1:])
    if code is not None:
        raise SystemExit(code)
    from tangerine.app import main
    raise SystemExit(main())
