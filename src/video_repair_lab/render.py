"""Conservative frame-grid render: decode/trim/re-encode, never alter source media."""
import json
import os
from pathlib import Path
import tempfile

from .media import AUDIO_RATE, RepairError, digest, executable, ffmpeg, run
from .timeline import validate_component


def render(report, destination, component_id=None, *, progress=lambda message: None):
    component, sources = validate_component(report, component_id if component_id is not None else 0,
                                            require_connected=component_id is None)
    destination = Path(destination).resolve()
    if destination.exists() or destination.suffix.lower() != ".mp4":
        raise RepairError("Choose a new .mp4 output path. Existing files are never overwritten.")
    fps = component["fps"]
    used = {s["source_id"] for s in component["segments"]}
    for key in used:
        if digest(sources[key]["path"]) != sources[key]["id"]:
            raise RepairError("A source changed after analysis; run analysis again.")
        if not sources[key]["has_audio"]:
            raise RepairError("Audio is missing. Review in Blender; this prototype will not silently fill an audio gap.")
    largest = max((sources[k] for k in used), key=lambda c: c["width"] * c["height"])
    width, height = largest["width"] // 2 * 2, largest["height"] // 2 * 2
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="vrl-render-", dir=destination.parent) as temp:
        temp = Path(temp)
        paths = []
        for i, segment in enumerate(component["segments"]):
            path = temp / f"part-{i}.mkv"
            clip = sources[segment["source_id"]]
            progress(f"Rendering segment {i + 1}/{len(component['segments'])}: {clip['width']}x{clip['height']} {clip['path']}")
            a, b = segment["source_start_frame"], segment["source_end_frame"]
            vf = (f"trim=start_frame={a}:end_frame={b},setpts=PTS-STARTPTS,"
                  f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
                  f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setsar=1")
            af = f"atrim=start={a / fps:.9f}:end={b / fps:.9f},asetpts=PTS-STARTPTS,aresample=48000"
            ffmpeg("-i", clip["path"], "-map", "0:v:0", "-map", "0:a:0", "-vf", vf, "-af", af,
                   "-c:v", "libx264", "-preset", "fast", "-crf", "16", "-pix_fmt", "yuv420p",
                   "-c:a", "pcm_s16le", "-ar", "48000", "-ac", "2", "-map_metadata", "-1", "-n", path)
            paths.append(path)
        # Only generated, controlled basenames enter the concat list (no shell/filter injection).
        listing = temp / "parts.txt"
        listing.write_text("".join(f"file '{p.name}'\n" for p in paths))
        output = temp / "assembled.mp4"
        progress("Joining segments and encoding the final video…")
        ffmpeg("-f", "concat", "-safe", "1", "-i", listing, "-c:v", "libx264", "-preset", "fast", "-crf", "18",
               "-r", f"{fps:.12f}", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
               "-movflags", "+faststart", "-map_metadata", "-1", "-n", output, timeout=600)
        # Fully decode the render and inspect decoded frame count and presentation timing.
        progress("Checking picture, timestamps and audio…")
        ffmpeg("-i", output, "-f", "null", "-", timeout=600)
        frames = json.loads(run([executable("ffprobe"), "-v", "error", "-select_streams", "v:0",
                                 "-show_entries", "frame=best_effort_timestamp_time", "-of", "json", str(output)]))["frames"]
        expected = component["segments"][-1]["timeline_end_frame"]
        if len(frames) != expected:
            raise RepairError(f"Render frame count mismatch: expected {expected}, got {len(frames)}.")
        stamps = [float(f["best_effort_timestamp_time"]) for f in frames]
        if any(abs(t - i / fps) > 0.002 for i, t in enumerate(stamps)):
            raise RepairError("Rendered video timestamps do not match the timeline.")
        audio = ffmpeg("-i", output, "-vn", "-ac", "1", "-ar", AUDIO_RATE, "-f", "f32le", "pipe:1", timeout=600)
        audio_duration = len(audio) / 4 / AUDIO_RATE
        if abs(audio_duration - expected / fps) > 0.05:
            raise RepairError("Rendered audio duration does not match picture (beyond codec padding tolerance).")
        # Exclusive create via hard link: a racing writer cannot be overwritten.
        os.link(output, destination)
    return {"output": str(destination), "frames": expected, "duration": expected / fps,
            "audio_duration": audio_duration, "component_id": component["id"], "complete_original": False}
