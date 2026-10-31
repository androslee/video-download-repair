"""Prepare blind local datasets from full videos; never pass the answer key to inference."""
from __future__ import annotations

from fractions import Fraction
from fnmatch import fnmatchcase
import json
import math
import os
from pathlib import Path
import random
import secrets
import tempfile

from .media import EXTENSIONS, MAX_CLIPS, MAX_CLIP_SECONDS, MAX_TOTAL_SECONDS, RepairError, digest, executable, ffmpeg, run

SCHEMA = "video-repair-lab.shuffle.v1"
STAMP = 1700000000
SOURCE_EXTENSIONS = EXTENSIONS | {".ts", ".m2ts", ".mts", ".mpg", ".mpeg", ".wmv", ".flv", ".ogv"}


def discover_sources(inputs, *, exclude=()):
    """Expand files and recursive directories deterministically before probing.

    Explicit files are retained even when an exclusion matches; directory symlinks
    and discovered symlink files are not followed. Overlapping inputs are deduplicated.
    """
    found, seen = [], set()

    def add(path):
        resolved = path.resolve(strict=True)
        if resolved not in seen:
            seen.add(resolved)
            found.append(resolved)
            if len(found) > 32:
                raise RepairError("Found more than 32 distinct source files. Select a narrower folder or exclude files.")

    def fail_walk(error):
        raise RepairError(f"Cannot scan input folder: {error}") from error

    for entry in inputs:
        path = Path(entry).resolve(strict=True)
        if path.is_file():
            add(path)
        elif path.is_dir():
            for parent, dirs, files in os.walk(path, followlinks=False, onerror=fail_walk):
                base = Path(parent)
                dirs[:] = sorted(d for d in dirs if not (base / d).is_symlink())
                for filename in sorted(files):
                    item = base / filename
                    relative = item.relative_to(path).as_posix()
                    if (item.is_symlink() or item.suffix.lower() not in SOURCE_EXTENSIONS
                            or any(fnmatchcase(filename, pattern) or fnmatchcase(relative, pattern) for pattern in exclude)):
                        continue
                    if item.is_file():
                        add(item)
        else:
            raise RepairError(f"Input is not a regular video file or folder: {path}")
    if not found:
        raise RepairError("No supported video files found in the supplied input paths.")
    return found


def source_info(path):
    """Metadata-only probing supports full-length source movies, not just engine-sized clips."""
    path = Path(path).resolve(strict=True)
    if not path.is_file():
        raise RepairError(f"Not a local video file: {path}")
    raw = json.loads(run([executable("ffprobe"), "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)]))
    videos = [s for s in raw["streams"] if s["codec_type"] == "video" and not s.get("disposition", {}).get("attached_pic")]
    audios = [s for s in raw["streams"] if s["codec_type"] == "audio"]
    if len(videos) != 1 or len(audios) > 1:
        raise RepairError(f"{path.name}: select a file with one picture stream and at most one audio track.")
    v = videos[0]
    try:
        fps = Fraction(v["avg_frame_rate"])
        duration = float(v.get("duration", raw.get("format", {}).get("duration", 0)))
        video_start = float(v.get("start_time", 0))
        audio_start = float(audios[0].get("start_time", 0)) if audios else video_start
    except (KeyError, TypeError, ValueError, ZeroDivisionError) as exc:
        raise RepairError(f"{path.name}: missing or invalid timing metadata") from exc
    if not math.isfinite(duration) or duration <= 0 or not 1 <= fps <= 120:
        raise RepairError(f"{path.name}: invalid duration/frame rate")
    # Do not erase deliberate stream delays while preparing supposed ground truth.
    if not math.isfinite(video_start) or abs(video_start) > 0.02 or abs(audio_start - video_start) > 0.02:
        raise RepairError(f"{path.name}: nonzero or different A/V start times need normalization before shuffling.")
    return {"path": str(path), "duration": duration, "fps": str(fps), "width": v["width"], "height": v["height"],
            "video_stream": v["index"], "audio_stream": audios[0]["index"] if audios else None}


def boundaries(total_frames, fps, minimum, maximum, rng, cuts=None):
    if cuts is not None:
        if any(not math.isfinite(t) for t in cuts):
            raise RepairError("Cut points must be finite")
        points = [round(t * fps) for t in cuts]
        if not points or points != sorted(set(points)) or points[0] <= 0 or points[-1] >= total_frames:
            raise RepairError("Cut points must be finite, increasing, unique frame positions inside the selected window.")
        return [0, *points, total_frames]
    low, high = round(minimum * fps), round(maximum * fps)
    points = [0]
    while points[-1] < total_frames:
        points.append(min(total_frames, points[-1] + rng.randint(low, high)))
    # Absorb a small tail when it fits the requested maximum. Otherwise the final
    # piece is explicitly allowed to be shorter than the target minimum.
    if len(points) > 2 and points[-1] - points[-2] < low and points[-1] - points[-3] <= high:
        del points[-2]
    return points


def plan_shuffle(paths, *, mode="both", minimum=20, maximum=40, overlap=5, folders=3,
                 seed=None, variants="all", start=0, duration=None, fps=None, cuts=None, omit_pieces=None, exclude=()):
    if mode not in ("clean", "overlap", "both") or variants not in ("all", "mixed"):
        raise RepairError("Invalid shuffle mode or variant policy")
    numbers = [minimum, maximum, overlap, start] + ([] if duration is None else [duration])
    if not all(math.isfinite(v) for v in numbers) or not 1 <= minimum <= maximum or overlap < 0 or start < 0 or (duration is not None and duration <= 0):
        raise RepairError("Use finite positive durations, 1 <= min-seconds <= max-seconds, and nonnegative start/overlap.")
    if not 1 <= folders <= 100:
        raise RepairError("Use 1–100 destination folders")
    sources = [source_info(p) for p in discover_sources(paths, exclude=exclude)]
    try:
        rate = Fraction(fps or sources[0]["fps"])
    except (ValueError, ZeroDivisionError) as exc:
        raise RepairError("Invalid output fps; use e.g. 24, 30 or 30000/1001") from exc
    if not 1 <= rate <= 120:
        raise RepairError("Output fps must be between 1 and 120")
    # Copies with substantially different lengths are not silently treated as one edit.
    if duration is None and max(s["duration"] for s in sources) - min(s["duration"] for s in sources) > max(0.1, 2 / float(rate)):
        raise RepairError("Source lengths differ. Use aligned copies of the same edit, or explicitly select a common --duration.")
    available = min(s["duration"] for s in sources) - start
    selected = available if duration is None else duration
    if selected <= 0 or selected > available + 0.001:
        raise RepairError("Selected start/duration is outside at least one source")
    total = math.floor(selected * float(rate) + 1e-5)
    if total < 2:
        raise RepairError("Selected window must contain at least two output frames")
    seed = secrets.randbits(63) if seed is None else seed
    rng = random.Random(seed)
    points = boundaries(total, float(rate), minimum, maximum, rng, cuts)
    extension = round(overlap * float(rate))
    if mode != "clean" and extension < 1:
        raise RepairError("Overlap mode requires an overlap of at least one frame")
    count = len(points) - 1
    omitted = set(omit_pieces or [])
    if any(type(i) is not int or i < 1 or i > count for i in omitted) or len(omitted) == count:
        raise RepairError(f"Omitted piece numbers must be between 1 and {count}, and at least one piece must remain.")
    if variants == "mixed" and count < len(sources):
        raise RepairError("Mixed mode needs at least one piece per source; use shorter pieces or --variants all")
    choices = [i % len(sources) for i in range(count)]
    rng.shuffle(choices)
    modes = ["clean", "overlap"] if mode == "both" else [mode]
    cases = {}
    warnings = ["Multiple inputs must be aligned copies of the same edit; matching duration does not verify matching content."] if len(sources) > 1 else []
    if omitted:
        warnings.append("Omitted base pieces simulate missing material; overlapping neighbors may still cover part or all of an omitted interval.")
    for case in modes:
        jobs = []
        for index, (a, b) in enumerate(zip(points, points[1:])):
            if index + 1 in omitted:
                continue
            end = min(total, b + extension) if case == "overlap" else b
            for source in (range(len(sources)) if variants == "all" else [choices[index]]):
                jobs.append({"source": source, "start_frame": a, "end_frame": end})
        if len(jobs) > 10000:
            raise RepairError("Too many output pieces (maximum 10,000 per case); increase clip length")
        rng.shuffle(jobs)  # Encoding order and filesystem creation order also carry no chronology.
        buckets = [f"set-{rng.getrandbits(64):016x}" for _ in range(min(folders, len(jobs)))]
        used_names = set()
        for i, job in enumerate(jobs):
            while True:
                name = f"clip-{rng.getrandbits(96):024x}.mp4"
                if name not in used_names:
                    used_names.add(name)
                    break
            job["file"] = f"{case}/inputs/{buckets[i % len(buckets)]}/{name}"
        cases[case] = jobs
        lengths = [(j["end_frame"] - j["start_frame"]) / float(rate) for j in jobs]
        if len(jobs) > MAX_CLIPS or min(lengths) < 1 or max(lengths) > MAX_CLIP_SECONDS or sum(lengths) > MAX_TOTAL_SECONDS:
            warnings.append(f"{case}: dataset exceeds current reconstruction-engine limits (2–24 clips, 1–120s each, 1200s total). Use --duration/longer or shorter pieces as appropriate.")
        if len(jobs) < 2:
            warnings.append(f"{case}: only one output clip; choose shorter pieces to test reconstruction.")
    if mode != "clean" and overlap < 2:
        warnings.append("The current overlap matcher needs at least 2 seconds of informative shared picture/audio.")
    if any(s["audio_stream"] is None for s in sources):
        warnings.append("Some sources have no audio; their samples remain silent and cannot currently establish automatic matches.")
    return {"schema": SCHEMA, "seed": seed, "sources": sources, "fps": str(rate), "total_frames": total,
            "start_seconds": start, "duration_seconds": total / float(rate), "cuts_frames": points,
            "variants": variants, "overlap_frames": extension, "omitted_pieces": sorted(omitted), "cases": cases, "warnings": warnings}


def inspect_encoded(path, expected_frames, has_audio, fps):
    raw = json.loads(run([executable("ffprobe"), "-v", "error", "-count_frames", "-show_streams",
                          "-of", "json", str(path)], timeout=3600))
    v = next(s for s in raw["streams"] if s["codec_type"] == "video")
    a = next((s for s in raw["streams"] if s["codec_type"] == "audio"), None)
    if int(v.get("nb_read_frames", -1)) != expected_frames or abs(float(v.get("start_time", 0))) > 0.002:
        raise RepairError(f"{path.name}: output frame count or start time does not match the planned cut")
    if bool(a) != has_audio:
        raise RepairError(f"{path.name}: audio stream unexpectedly missing/added")
    if a and (abs(float(a.get("start_time", 0))) > 0.002 or abs(float(a.get("duration", 0)) - expected_frames / fps) > 0.05):
        raise RepairError(f"{path.name}: audio length/timing does not match the planned cut")
    return {"frames": expected_frames, "width": v["width"], "height": v["height"], "has_audio": has_audio}


def prepare_shuffle(paths, output, *, dry_run=False, keep_references=False, progress=lambda message: None, **options):
    output = Path(output).resolve()
    if output.exists():
        raise RepairError("Output already exists; choose a new dataset directory. Nothing is overwritten.")
    exclude = options.pop("exclude", ()) or ()
    selected = discover_sources(paths, exclude=exclude)
    progress(f"Found {len(selected)} source video(s):")
    for path in selected:
        progress(f"  {path}")
    plan = plan_shuffle(selected, **options)
    if dry_run:
        return {"output": str(output), "seed": plan["seed"], "fps": plan["fps"], "duration_seconds": plan["duration_seconds"],
                "sources": [s["path"] for s in plan["sources"]],
                "counts": {k: len(v) for k, v in plan["cases"].items()}, "warnings": plan["warnings"], "dry_run": True}
    output.mkdir(parents=True, exist_ok=False)
    truth = output / "truth"
    truth.mkdir()
    incomplete = output / "INCOMPLETE.txt"
    incomplete.write_text("Preparation has not completed. Do not use this dataset for evaluation.\n", encoding="utf-8")
    rate = float(Fraction(plan["fps"]))
    for warning in plan["warnings"]:
        progress("Note: " + warning)
    # Normalize once per source, so every cut refers to exactly the same CFR grid.
    # Temporary normalized media are private and removed on both success/failure.
    with tempfile.TemporaryDirectory(prefix=".preparing-", dir=output) as work:
        normalized = []
        for index, source in enumerate(plan["sources"]):
            progress(f"Preparing source {index + 1}/{len(plan['sources'])} on the shared frame grid…")
            source["sha256"] = digest(source["path"])
            target = Path(work) / f"source-{index}.mp4"
            audio = source["audio_stream"] is not None
            args = ["-ss", plan["start_seconds"], "-i", source["path"], "-map", f"0:{source['video_stream']}"]
            if audio:
                args += ["-map", f"0:{source['audio_stream']}", "-af", "aresample=48000", "-c:a", "alac"]
            else:
                args += ["-an"]
            # Retain each source's displayed resolution, including rotation/anamorphic correction.
            args += ["-vf", f"fps={plan['fps']}:start_time=0,scale=trunc(iw*sar/2)*2:trunc(ih/2)*2,setsar=1",
                     "-t", f"{plan['duration_seconds']:.12f}", "-c:v", "libx264", "-preset", "fast", "-crf", "16",
                     "-pix_fmt", "yuv420p", "-map_metadata", "-1", "-map_metadata:s", "-1", "-map_chapters", "-1", "-n", target]
            ffmpeg(*args, timeout=86400)
            source["normalized"] = inspect_encoded(target, plan["total_frames"], audio, rate)
            normalized.append(target)
        for case, jobs in plan["cases"].items():
            for index, job in enumerate(jobs):
                progress(f"Writing {case} piece {index + 1}/{len(jobs)}…")
                path = output / job["file"]
                path.parent.mkdir(parents=True, exist_ok=True)
                source = plan["sources"][job["source"]]
                audio = source["audio_stream"] is not None
                count = job["end_frame"] - job["start_frame"]
                args = ["-ss", f"{job['start_frame'] / rate:.12f}", "-i", normalized[job["source"]],
                        "-t", f"{count / rate:.12f}", "-map", "0:v:0", "-c:v", "libx264", "-preset", "fast", "-crf", "18"]
                args += ["-map", "0:a:0", "-c:a", "aac", "-b:a", "192k"] if audio else ["-an"]
                args += ["-pix_fmt", "yuv420p", "-map_metadata", "-1", "-map_metadata:s", "-1", "-map_chapters", "-1", "-n", path]
                ffmpeg(*args, timeout=86400)
                job["encoded"] = inspect_encoded(path, count, audio, rate)
                job["sha256"] = digest(path)
                os.utime(path, (STAMP, STAMP))
        if keep_references:
            references = truth / "references"
            references.mkdir()
            for i, path in enumerate(normalized):
                destination = references / path.name
                path.replace(destination)
                plan["sources"][i]["reference_file"] = destination.relative_to(output).as_posix()
    for case in plan["cases"]:
        directory = output / case / "inputs"
        for path in sorted(directory.rglob("*"), reverse=True):
            if path.is_dir():
                os.utime(path, (STAMP, STAMP))
        os.utime(directory, (STAMP, STAMP))
    plan["ffmpeg_version"] = run([executable("ffmpeg"), "-version"]).decode().splitlines()[0]
    plan["encoding"] = {"normalization": "H.264 CRF16 + lossless ALAC (if sound exists)", "pieces": "H.264 CRF18 + AAC192k", "frame_intervals": "zero-based, end-exclusive in normalized source window"}
    plan["complete"] = True
    with (truth / "manifest.json").open("x", encoding="utf-8") as stream:
        json.dump(plan, stream, indent=2, allow_nan=False)
    (output / "README.txt").write_text(
        "Prepared blind video samples. Feed only a case's inputs/ folder to the assembler with --recursive.\n"
        "Keep truth/manifest.json (and optional references) away from inference. It contains the answer key.\n"
        "Clean pieces have no shared coverage; their original order may be unknowable without review.\n", encoding="utf-8")
    incomplete.unlink()
    return {"output": str(output), "seed": plan["seed"], "counts": {k: len(v) for k, v in plan["cases"].items()},
            "inputs": {case: str(output / case / "inputs") for case in plan["cases"]}, "warnings": plan["warnings"]}
