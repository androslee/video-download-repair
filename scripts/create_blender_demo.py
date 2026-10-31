"""Import an existing engine report and save a reviewable .blend (requires bpy)."""
import argparse
import importlib.util
import json
from pathlib import Path

import bpy

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("timeline", type=Path)
parser.add_argument("output", type=Path)
args = parser.parse_args()
if args.output.exists():
    raise SystemExit("Output exists; choose a new .blend path")
adapter = Path(__file__).resolve().parents[1] / "blender_addon" / "video_repair_lab" / "timeline_import.py"
spec = importlib.util.spec_from_file_location("vrl_demo_adapter", adapter)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
scene = module.import_component(json.loads(args.timeline.read_text()))
bpy.context.window.scene = scene
for area in bpy.context.screen.areas:
    if area.type == "VIEW_3D":
        area.type = "SEQUENCE_EDITOR"
        area.spaces.active.view_type = "SEQUENCER_PREVIEW"
args.output.parent.mkdir(parents=True, exist_ok=True)
bpy.ops.wm.save_as_mainfile(filepath=str(args.output.resolve()))
print(args.output.resolve())
bpy.ops.wm.quit_blender()
