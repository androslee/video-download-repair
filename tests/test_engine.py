import copy
import json
from pathlib import Path

import numpy as np
import pytest

from video_repair_lab.matching import match_pair
from video_repair_lab.media import AUDIO_RATE, RepairError, decode_features, probe, ffmpeg
from video_repair_lab.render import render
from video_repair_lab.timeline import solve, validate_component


def test_blind_overlap_coverage(experiment):
    root, truth, report = experiment
    (root / "timeline.json").write_text(json.dumps(report, indent=2))
    assert report["status"] == "relative_timeline", report["matches"]
    assert report["complete_original"] is False
    assert len(report["duplicates"]) == 1
    component, sources = validate_component(report, 0, require_connected=True)
    assert component["duration"] == pytest.approx(truth["duration"], abs=1 / truth["fps"])
    for key, offset in component["positions"].items():
        assert offset == pytest.approx(truth["clips"][Path(sources[key]["path"]).name]["start"], abs=0.005)
    cursor = 0
    for segment in component["segments"]:
        source = sources[segment["source_id"]]
        truth_start = truth["clips"][Path(source["path"]).name]["start"]
        assert segment["timeline_start_frame"] == cursor
        assert truth_start * truth["fps"] + segment["source_start_frame"] == cursor
        cursor = segment["timeline_end_frame"]
    assert cursor == truth["duration"] * truth["fps"]
    # Reordering the graph input cannot change recovered relative coordinates.
    reversed_components = solve(list(reversed(report["sources"])), list(reversed(report["matches"])))
    assert reversed_components[0]["positions"] == component["positions"]


def test_render_picture_and_audio(experiment):
    root, truth, report = experiment
    output = root / "reconstructed.mp4"
    receipt = render(report, output)
    assert receipt["frames"] == truth["duration"] * truth["fps"]
    ref_features = decode_features(probe(truth["reference"]))
    out_features = decode_features(probe(output))
    # Evaluate content, not merely a successful mux or stream count.
    mse = float(np.mean((ref_features["pixels"] - out_features["pixels"]) ** 2))
    assert mse < 0.003, mse
    from scipy.signal import correlate, correlation_lags
    ref, out = ref_features["audio"], out_features["audio"]
    corr = correlate(out, ref, method="fft")
    lag = correlation_lags(len(out), len(ref))[np.argmax(corr)]
    assert abs(lag) / AUDIO_RATE <= 0.02
    n = min(len(ref), len(out))
    correlation = float(np.corrcoef(ref[:n], out[:n])[0, 1])
    assert correlation > 0.93, correlation
    # Inspect audio around every source switch independently (global lag can hide a bad join).
    for segment in report["components"][0]["segments"][1:]:
        seam = int(segment["timeline_start_frame"] / truth["fps"] * AUDIO_RATE)
        lo, hi = max(0, seam - AUDIO_RATE // 2), min(n, seam + AUDIO_RATE // 2)
        assert float(np.corrcoef(ref[lo:hi], out[lo:hi])[0, 1]) > 0.90
    (root / "evaluation.json").write_text(json.dumps({**receipt, "video_proxy_mse": mse,
                                                      "audio_correlation": correlation, "audio_lag_ms": lag / AUDIO_RATE * 1000}, indent=2))
    with pytest.raises(RepairError, match="never overwritten"):
        render(report, output)


def test_graph_conflict_and_disconnected(experiment):
    _, _, report = experiment
    clips = report["sources"][:3]
    a, b, c = (clip["id"] for clip in clips)
    edges = [{"a": a, "b": b, "offset": 1, "accepted": True},
             {"a": b, "b": c, "offset": 1, "accepted": True},
             {"a": a, "b": c, "offset": 5, "accepted": True}]
    assert solve(clips, edges)[0]["conflicts"]
    separate = copy.deepcopy(report)
    separate["components"] = solve(clips, [])
    assert len(separate["components"]) == 3
    with pytest.raises(RepairError, match="unresolved relative order"):
        validate_component(separate, 0, require_connected=True)


def test_invalid_timeline_is_refused(experiment):
    _, _, report = experiment
    invalid = copy.deepcopy(report)
    invalid["components"][0]["segments"][0]["source_start_frame"] = -1
    with pytest.raises(RepairError, match="bounds"):
        validate_component(invalid, 0)


def test_repeated_content_is_not_accepted():
    rng = np.random.default_rng(16)
    audio = np.tile(rng.normal(size=AUDIO_RATE * 3).astype(np.float32), 4)
    pixels = np.tile(rng.random((24, 576)).astype(np.float32), (4, 1))
    centered = pixels - pixels.mean(axis=1, keepdims=True)
    feature = {"audio": audio, "pixels": pixels, "video": centered / np.linalg.norm(centered, axis=1, keepdims=True)}
    clip = {"id": "a", "fps": 24, "has_audio": True}
    match = match_pair(clip, {**clip, "id": "b"}, feature, feature)
    assert not match["accepted"]
    assert match["reason"] == "repeated_content_multiple_offsets"


def test_silence_and_still_picture_do_not_anchor():
    pixels = np.zeros((64, 576), dtype=np.float32)
    feature = {"audio": np.zeros(AUDIO_RATE * 8), "pixels": pixels, "video": pixels}
    clip = {"id": "a", "fps": 24, "has_audio": True}
    assert not match_pair(clip, {**clip, "id": "b"}, feature, feature)["accepted"]


def test_matching_audio_with_wrong_picture_is_refused(experiment):
    _, _, report = experiment
    a, b = report["sources"][:2]
    features = decode_features(a)
    wrong = dict(features)
    wrong["video"] = np.random.default_rng(31).normal(size=features["video"].shape)
    match = match_pair(a, b, features, wrong)
    assert not match["accepted"]
    assert match["reason"] == "insufficient_or_conflicting_audio_video_evidence"


def test_disjoint_fragments_remain_unresolved(experiment, tmp_path):
    _, truth, _ = experiment
    from video_repair_lab.engine import analyze
    for name, start in (("right.mp4", 0), ("left.mp4", 10)):
        ffmpeg("-i", truth["reference"], "-ss", start, "-t", 4, "-c:v", "libx264", "-c:a", "aac", "-n", tmp_path / name)
    report = analyze(tmp_path)
    assert len(report["components"]) == 2
    assert report["status"] == "review_required"
    with pytest.raises(RepairError, match="unresolved"):
        render(report, tmp_path / "forbidden.mp4")


def test_changed_source_refused(experiment, tmp_path):
    _, _, report = experiment
    changed = copy.deepcopy(report)
    source_id = report["components"][0]["segments"][0]["source_id"]
    source = next(c for c in changed["sources"] if c["id"] == source_id)
    fake = tmp_path / "changed.mp4"
    fake.write_bytes(b"not the analyzed source")
    source["path"] = str(fake)
    with pytest.raises(RepairError, match="source changed"):
        render(changed, tmp_path / "out.mp4")
