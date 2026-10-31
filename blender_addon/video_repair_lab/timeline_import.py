"""Small stdlib-only adapter. Never import the engine's NumPy/SciPy dependencies."""
import math
import hashlib
from pathlib import Path

import bpy

SCHEMA = "video-repair-lab.timeline.v1"


def import_component(report, component_id=0):
    if report.get("schema") != SCHEMA:
        raise ValueError("Unsupported Video Repair Lab timeline schema")
    component = next((c for c in report["components"] if c["id"] == component_id), None)
    if component is None or component.get("conflicts"):
        raise ValueError("Missing group or contradictory matches; review the engine report")
    fps = component["fps"]
    if not isinstance(fps, (int, float)) or not math.isfinite(fps) or not 1 <= fps <= 120:
        raise ValueError("Invalid frame rate")
    sources = {c["id"]: c for c in report["sources"]}
    checked = set()
    # Validate everything before changing Blender data.
    cursor = 0
    for segment in component["segments"]:
        clip = sources[segment["source_id"]]
        if not Path(clip["path"]).is_file():
            raise ValueError(f"Source moved or missing: {clip['path']}")
        if clip["id"] not in checked:
            with Path(clip["path"]).open("rb") as stream:
                actual = hashlib.file_digest(stream, "sha256").hexdigest()
            if actual != clip["id"]:
                raise ValueError("Source changed after analysis; analyze again before importing")
            checked.add(clip["id"])
        start, end = segment["timeline_start_frame"], segment["timeline_end_frame"]
        a, b = segment["source_start_frame"], segment["source_end_frame"]
        if any(type(v) is not int for v in (start, end, a, b)) or start != cursor or end <= start or b - a != end - start:
            raise ValueError("Invalid or discontinuous timeline intervals")
        if not 0 <= a < b <= round(clip["duration"] * fps):
            raise ValueError("Source trim is out of bounds")
        cursor = end
    if cursor <= 0:
        raise ValueError("Empty timeline")
    scene = bpy.data.scenes.new(f"Reconstruction group {component_id + 1} (relative)")
    try:
        scene.render.fps = round(fps)
        scene.render.fps_base = round(fps) / fps
        scene.frame_start, scene.frame_end = 1, cursor
        used = [sources[s["source_id"]] for s in component["segments"]]
        largest = max(used, key=lambda c: c["width"] * c["height"])
        scene.render.resolution_x, scene.render.resolution_y = largest["width"], largest["height"]
        scene.render.resolution_percentage = 100
        scene.render.image_settings.file_format = "FFMPEG"
        scene.render.ffmpeg.format = "MPEG4"
        scene.render.ffmpeg.codec = "H264"
        scene.render.ffmpeg.audio_codec = "AAC"
        scene.view_settings.view_transform = "Standard"
        editor = scene.sequence_editor_create()
        for index, segment in enumerate(component["segments"]):
            clip = sources[segment["source_id"]]
            start, end = segment["timeline_start_frame"] + 1, segment["timeline_end_frame"] + 1
            source_in = segment["source_start_frame"]
            movie = editor.strips.new_movie(Path(clip["path"]).name, clip["path"], channel=2,
                                            frame_start=start - source_in, fit_method="FIT")
            movie.frame_final_start, movie.frame_final_end = start, end
            movie["vrl_source_id"] = clip["id"]
            if clip["has_audio"]:
                sound = editor.strips.new_sound(f"Audio {index + 1}", clip["path"], channel=1, frame_start=start - source_in)
                sound.frame_final_start, sound.frame_final_end = start, end
            else:
                scene.timeline_markers.new("AUDIO MISSING", frame=start)
            if index:
                scene.timeline_markers.new("Review source join", frame=start)
        scene.timeline_markers.new("Relative start; original extent unknown", frame=1)
        scene["vrl_component_id"] = component_id
        scene["vrl_complete_original"] = False
        scene["vrl_status"] = component["status"]
        return scene
    except Exception:
        bpy.data.scenes.remove(scene)
        raise
