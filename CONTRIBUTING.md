# Contributing

Video Repair Lab is an early prototype. Start with the [README](README.md),
[test plan](TEST_PLAN.md), and [release checklist](docs/RELEASE_CHECKLIST.md).
Explain the behavior being changed and report the OS, Python and FFmpeg versions
and the commands you ran. Keep unrelated work separate.

## Development checks

Install Python 3.11 and FFmpeg/ffprobe. From the project directory:

```bash
python3.11 -m venv .venv
.venv/bin/python -m pip install -e . pytest
.venv/bin/python -m pytest -q
python scripts/check_repository.py
```

The Blender tests skip when `bpy` is missing. To exercise them, install
`requirements-dev.txt`; it includes the large, optional Blender Python runtime.
The regular tests generate their own short synthetic media and use no cloud or
real downloads. The `bpy` test does not replace interactive desktop checks.
The repository check inspects tracked/staged files, not ignored files or git
history. It catches common mistakes; it is not a complete secrets scanner.

Keep personal video, downloaded media, generated reports, file paths, credentials,
virtual environments and Blender projects out of contributions. Use synthetic or
appropriately licensed fixtures, keep the answer key separate from inference, and
record uncertainty and failing cases as well as successes. Verify dependency and
license provenance before contributing code or fixtures from another project.

Before opening an issue about a potential vulnerability, see [SECURITY.md](SECURITY.md).
