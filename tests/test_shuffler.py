import json
from pathlib import Path
import subprocess
import sys
import shutil

import numpy as np
import pytest

from video_repair_lab.engine import analyze
from video_repair_lab.media import RepairError, digest, ffmpeg
from video_repair_lab.shuffler import discover_sources, plan_shuffle, prepare_shuffle


@pytest.fixture(scope="module")
def shuffle_sources(tmp_path_factory, fixture_factory):
    root = tmp_path_factory.mktemp("shuffle-sources")
    truth = fixture_factory(root / "fixture")
    first = Path(truth["reference"])
    second = root / "lower resolution with spaces.mp4"
    ffmpeg("-i", first, "-vf", "scale=160:90,fps=30", "-c:v", "libx264", "-c:a", "aac", "-n", second)
    return first, second


@pytest.fixture(scope="module", params=[False, True], ids=["single-video", "resolution-copies"])
def shuffled(request, shuffle_sources, tmp_path_factory):
    sources = list(shuffle_sources if request.param else shuffle_sources[:1])
    before = [digest(p) for p in sources]
    output = tmp_path_factory.mktemp("shuffled") / "dataset"
    result = prepare_shuffle(sources, output, mode="both", cuts=[4, 8, 12], overlap=2,
                             seed=22, folders=3, keep_references=True)
    assert before == [digest(p) for p in sources]
    manifest = json.loads((output / "truth/manifest.json").read_text())
    return output, result, manifest


def test_distribution_coverage_and_blind_metadata(shuffled):
    root, result, manifest = shuffled
    assert manifest["complete"] is True
    assert not (root / "INCOMPLETE.txt").exists()
    assert not list(root.glob(".preparing-*"))
    assert manifest["fps"] == "24"
    for mode, pieces in manifest["cases"].items():
        actual = list((root / mode / "inputs").rglob("*.mp4"))
        assert len(actual) == len(pieces) == 4 * len(manifest["sources"])
        assert len({p.parent for p in actual}) == 3
        assert not list((root / mode / "inputs").rglob("*.json"))
        assert {p.stat().st_mtime for p in actual} == {1700000000}
        assert all(p.name.startswith("clip-") and p.parent.name.startswith("set-") for p in actual)
        # The hidden key reconstructs coverage exactly for every source version.
        for source in range(len(manifest["sources"])):
            ordered = sorted((p for p in pieces if p["source"] == source), key=lambda p: p["start_frame"])
            assert ordered[0]["start_frame"] == 0 and ordered[-1]["end_frame"] == 384
            for a, b in zip(ordered, ordered[1:]):
                assert a["end_frame"] - b["start_frame"] == (48 if mode == "overlap" else 0)
        for piece in pieces:
            assert digest(root / piece["file"]) == piece["sha256"]


def _picture(path):
    return np.frombuffer(ffmpeg("-i", path, "-an", "-vf", "scale=32:18,format=gray", "-f", "rawvideo", "pipe:1"), np.uint8).reshape(-1, 576).astype(float) / 255


def _audio(path):
    return np.frombuffer(ffmpeg("-i", path, "-vn", "-ac", 1, "-ar", 8000, "-f", "f32le", "pipe:1"), "<f4")


def test_actual_picture_and_audio_trims_match_answer_key(shuffled):
    root, _, manifest = shuffled
    references = {i: (_picture(root / s["reference_file"]), _audio(root / s["reference_file"])) for i, s in enumerate(manifest["sources"])}
    # The evaluator uses the key; inference never receives it.
    for pieces in manifest["cases"].values():
        for piece in pieces:
            video, audio = references[piece["source"]]
            a, b = piece["start_frame"], piece["end_frame"]
            actual_video = _picture(root / piece["file"])
            assert actual_video.shape == video[a:b].shape
            assert float(np.mean((actual_video - video[a:b]) ** 2)) < 0.0002
            actual_audio = _audio(root / piece["file"])
            lo, hi = round(a / 24 * 8000), round(b / 24 * 8000)
            expected = audio[lo:hi]
            assert abs(len(actual_audio) - len(expected)) / 8000 < 0.05
            n = min(len(actual_audio), len(expected))
            assert np.corrcoef(actual_audio[:n], expected[:n])[0, 1] > 0.97


def test_shuffled_subfolders_feed_reconstruction(shuffled):
    root, _, manifest = shuffled
    result = analyze(root / "overlap/inputs", recursive=True)
    assert result["status"] == "relative_timeline", result["matches"]
    assert len(result["components"]) == 1
    assert result["components"][0]["duration"] == pytest.approx(16)
    answer = {str((root / p["file"]).resolve()): p for p in manifest["cases"]["overlap"]}
    for source in result["sources"]:
        offset = result["components"][0]["positions"][source["id"]]
        assert offset == pytest.approx(answer[source["path"]]["start_frame"] / 24, abs=0.005)
    with pytest.raises(RepairError, match="inputs"):
        analyze(root, recursive=True)
    with pytest.raises(RepairError, match="evaluation"):
        analyze(root / "truth/references", recursive=True)


def test_seed_and_mixed_selection(shuffle_sources):
    options = dict(mode="both", minimum=3, maximum=5, seed=21, variants="mixed")
    one = plan_shuffle(shuffle_sources, **options)
    two = plan_shuffle(shuffle_sources, **options)
    assert one == two
    assert {p["source"] for p in one["cases"]["clean"]} == {0, 1}
    assert len(one["cases"]["clean"]) == len(one["cuts_frames"]) - 1
    assert one["cuts_frames"][-1] == 384
    different = plan_shuffle(shuffle_sources, **{**options, "seed": 22})
    assert one["cases"] != different["cases"]


@pytest.mark.parametrize("options", [dict(minimum=0), dict(overlap=-1), dict(folders=0),
                                         dict(cuts=[8, 4]), dict(cuts=[float("nan")]), dict(fps="0/0"), dict(start=20)])
def test_invalid_requests_do_not_create_output(shuffle_sources, tmp_path, options):
    with pytest.raises(RepairError):
        prepare_shuffle(shuffle_sources, tmp_path / "absent", **options)
    assert not (tmp_path / "absent").exists()


def test_cli_dry_run_and_no_overwrite(shuffle_sources, tmp_path):
    output = tmp_path / "preview"
    command = [sys.executable, "-m", "video_repair_lab", "shuffle", str(shuffle_sources[0]),
               "--output", str(output), "--min-seconds", "3", "--max-seconds", "5", "--seed", "9", "--dry-run"]
    result = subprocess.run(command, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["dry_run"]
    assert not output.exists()
    output.mkdir()
    sentinel = output / "mine.txt"
    sentinel.write_text("keep")
    result = subprocess.run(command, capture_output=True, text=True)
    assert result.returncode == 2
    assert sentinel.read_text() == "keep"


def test_failure_is_marked_and_temporary_reference_removed(shuffle_sources, tmp_path, monkeypatch):
    from video_repair_lab import shuffler
    def fail(*args, **kwargs):
        raise RepairError("simulated encoder failure")
    monkeypatch.setattr(shuffler, "ffmpeg", fail)
    output = tmp_path / "failed"
    with pytest.raises(RepairError, match="encoder failure"):
        prepare_shuffle(shuffle_sources[:1], output)
    assert (output / "INCOMPLETE.txt").exists()
    assert not (output / "truth/manifest.json").exists()
    assert not list(output.glob(".preparing-*"))


def test_long_source_selected_window_and_silent_input(tmp_path):
    source = tmp_path / "long.mp4"
    ffmpeg("-f", "lavfi", "-i", "testsrc2=size=64x36:rate=24:duration=125", "-c:v", "libx264", "-preset", "ultrafast", "-an", "-n", source)
    output = tmp_path / "samples"
    prepare_shuffle([source], output, start=120, duration=5, mode="clean", cuts=[2], seed=9)
    manifest = json.loads((output / "truth/manifest.json").read_text())
    assert manifest["duration_seconds"] == 5
    assert manifest["start_seconds"] == 120
    assert all(not p["encoded"]["has_audio"] for p in manifest["cases"]["clean"])


def test_fractional_frame_grid_and_noninteger_cut_times(shuffle_sources, tmp_path):
    from fractions import Fraction
    output = tmp_path / "fractional"
    prepare_shuffle(shuffle_sources[:1], output, start=1.2, duration=8, fps="30000/1001",
                    cuts=[1.13, 3.71, 6.2], overlap=0.65, mode="both", seed=5, keep_references=True)
    manifest = json.loads((output / "truth/manifest.json").read_text())
    rate = float(Fraction(manifest["fps"]))
    reference = output / manifest["sources"][0]["reference_file"]
    video, audio = _picture(reference), _audio(reference)
    for pieces in manifest["cases"].values():
        for piece in pieces:
            a, b = piece["start_frame"], piece["end_frame"]
            actual = _picture(output / piece["file"])
            assert len(actual) == b - a
            # Exact alignment must beat either neighboring frame; a loose image
            # threshold alone can miss a one-frame seek error in smooth motion.
            errors = {delta: np.mean((actual - video[a + delta:b + delta]) ** 2)
                      for delta in (-1, 0, 1) if a + delta >= 0 and b + delta <= len(video)}
            assert min(errors, key=errors.get) == 0, errors
            actual_audio = _audio(output / piece["file"])
            expected = audio[round(a / rate * 8000):round(b / rate * 8000)]
            n = min(len(actual_audio), len(expected))
            assert np.corrcoef(actual_audio[:n], expected[:n])[0, 1] > 0.97


def test_partial_dataset_inputs_are_refused(shuffle_sources, tmp_path):
    root = tmp_path / "unfinished"
    inputs = root / "overlap/inputs"
    inputs.mkdir(parents=True)
    (root / "INCOMPLETE.txt").write_text("stopped")
    with pytest.raises(RepairError, match="incomplete"):
        analyze(inputs, recursive=True)


def test_source_titles_and_timecode_do_not_leak(shuffle_sources, tmp_path):
    from video_repair_lab.media import executable, run
    source = tmp_path / "with-tags.mp4"
    ffmpeg("-i", shuffle_sources[0], "-t", 5, "-c:v", "copy", "-c:a", "aac",
           "-metadata", "title=Secret original chronology", "-metadata:s:v:0", "title=Secret original chronology",
           "-timecode", "12:34:56:00", "-n", source)
    output = tmp_path / "stripped"
    prepare_shuffle([source], output, mode="clean", cuts=[2], seed=11)
    for path in (output / "clean/inputs").rglob("*.mp4"):
        metadata = run([executable("ffprobe"), "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)]).decode()
        assert "Secret original chronology" not in metadata
        assert "12:34:56" not in metadata


def test_deliberately_missing_interval_stays_unplaced(shuffle_sources, tmp_path):
    root = tmp_path / "missing"
    prepare_shuffle(shuffle_sources[:1], root, mode="overlap", cuts=[4, 8, 12],
                    overlap=2, omit_pieces=[2], seed=4)
    manifest = json.loads((root / "truth/manifest.json").read_text())
    assert manifest["omitted_pieces"] == [2]
    intervals = sorted((j["start_frame"], j["end_frame"]) for j in manifest["cases"]["overlap"])
    assert intervals == [(0, 144), (192, 336), (288, 384)]
    report = analyze(root / "overlap/inputs", recursive=True)
    assert report["status"] == "review_required"
    assert len(report["components"]) == 2
    assert len(report["components"][0]["positions"]) in (1, 2)
    from video_repair_lab.render import render
    with pytest.raises(RepairError, match="unresolved"):
        render(report, tmp_path / "must-not-guess.mp4")
    with pytest.raises(RepairError, match="piece numbers"):
        plan_shuffle(shuffle_sources[:1], cuts=[4, 8, 12], omit_pieces=[5])


def test_folder_input_discovers_nested_versions_and_shuffles(shuffle_sources, tmp_path):
    root = tmp_path / "source files"
    nested = root / "lower resolution"
    nested.mkdir(parents=True)
    first = root / "first.mkv"
    second = nested / "second.MP4"
    shutil.copy2(shuffle_sources[0], first)
    shutil.copy2(shuffle_sources[1], second)
    (root / "notes.txt").write_text("not a video")
    output = tmp_path / "dataset"
    progress = []
    result = prepare_shuffle([root], output, mode="overlap", cuts=[4, 8, 12],
                             overlap=2, seed=8, variants="mixed", progress=progress.append)
    manifest = json.loads((output / "truth/manifest.json").read_text())
    assert [s["path"] for s in manifest["sources"]] == [str(first.resolve()), str(second.resolve())]
    assert {j["source"] for j in manifest["cases"]["overlap"]} == {0, 1}
    assert result["counts"]["overlap"] == 4
    assert str(first.resolve()) in "\n".join(progress) and str(second.resolve()) in "\n".join(progress)
    assert analyze(output / "overlap/inputs", recursive=True)["status"] == "relative_timeline"


def test_folder_discovery_preview_exclusion_and_duplicates(shuffle_sources, tmp_path):
    root = tmp_path / "inputs"
    root.mkdir()
    for name, source in (("a.mkv", shuffle_sources[0]), ("skip.mp4", shuffle_sources[1])):
        shutil.copy2(source, root / name)
    command = [sys.executable, "-m", "video_repair_lab", "shuffle", str(root), str(root / "a.mkv"),
               "--exclude", "skip.*", "--output", str(tmp_path / "not-created"), "--dry-run"]
    result = subprocess.run(command, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["sources"] == [str((root / "a.mkv").resolve())]
    assert "Found 1 source video(s)" in result.stderr
    assert not (tmp_path / "not-created").exists()
    # Explicit files can be added even when a folder exclusion matches them.
    assert discover_sources([root, root / "skip.mp4"], exclude=["skip.*"]) == [
        (root / "a.mkv").resolve(), (root / "skip.mp4").resolve()]
    with pytest.raises(RepairError, match="No supported video"):
        discover_sources([root], exclude=["*"])


def test_folder_discovery_skips_symlinks_and_limits_count(tmp_path):
    root = tmp_path / "inputs"
    root.mkdir()
    target = root / "original.mp4"
    target.write_bytes(b"fixture")
    try:
        (root / "alias.mp4").symlink_to(target)
        (root / "cycle").symlink_to(root, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("Symlinks unavailable on this platform")
    assert discover_sources([root]) == [target.resolve()]
    for i in range(32):
        (root / f"clip-{i}.mp4").write_bytes(b"fixture")
    with pytest.raises(RepairError, match="more than 32"):
        discover_sources([root])
