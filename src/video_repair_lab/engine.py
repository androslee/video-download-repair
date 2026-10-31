from datetime import datetime, timezone
from itertools import combinations
from time import perf_counter

from .matching import match_pair
from .media import decode_features, discover, executable, run
from .timeline import SCHEMA, solve
from . import __version__


def analyze(directory, progress=lambda message: None, *, recursive=False):
    started = perf_counter()
    progress("Probing fragments and checking constant frame timing…")
    clips, duplicates = discover(directory, recursive=recursive)
    probed = perf_counter()
    features = {}
    for i, clip in enumerate(clips):
        progress(f"Decoding analysis proxies {i + 1}/{len(clips)}: {clip['path']}")
        features[clip["id"]] = decode_features(clip)
    decoded = perf_counter()
    matches = []
    pairs = list(combinations(clips, 2))
    for i, (a, b) in enumerate(pairs):
        progress(f"Matching picture and audio {i + 1}/{len(pairs)}…")
        matches.append(match_pair(a, b, features[a["id"]], features[b["id"]]))
    matched = perf_counter()
    components = solve(clips, matches)
    return {"schema": SCHEMA, "engine_version": __version__, "created_utc": datetime.now(timezone.utc).isoformat(),
            "complete_original": False, "absolute_origin_known": False,
            "status": "review_required" if len(components) > 1 or any(c["conflicts"] for c in components) else "relative_timeline",
            "sources": clips, "duplicates": duplicates, "matches": matches, "components": components,
            "warnings": ["Relative coverage only: the original beginning and ending are unknown.",
                         "Evidence scores are uncalibrated, not probabilities.",
                         "Source choice uses nominal pixel dimensions, not measured perceptual quality.",
                         "Prototype: same-rate CFR, >=2s overlap, informative matching picture AND audio required."],
            "timings_seconds": {"probe": probed - started, "decode": decoded - probed,
                                "match": matched - decoded, "total": perf_counter() - started},
            "ffmpeg_version": run([executable("ffmpeg"), "-version"]).decode().splitlines()[0]}
