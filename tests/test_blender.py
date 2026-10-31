"""Exercise actual Blender 4.5 data/API with optional bpy runtime, not a mock."""
import importlib.util
from pathlib import Path
import sys
import time
import shutil

import pytest

bpy = pytest.importorskip("bpy")


@pytest.fixture(scope="module")
def addon():
    path = Path(__file__).resolve().parents[1] / "blender_addon" / "video_repair_lab" / "__init__.py"
    spec = importlib.util.spec_from_file_location("vrl_blender_test", path, submodule_search_locations=[str(path.parent)])
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    module.register()
    yield module
    module.unregister()


def test_import_preserves_video_audio_timing_and_original_scene(experiment, addon):
    _, truth, report = experiment
    original = bpy.context.scene
    scene = addon.import_component(report)
    try:
        assert bpy.context.scene == original
        assert scene.frame_end == truth["duration"] * truth["fps"]
        assert scene.render.fps / scene.render.fps_base == pytest.approx(truth["fps"])
        movies = sorted((s for s in scene.sequence_editor.strips if s.type == "MOVIE"), key=lambda s: s.frame_final_start)
        sounds = sorted((s for s in scene.sequence_editor.strips if s.type == "SOUND"), key=lambda s: s.frame_final_start)
        segments = report["components"][0]["segments"]
        assert len(movies) == len(sounds) == len(segments)
        for movie, sound, segment in zip(movies, sounds, segments):
            assert movie.frame_final_start == sound.frame_final_start == segment["timeline_start_frame"] + 1
            assert movie.frame_final_end == sound.frame_final_end == segment["timeline_end_frame"] + 1
            assert movie.frame_offset_start == sound.frame_offset_start == segment["source_start_frame"]
        assert len(scene.timeline_markers) == len(segments)
        assert scene["vrl_complete_original"] == 0
    finally:
        bpy.data.scenes.remove(scene)


def test_blender_actually_renders_correct_picture(experiment, addon, tmp_path):
    import numpy as np
    from video_repair_lab.media import ffmpeg
    _, truth, report = experiment
    original = bpy.context.window.scene
    scene = addon.import_component(report)
    bpy.context.window.scene = scene
    try:
        scene.render.image_settings.file_format = "PNG"
        for frame in (1, 169, 265):
            scene.frame_set(frame)
            path = tmp_path / f"blender-{frame}.png"
            scene.render.filepath = str(path)
            bpy.ops.render.render(write_still=True, scene=scene.name)
            actual = np.frombuffer(ffmpeg("-i", path, "-vf", "scale=32:18,format=gray", "-frames:v", 1,
                                          "-f", "rawvideo", "pipe:1"), np.uint8).astype(float) / 255
            expected = np.frombuffer(ffmpeg("-ss", (frame - 1) / truth["fps"], "-i", truth["reference"],
                                            "-vf", "scale=32:18,format=gray", "-frames:v", 1,
                                            "-f", "rawvideo", "pipe:1"), np.uint8).astype(float) / 255
            assert len(actual) == len(expected) == 576
            assert float(np.mean((actual - expected) ** 2)) < 0.003
    finally:
        bpy.context.window.scene = original
        bpy.data.scenes.remove(scene)


def test_addon_external_engine_operator(experiment, addon):
    root, _, _ = experiment
    # An actual registered preference record and bpy operator, with a real separate engine process.
    record = bpy.context.preferences.addons.new()
    record.module = addon.__package__
    try:
        record.preferences.engine_python = sys.executable
        nested = root / "nested-inputs" / "random-folder"
        nested.mkdir(parents=True, exist_ok=True)
        for path in (root / "inputs").iterdir():
            shutil.copy2(path, nested / path.name)
        bpy.context.scene.vrl_settings.input_directory = str(nested.parent)
        bpy.context.scene.vrl_settings.recursive = True
        assert bpy.ops.vrl.analyze() == {"FINISHED"}
        deadline = time.monotonic() + 30
        while addon._job is not None and time.monotonic() < deadline:
            addon._poll()
            time.sleep(0.05)
        assert addon._job is None
        settings = bpy.context.scene.vrl_settings
        assert Path(settings.report_path).is_file(), settings.status
        assert "1 group(s)" in settings.status
        # Explicit cancellation must stop the owned engine subprocess.
        assert bpy.ops.vrl.analyze() == {"FINISHED"}
        process = addon._job["process"]
        assert bpy.ops.vrl.cancel() == {"FINISHED"}
        assert process.poll() is not None
    finally:
        addon._stop_job()
        bpy.context.preferences.addons.remove(record)
