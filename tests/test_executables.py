import os

import pytest

from video_repair_lab import media


def executable_file(path):
    path.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    path.chmod(0o755)
    return str(path)


@pytest.mark.skipif(os.name == "nt", reason="Unix executable fixture")
def test_executable_search_priority_and_invalid_override(tmp_path, monkeypatch):
    local = tmp_path / "local"
    system = tmp_path / "system"
    local.mkdir()
    system.mkdir()
    local_binary = executable_file(local / "ffprobe")
    system_binary = executable_file(system / "ffprobe")
    monkeypatch.setattr(media, "LOCAL_FFMPEG_DIR", local)
    monkeypatch.delenv("VRL_FFPROBE", raising=False)
    monkeypatch.setenv("PATH", str(system))
    assert media.executable("ffprobe") == system_binary
    monkeypatch.setenv("PATH", "")
    assert media.executable("ffprobe") == local_binary
    monkeypatch.setenv("VRL_FFPROBE", system_binary)
    assert media.executable("ffprobe") == system_binary
    monkeypatch.setenv("VRL_FFPROBE", str(tmp_path / "missing"))
    with pytest.raises(media.RepairError, match="VRL_FFPROBE"):
        media.executable("ffprobe")
