# Video Repair Lab

Reconstruct a reviewable timeline from overlapping, playable video fragments. The
local Python engine matches picture and audio; a separate Blender Video Sequence
Editor add-on imports its results into an editable scene.

**Status: working early prototype, 2026-10-27.** Synthetic same-resolution and
mixed-resolution overlap tests pass. This is not yet a general damaged-download
repair tool. One mixed-resolution real-footage example has been assembled; broader real-world
footage, long recordings and Windows desktop use still need validation. The original beginning/end remain unknown without a reference.

- [Mixed-resolution example](examples/gamers-nexus-mixed-resolution/README.md)
- [Blender setup and use](docs/BLENDER.md)
- [Video shuffler: prepare samples from your own videos](docs/SHUFFLER.md)
- [Existing tools and comparison candidates](docs/RELATED_TOOLS.md)
- [Measured prototype results and limits](docs/PROTOTYPE_RESULTS.md)
- [Release and test checklist](docs/RELEASE_CHECKLIST.md)
- [Contributing](CONTRIBUTING.md), [security](SECURITY.md), [third-party notices](THIRD_PARTY_NOTICES.md)
- [Engine architecture and Python/Rust/AI decision](docs/ARCHITECTURE.md)
- [Longer-term design](DESIGN.md)
- [Experimental test plan](TEST_PLAN.md)
- [Primary sources](SOURCES.md)

## What works now

- Local CLI with no Blender, GPU, AI model, DSH or cloud requirement.
- Video shuffler for full local videos: clean/overlapping cuts, multiple resolutions,
  random folders/names, repeatable seeds and a separate evaluation answer key.
- Shuffler accepts video files or recursively discovers them in input folders.
- FFmpeg/ffprobe probing, constant-frame-rate checks, small grayscale proxies and mono audio.
- FFT audio correlation confirmed against a sequence of visual matches.
- Overlap-connected groups, contradictory-cycle detection and separate unresolved groups.
- Byte-identical duplicate removal and interval selection that keeps unique clip tails.
- Mixed-resolution matching; source selection currently prefers nominal pixel dimensions.
- JSON report with offsets, evidence, source hashes, timings and uncertainty.
- A readable source timeline printed to the console and saved beside each analysis,
  including source clip, time range, resolution and overlapping alternatives.
- MP4 export with trimmed picture/audio, followed by full decode and timing checks.
- Blender add-on with an external engine process, cancellation, new-scene import,
  video/audio tracks and markers at source changes. Originals are never modified.

## Current boundaries

Use **2–24 clips**, each **1–120 seconds**, at most **20 minutes of combined input**.
Automatic matching requires at least **2 seconds of informative overlapping
picture and matching audio**, equal constant frame rates and frame-aligned cuts.
These deliberately small limits bound the first exhaustive pairwise matcher.

Silent/video-only inputs remain available as unplaced clips but cannot yet establish
automatic matches. Variable frame rate, different frame rates, rotated/non-square
pixel media, different A/V start timestamps and multiple audio tracks are refused.
Crops, time stretching, dubs, damaged containers and different edits are unsupported.
Repeated/static content may remain unresolved. Disconnected scenes are never forced
into an invented order. A full original cannot be promised from a continuous fragment.

## Install the independent engine

Install Python 3.11 and FFmpeg (including **ffprobe**). Then, in this project folder:

```bash
python3.11 -m venv .venv
.venv/bin/python -m pip install -r requirements-tested.txt
.venv/bin/python -m pip install -e .
ffmpeg -version
ffprobe -version
```

Windows PowerShell:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-tested.txt
.\.venv\Scripts\python.exe -m pip install -e .
ffmpeg -version
ffprobe -version
```

`requirements-tested.txt` pins the versions measured in the initial Linux tests.
The engine supports Python >=3.11, but those exact dependency pins were tested on
3.11. The optional Blender 4.5 `bpy` test runtime specifically requires 3.11.
Network is needed for initial dependency downloads, not for analysis or rendering.

If FFmpeg is not on PATH, set `VRL_FFMPEG` and `VRL_FFPROBE` to its full executable
paths. A local package in `.local/tools/ffmpeg-package/usr/bin/` is also detected
automatically when present. Blender also has a preference for the folder containing
those executables.

## Analyze and export

Keep only the fragments in the selected input folder. Discovery is non-recursive
unless you pass `--recursive` for the shuffler's randomized subfolders.
Do not put the complete reference video there during a blind reconstruction test.

```bash
.venv/bin/python -m video_repair_lab analyze /path/to/clips --output .local/timeline.json
.venv/bin/python -m video_repair_lab render .local/timeline.json --output .local/reconstructed.mp4
```

Analysis also creates `.local/timeline.sources.txt`. To describe a previously
saved timeline without analyzing again, run:

```bash
.venv/bin/python -m video_repair_lab report .local/timeline.json --output .local/sources.txt
```

To see original filenames for
a shuffler test, add its `--answer-key` path; the answer key is never used to
match clips. See the [shuffler guide](docs/SHUFFLER.md) for an example.

Existing output files are never overwritten; choose a new output name on subsequent
runs. If the clips form multiple unplaced groups, default export refuses to invent
an order. Import the groups separately into Blender, or explicitly export just one:

```bash
.venv/bin/python -m video_repair_lab render .local/timeline.json --component 0 --output .local/group-0.mp4
```

This is a **partial relative sequence**, not a claim to have recovered the whole original.
The first exporter requires audio in every selected source; it will not silently
fill missing sound. Inspect every join before using a reconstruction.

## Try the reproducible demo

For your own downloaded videos, use the new shuffler:

```bash
cd /path/to/video-repair-lab
.venv/bin/python -m video_repair_lab shuffle /path/to/full-video.mp4 --output .local/my-samples --mode both --duration 120 --seed 42
.venv/bin/python -m video_repair_lab analyze .local/my-samples/overlap/inputs --recursive --output .local/my-result.json
```

Replace both example paths with your actual project directory and video. `.venv`
and `.local` are hidden directories; most Linux file managers show them with
Ctrl+H. The example selects 120 seconds, so omit `--duration 120` to use the full
video. Each `--output` must be a new path.

See the [shuffler guide](docs/SHUFFLER.md) for multiple resolutions, exact cuts,
overlap and clip-length settings, deliberately missing sections, full-video runs
and Windows commands.

No downloaded video is required. The fixture generator creates anonymous fragments
and places the reference and answer key in a separate `truth/` folder.

```bash
.venv/bin/python scripts/make_fixture.py .local/demo --mixed
.venv/bin/python -m video_repair_lab analyze .local/demo/inputs --output .local/demo/timeline.json
.venv/bin/python -m video_repair_lab render .local/demo/timeline.json --output .local/demo/reconstructed.mp4
.venv/bin/python scripts/package_addon.py
```

Install `.local/dist/video-repair-lab-blender.zip` in Blender 4.5 LTS or newer using
**Preferences → Add-ons → menu → Install from Disk**. See [Blender setup](docs/BLENDER.md).
Only Blender 4.5.3 has been tested; newer versions are not yet verified.

## Development checks

```bash
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python -m pytest -q
```

The optional `bpy` package is large. For engine-only development, install `pytest`
instead; Blender tests skip when `bpy` is unavailable. Tests create their own tiny
media and never need YouTube or a network. `scripts/create_blender_demo.py` can save
a `.blend` from a report when the optional `bpy` runtime is installed.

## Project layout

```text
src/video_repair_lab/           independent engine + CLI
blender_addon/video_repair_lab/ stdlib-only Blender frontend
scripts/                       fixture, packaging and demo tools
tests/                         blind engine tests + real Blender API tests
docs/                          setup, architecture and measured scope
examples/                      reviewed reconstruction example
.local/                        ignored media, reports, packages and local tools
```

The engine and project scripts use the MIT license. The Blender add-on has its own
GPL-3.0-or-later license. Third-party dependencies and the Gamers Nexus example footage have their own rights;
the project code license does not apply to that footage. No FFmpeg or Blender
binaries are part of the add-on package.
