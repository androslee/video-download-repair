import importlib.util
import sys
import os
import tempfile
from pathlib import Path

import pytest

_blender_profile = None
_original_datafiles = None


def pytest_configure(config):
    global _blender_profile, _original_datafiles
    _original_datafiles = os.environ.get("BLENDER_USER_DATAFILES")
    _blender_profile = tempfile.TemporaryDirectory(prefix="vrl-blender-test-data-")
    os.environ["BLENDER_USER_DATAFILES"] = _blender_profile.name


def pytest_unconfigure(config):
    if _blender_profile is not None:
        _blender_profile.cleanup()
    if _original_datafiles is None:
        os.environ.pop("BLENDER_USER_DATAFILES", None)
    else:
        os.environ["BLENDER_USER_DATAFILES"] = _original_datafiles


def pytest_sessionfinish(session, exitstatus):
    # The embedded bpy runtime needs to release render threads/caches before
    # Python tears down its C++ modules. This does not change pytest's exit status.
    if "bpy" in sys.modules:
        sys.modules["bpy"].ops.wm.quit_blender()


@pytest.fixture(scope="session")
def fixture_factory():
    path = Path(__file__).resolve().parents[1] / "scripts" / "make_fixture.py"
    spec = importlib.util.spec_from_file_location("make_fixture", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.make_fixture


@pytest.fixture(scope="session", params=[False, True], ids=["same-resolution", "mixed-resolution"])
def experiment(request, tmp_path_factory, fixture_factory):
    from video_repair_lab.engine import analyze
    root = tmp_path_factory.mktemp("experiment") / "fixture"
    truth = fixture_factory(root, mixed=request.param)
    # No original/truth is passed to inference.
    report = analyze(root / "inputs")
    return root, truth, report
