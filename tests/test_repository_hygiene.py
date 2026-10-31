"""Exercise the staged-index guard, including the reviewed-media exception."""
from pathlib import Path
import shutil
import subprocess
import sys

import pytest


@pytest.mark.skipif(shutil.which('git') is None, reason='git required')
def test_index_checker_blocks_media_and_tampered_example(tmp_path):
    repo = tmp_path / 'repo'
    (repo / 'scripts').mkdir(parents=True)
    script = Path(__file__).resolve().parents[1] / 'scripts' / 'check_repository.py'
    shutil.copy(script, repo / 'scripts' / 'check_repository.py')
    subprocess.run(['git', 'init', '-q', str(repo)], check=True)
    unreviewed = repo / 'private.mp4'
    unreviewed.write_bytes(b'not a video')
    subprocess.run(['git', '-C', str(repo), 'add', '.'], check=True)
    result = subprocess.run([sys.executable, str(repo / 'scripts' / 'check_repository.py')], capture_output=True, text=True)
    assert result.returncode == 1
    assert 'private configuration or media' in result.stderr
    unreviewed.unlink()
    approved_path = repo / 'examples/gamers-nexus-mixed-resolution/reconstructed.mp4'
    approved_path.parent.mkdir(parents=True)
    approved_path.write_bytes(b'replaced media')
    subprocess.run(['git', '-C', str(repo), 'add', '-A'], check=True)
    result = subprocess.run([sys.executable, str(repo / 'scripts' / 'check_repository.py')], capture_output=True, text=True)
    assert result.returncode == 1
    assert 'does not match reviewed hash' in result.stderr
