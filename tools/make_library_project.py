"""Copy the pick-and-place TwinCAT project and strip it down to a library project:
only Framework/ and Devices/, no task, no TcUnit, with library metadata."""
import os
import pathlib
import re
import shutil
import sys

src = pathlib.Path(sys.argv[1])          # repo/TcProject
version = sys.argv[2]                    # e.g. 1.0.0.0
dst = pathlib.Path(os.environ["TEMP"]) / "nodetree_lib" / "TcProject"
if dst.parent.exists():
    shutil.rmtree(dst.parent)
shutil.copytree(src, dst, ignore=shutil.ignore_patterns("_CompileInfo", "_Boot", "*.tmc", "*.~u", "*.compiled-library*"))
plc = dst / "PickPlace" / "PickPlacePlc"
for d in ["Machine", "Test"]:
    shutil.rmtree(plc / d)
(plc / "PlcTask.TcTTO").unlink()

p = plc / "PickPlacePlc.plcproj"
s = p.read_text(encoding="utf-8-sig")
s = re.sub(r'\s*<Compile Include="(?:Machine|Test)\\[^"]+">\s*<SubType>Code</SubType>\s*</Compile>', "", s)
s = re.sub(r'\s*<Compile Include="PlcTask.TcTTO">\s*<SubType>Code</SubType>\s*</Compile>', "", s)
s = re.sub(r'\s*<Folder Include="(?:Machine|Test)" />', "", s)
s = re.sub(r'\s*<PlaceholderReference Include="TcUnit">.*?</PlaceholderReference>', "", s, flags=re.S)
meta = f"""
    <Company>sulemanali5760</Company>
    <Title>NodeTree</Title>
    <ProjectVersion>{version}</ProjectVersion>
    <DefaultNamespace>NodeTree</DefaultNamespace>
    <Author>Suleman Ali</Author>
    <Description>Node-tree machine framework: one Cyclic() on the root runs the plant; commands return eBusy/eDone/eError; mode handling and step manager. Plus FB_PneumaticCylinder.</Description>
"""
s = s.replace("<Name>PickPlacePlc</Name>", "<Name>PickPlacePlc</Name>" + meta.rstrip("\n"), 1)
assert "Machine\\" not in s and "Test\\" not in s and "TcUnit" not in s and "PlcTask" not in s
p.write_text(s, encoding="utf-8")
print(dst / "PickPlace.sln")
