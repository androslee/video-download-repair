"""Bounded local FFmpeg decoding. All subprocess arguments are passed without a shell."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
from fractions import Fraction

import numpy as np

VIDEO_RATE = 8
AUDIO_RATE = 8000
WIDTH, HEIGHT = 32, 18
MAX_CLIP_SECONDS = 120
MAX_TOTAL_SECONDS = 1200
MAX_CLIPS = 24
EXTENSIONS = {".mp4", ".mkv", ".mov", ".webm", ".avi", ".m4v"}
LOCAL_FFMPEG_DIR = Path(__file__).resolve().parents[2] / ".local" / "tools" / "ffmpeg-package" / "usr" / "bin"


class RepairError(ValueError):
    pass


def executable(name):
    override = os.environ.get("VRL_" + name.upper())
    if override is not None:
        found = shutil.which(override)
        if not found:
            raise RepairError(f"VRL_{name.upper()} points to an unavailable executable: {override}")
        return found
    found = shutil.which(name)
    if found:
        return found
    local_name = name + (".exe" if os.name == "nt" else "")
    found = shutil.which(str(LOCAL_FFMPEG_DIR / local_name))
    if found:
        return found
    raise RepairError(f"{name} not found. Install FFmpeg or set VRL_{name.upper()} to its executable.")


def run(args, *, timeout=180):
    try:
        proc = subprocess.run(args, capture_output=True, timeout=timeout, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RepairError(f"Media command failed: {exc}") from exc
    if proc.returncode:
        raise RepairError(proc.stderr.decode(errors="replace")[-4000:] or f"Command exited {proc.returncode}")
    return proc.stdout


def ffmpeg(*args, timeout=180):
    return run([executable("ffmpeg"), "-nostdin", "-hide_banner", "-loglevel", "error", "-xerror",
                "-threads", "2", *map(str, args)], timeout=timeout)


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def probe(path):
    path = Path(path).resolve(strict=True)
    raw = json.loads(run([executable("ffprobe"), "-v", "error", "-show_streams", "-show_format",
                          "-of", "json", str(path)]))
    videos = [s for s in raw["streams"] if s["codec_type"] == "video" and not s.get("disposition", {}).get("attached_pic")]
    audios = [s for s in raw["streams"] if s["codec_type"] == "audio"]
    if len(videos) != 1 or len(audios) > 1:
        raise RepairError(f"{path.name}: prototype needs one video stream and at most one audio stream.")
    v = videos[0]
    fps = float(Fraction(v.get("avg_frame_rate", "0/1")))
    duration = float(v.get("duration", raw.get("format", {}).get("duration", 0)))
    if not 1 <= duration <= MAX_CLIP_SECONDS or not 1 <= fps <= 120:
        raise RepairError(f"{path.name}: supported range is 1–{MAX_CLIP_SECONDS}s per clip, 1–120 fps.")
    if v.get("sample_aspect_ratio", "1:1") not in ("1:1", "N/A"):
        raise RepairError(f"{path.name}: non-square pixels need normalization before this prototype.")
    if any(abs(float(s.get("rotation", 0))) > 0.01 for s in v.get("side_data_list", [])) or v.get("tags", {}).get("rotate", "0") != "0":
        raise RepairError(f"{path.name}: rotate the clip into its displayed orientation first.")
    if audios and abs(float(audios[0].get("start_time", 0)) - float(v.get("start_time", 0))) > 0.02:
        raise RepairError(f"{path.name}: differing audio/video start timestamps need explicit handling; refusing to shift them.")
    frames = json.loads(run([executable("ffprobe"), "-v", "error", "-read_intervals", f"%+{MAX_CLIP_SECONDS + 1}", "-select_streams", "v:0",
                             "-show_entries", "frame=best_effort_timestamp_time", "-of", "json", str(path)]))["frames"]
    stamps = np.array([float(f["best_effort_timestamp_time"]) for f in frames if "best_effort_timestamp_time" in f])
    if len(stamps) < 2 or np.max(np.abs(np.diff(stamps) - 1 / fps)) > max(0.002, 0.05 / fps):
        raise RepairError(f"{path.name}: variable or damaged frame timing is not supported yet.")
    duration = float(stamps[-1] - stamps[0] + 1 / fps)
    if duration > MAX_CLIP_SECONDS + 0.002:
        raise RepairError(f"{path.name}: decoded duration exceeds the prototype's limit.")
    return {"id": digest(path), "path": str(path), "duration": duration, "fps": fps,
            "width": v["width"], "height": v["height"], "has_audio": bool(audios),
            "video_start": float(v.get("start_time", 0))}


def decode_features(clip):
    # Restrict output duration even if malformed container metadata under-reports it.
    pixels = ffmpeg("-i", clip["path"], "-t", MAX_CLIP_SECONDS, "-map", "0:v:0", "-an",
                    "-vf", f"setpts=PTS-STARTPTS,fps={VIDEO_RATE},scale={WIDTH}:{HEIGHT}:flags=area,format=gray",
                    "-f", "rawvideo", "pipe:1")
    video = np.frombuffer(pixels, np.uint8).reshape(-1, HEIGHT * WIDTH).astype(np.float32) / 255
    centered = video - video.mean(axis=1, keepdims=True)
    norms = np.linalg.norm(centered, axis=1, keepdims=True)
    features = centered / np.maximum(norms, 1e-6)
    audio = np.empty(0, dtype=np.float32)
    if clip["has_audio"]:
        audio = np.frombuffer(ffmpeg("-i", clip["path"], "-t", MAX_CLIP_SECONDS, "-map", "0:a:0", "-vn",
                                    "-ac", "1", "-ar", AUDIO_RATE, "-f", "f32le", "pipe:1"), dtype="<f4").copy()
    return {"video": features, "pixels": video, "audio": audio}


def discover(directory, *, recursive=False):
    directory = Path(directory).resolve(strict=True)
    if not directory.is_dir():
        raise RepairError("Input must be a folder containing only the fragments to analyze.")
    if (directory / "truth").exists() or (directory / "INCOMPLETE.txt").exists():
        raise RepairError("Select a completed dataset's case/inputs folder, not its root or answer key.")
    if any((parent / "INCOMPLETE.txt").exists() for parent in directory.parents):
        raise RepairError("This dataset is incomplete; preparation must finish before reconstruction.")
    if directory.name == "truth" or any(parent.name == "truth" for parent in directory.parents):
        raise RepairError("The truth folder is for evaluation only; select the case/inputs folder.")
    candidates = directory.rglob("*") if recursive else directory.iterdir()
    paths = sorted(p for p in candidates if p.is_file() and p.suffix.lower() in EXTENSIONS and not p.is_symlink())
    if not 2 <= len(paths) <= MAX_CLIPS:
        raise RepairError(f"Select 2–{MAX_CLIPS} video clips; found {len(paths)}.")
    clips = []
    for path in paths:
        clip = probe(path)
        if sum(c["duration"] for c in clips) + clip["duration"] > MAX_TOTAL_SECONDS:
            raise RepairError(f"Prototype limit: {MAX_TOTAL_SECONDS}s of input total.")
        clips.append(clip)
    # Content identities make ordering independent of filename or directory enumeration.
    unique = {}
    duplicates = []
    for clip in clips:
        if clip["id"] in unique:
            duplicates.append({"path": clip["path"], "same_as": unique[clip["id"]]["path"]})
        else:
            unique[clip["id"]] = clip
    return sorted(unique.values(), key=lambda c: c["id"]), duplicates
