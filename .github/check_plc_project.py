#!/usr/bin/env python3
"""Check the TwinCAT project without TwinCAT.

The PLC only compiles on Windows with XAE installed, so CI cannot build it.
What CI can do is catch the two failures that are silent in the IDE:

  1. a .Tc* file that sits on disk but is missing from PickPlacePlc.plcproj
     -- the code is never compiled and never runs;
  2. a Compile entry that points at a file that no longer exists
     -- the build breaks on the reviewer's machine, not here.

On the way it parses every object file as XML and checks that the name inside
matches the file name, which is what TwinCAT assumes when it loads a project.
"""

from __future__ import annotations

import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROJECT_DIR = ROOT / "TcProject" / "PickPlace" / "PickPlacePlc"
PLCPROJ = PROJECT_DIR / "PickPlacePlc.plcproj"
TSPROJ = ROOT / "TcProject" / "PickPlace" / "PickPlace.tsproj"
OBJECT_SUFFIXES = {".TcPOU", ".TcIO", ".TcDUT", ".TcGVL", ".TcTTO"}
MSBUILD = {"msb": "http://schemas.microsoft.com/developer/msbuild/2003"}

errors: list[str] = []


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def compiled_files() -> set[Path]:
    root = ET.parse(PLCPROJ).getroot()
    found: set[Path] = set()
    for item in root.findall(".//msb:Compile", MSBUILD):
        include = item.get("Include", "")
        path = PROJECT_DIR / include.replace("\\", "/")
        found.add(path)
        if not path.is_file():
            errors.append(f"{PLCPROJ.name} compiles {include!r}, which does not exist")
    return found


def check_object(path: Path) -> None:
    try:
        document = ET.parse(path)
    except ET.ParseError as exc:
        errors.append(f"{rel(path)}: not well-formed XML: {exc}")
        return
    named = [node.get("Name", "") for node in document.getroot().findall("*[@Name]")]
    if not named:
        errors.append(f"{rel(path)}: contains no named object")
    elif path.stem not in named:
        errors.append(
            f"{rel(path)}: declares {', '.join(named)} but the file is named {path.stem}"
        )


def main() -> int:
    try:
        compiled = compiled_files()
    except ET.ParseError as exc:
        errors.append(f"{PLCPROJ.name}: not well-formed XML: {exc}")
        compiled = set()

    on_disk = {path for path in PROJECT_DIR.rglob("*.Tc*") if path.suffix in OBJECT_SUFFIXES}
    for path in sorted(on_disk - compiled):
        errors.append(f"{rel(path)} is not listed in {PLCPROJ.name} - TwinCAT will ignore it")
    for path in sorted(on_disk):
        check_object(path)

    try:
        ET.parse(TSPROJ)
    except ET.ParseError as exc:
        errors.append(f"{rel(TSPROJ)}: not well-formed XML: {exc}")

    for message in errors:
        print(f"::error::{message}")
    print(f"{len(on_disk)} object files, {len(compiled)} compile entries, {len(errors)} error(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
