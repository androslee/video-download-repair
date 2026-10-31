"""Human-readable, relative timeline provenance; never uses the answer key for matching."""
from pathlib import Path
import math

from .media import RepairError
from .timeline import SCHEMA


def clock(seconds):
    ms = round(seconds * 1000)
    hours, ms = divmod(ms, 3_600_000)
    minutes, ms = divmod(ms, 60_000)
    seconds, ms = divmod(ms, 1000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}.{ms:03d}"


def answer_key_sources(key):
    if key.get("schema") != "video-repair-lab.shuffle.v1" or not key.get("complete"):
        raise RepairError("Expected a completed shuffler answer key.")
    result = {}
    try:
        for jobs in key["cases"].values():
            for job in jobs:
                original = key["sources"][job["source"]]["path"]
                prior = result.setdefault(job["sha256"], original)
                if prior != original:
                    raise RepairError("Answer key has conflicting source identities.")
    except (KeyError, IndexError, TypeError) as exc:
        raise RepairError("Invalid shuffler answer key.") from exc
    return result


def format_report(report, answer_key=None):
    if report.get("schema") != SCHEMA:
        raise RepairError("Unsupported timeline schema.")
    sources = {s["id"]: s for s in report["sources"]}
    originals = answer_key_sources(answer_key) if answer_key is not None else None
    lines = ["VIDEO REPAIR LAB — SOURCE TIMELINE", "",
             f"Status: {report.get('status', 'unknown')}; groups: {len(report['components'])}",
             "All times are relative to each group; original start/end are unknown.",
             "Resolution is nominal; it is not a measurement of perceptual quality."]
    if originals is not None:
        lines.append("Original filenames are from the supplied shuffler answer key, not inferred by matching.")
    if len(report["components"]) > 1:
        lines.append("Groups have unknown relative placement; their timestamps cannot be compared.")
    for component in report["components"]:
        fps = component["fps"]
        if not isinstance(fps, (int, float)) or not math.isfinite(fps) or fps <= 0:
            raise RepairError("Invalid timeline frame rate.")
        lines.extend(["", f"GROUP {component['id']} — {component['status']}; duration {clock(component['duration'])}"])
        if component.get("conflicts"):
            lines.append("  WARNING: contradictory alignment evidence; review required.")
        for index, segment in enumerate(component["segments"], 1):
            source = sources[segment["source_id"]]
            start, end = segment["timeline_start_frame"] / fps, segment["timeline_end_frame"] / fps
            a, b = segment["source_start_frame"] / fps, segment["source_end_frame"] / fps
            lines.extend([f"  {index}. {clock(start)} – {clock(end)}  ({source['width']}x{source['height']})",
                          f"     Clip: {source['path']}",
                          f"     Clip time: {clock(a)} – {clock(b)}"])
            if originals is not None:
                lines.append(f"     Original source: {originals.get(source['id'], 'not found in supplied answer key')}")
            for other_id, position in sorted(component["positions"].items()):
                if other_id == source["id"]:
                    continue
                other = sources[other_id]
                lo, hi = max(start, position), min(end, position + other["duration"])
                if hi > lo + 1 / fps:
                    lines.append(f"     Alternative {clock(lo)} – {clock(hi)}: {other['width']}x{other['height']} {other['path']}")
    lines.extend(["", "Intervals are end-exclusive. Inspect joins and any low-resolution sections before use."])
    return "\n".join(lines) + "\n"
