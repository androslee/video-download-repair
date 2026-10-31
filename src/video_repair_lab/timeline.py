"""Timeline solving and validation, independent of Blender and FFmpeg processes."""
import math
from pathlib import Path

from .media import RepairError

SCHEMA = "video-repair-lab.timeline.v1"


def solve(clips, matches):
    by_id = {c["id"]: c for c in clips}
    graph = {c["id"]: [] for c in clips}
    for edge in matches:
        if edge["accepted"]:
            graph[edge["a"]].append((edge["b"], edge["offset"]))
            graph[edge["b"]].append((edge["a"], -edge["offset"]))
    seen, components = set(), []
    for root in sorted(graph):
        if root in seen:
            continue
        positions, queue, conflicts = {root: 0.0}, [root], []
        while queue:
            node = queue.pop(0)
            seen.add(node)
            for target, delta in graph[node]:
                proposed = positions[node] + delta
                if target not in positions:
                    positions[target] = proposed
                    queue.append(target)
                elif abs(positions[target] - proposed) > 0.01:
                    conflicts.append({"a": node, "b": target, "residual_seconds": positions[target] - proposed})
        origin = min(positions.values())
        positions = {k: round(v - origin, 6) for k, v in positions.items()}
        fps = by_id[root]["fps"]
        segments = select_coverage(positions, by_id, fps)
        components.append({"id": len(components), "positions": positions,
                           "fps": fps, "conflicts": conflicts, "segments": segments,
                           "duration": max(positions[k] + by_id[k]["duration"] for k in positions),
                           "status": "conflict" if conflicts else "relative_overlap" if len(positions) > 1 else "unplaced"})
    return components


def select_coverage(positions, by_id, fps):
    # Rank by nominal resolution only; no claim of perceptual quality estimation.
    starts = {k: round(v * fps) for k, v in positions.items()}
    ends = {k: starts[k] + round(by_id[k]["duration"] * fps) for k in starts}
    boundaries = sorted(set(starts.values()) | set(ends.values()))
    segments = []
    previous = None
    for start, end in zip(boundaries, boundaries[1:]):
        available = [k for k in starts if starts[k] <= start and ends[k] >= end]
        if not available:
            continue
        chosen = max(available, key=lambda k: (by_id[k]["width"] * by_id[k]["height"], k == previous, ends[k], k))
        if segments and segments[-1]["source_id"] == chosen and segments[-1]["timeline_end_frame"] == start:
            segments[-1]["timeline_end_frame"] = end
            segments[-1]["source_end_frame"] = end - starts[chosen]
        else:
            segments.append({"source_id": chosen, "timeline_start_frame": start, "timeline_end_frame": end,
                             "source_start_frame": start - starts[chosen], "source_end_frame": end - starts[chosen]})
        previous = chosen
    return segments


def validate_component(report, component_id, *, require_connected=False):
    if report.get("schema") != SCHEMA:
        raise RepairError("Unsupported timeline schema.")
    components = report.get("components", [])
    if require_connected and len(components) != 1:
        raise RepairError("The clips have unresolved relative order. Select a single component explicitly for a partial export.")
    component = next((c for c in components if c["id"] == component_id), None)
    if component is None or component.get("conflicts"):
        raise RepairError("Missing component or contradictory alignment evidence; review required.")
    fps = component["fps"]
    if not isinstance(fps, (int, float)) or not math.isfinite(fps) or not 1 <= fps <= 120:
        raise RepairError("Invalid timeline frame rate.")
    sources = {c["id"]: c for c in report["sources"]}
    cursor = 0
    for segment in component["segments"]:
        clip = sources.get(segment["source_id"])
        if clip is None or not Path(clip["path"]).is_file():
            raise RepairError("A timeline source is missing; regenerate the analysis after moving files.")
        a, b = segment["source_start_frame"], segment["source_end_frame"]
        start, end = segment["timeline_start_frame"], segment["timeline_end_frame"]
        if any(type(v) is not int for v in (a, b, start, end)) or not (0 <= a < b <= round(clip["duration"] * fps)):
            raise RepairError("Invalid source trim bounds.")
        if start != cursor or end - start != b - a:
            raise RepairError("Timeline contains a gap, duplicate interval or unequal source/output duration.")
        cursor = end
    if not cursor:
        raise RepairError("Empty timeline.")
    return component, sources
