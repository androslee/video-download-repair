import json
import subprocess
import sys
from pathlib import Path

import pytest

from video_repair_lab.media import RepairError
from video_repair_lab.source_report import format_report


def test_report_shows_correct_sources_trims_and_alternatives(experiment, tmp_path):
    _, _, report = experiment
    detail = format_report(report)
    component = report["components"][0]
    sources = {s["id"]: s for s in report["sources"]}
    for segment in component["segments"]:
        source = sources[segment["source_id"]]
        assert source["path"] in detail
        assert f"{source['width']}x{source['height']}" in detail
    assert "Clip time:" in detail
    assert "Alternative" in detail
    assert "Original source:" not in detail

    timeline = tmp_path / "timeline.json"
    timeline.write_text(json.dumps(report))
    output = tmp_path / "sources.txt"
    command = [sys.executable, "-m", "video_repair_lab", "report", str(timeline), "--output", str(output)]
    result = subprocess.run(command, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert output.read_text() == detail
    assert detail in result.stderr
    assert json.loads(result.stdout)["source_report"] == str(output)
    result = subprocess.run(command, capture_output=True, text=True)
    assert result.returncode == 2
    assert output.read_text() == detail


def test_answer_key_mapping_is_explicit(experiment):
    _, _, report = experiment
    selected = report["components"][0]["segments"][0]["source_id"]
    source = next(s for s in report["sources"] if s["id"] == selected)
    key = {"schema": "video-repair-lab.shuffle.v1", "complete": True,
           "sources": [{"path": "/original/full-video.mkv"}],
           "cases": {"overlap": [{"source": 0, "sha256": source["id"]}]}}
    detail = format_report(report, key)
    assert "/original/full-video.mkv" in detail
    assert "not inferred by matching" in detail
    with pytest.raises(RepairError, match="completed"):
        format_report(report, {})


def test_analysis_writes_and_prints_source_report(experiment, tmp_path):
    root, _, _ = experiment
    output = tmp_path / "new-timeline.json"
    cmd = [sys.executable, "-m", "video_repair_lab", "analyze", str(root / "inputs"), "--output", str(output)]
    result = subprocess.run(cmd, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    summary = json.loads(result.stdout)
    report = json.loads(output.read_text())
    detail = Path(summary["source_report"]).read_text()
    assert detail == format_report(report)
    assert detail in result.stderr
