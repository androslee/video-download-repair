# Initial prototype results

Measured 2026-10-27 on this Linux workstation. These are development fixtures,
not a production accuracy claim or evidence of Windows desktop compatibility.

## Environment

- Python 3.11.15; NumPy 1.26.4; SciPy 1.17.1; pytest 9.1.1.
- FFmpeg/ffprobe 6.1.1 from Ubuntu's package, extracted locally without a system install.
- Real Blender 4.5.3 LTS `bpy` runtime for adapter tests; no mocked Blender API.
- No local AI model, GPU inference or cloud API used by reconstruction.

## Blind overlap experiment

A 16-second, 24-fps synthetic scene with continuous motion and nonrepeating audio
was encoded into four overlapping clips: [0,7), [4,11), [8,16), [5,9). One exact
duplicate was added. Names/order and filesystem timestamps carry no chronological
hints. The engine sees only `inputs/`; the evaluator reads `truth/` afterward.

The mixed-resolution run uses 320x180, 256x144 and 160x90 inputs. These deliberately
small fixtures establish functional plumbing, not 1080p/4K performance or quality.

| Measurement | Same resolution | Mixed resolution |
|---|---:|---:|
| Reconstructed video | 384 frames / 16 s | 384 frames / 16 s |
| Decoded output audio | 16 s | 16 s |
| Measured global audio offset | 0 ms | 0 ms |
| Audio correlation with reference | 0.9974 | 0.9974 |
| Grayscale proxy mean squared error | 0.00000587 | 0.00000665 |
| Probe + decode | ~0.71 s | ~0.68 s |
| Matching | ~0.023 s | ~0.020 s |
| Entire analysis | ~0.73 s | ~0.70 s |

Timing excludes fixture generation and export and varies by machine/cache. Proxy
MSE is measured on reduced grayscale frames; it is not a full-resolution perceptual
quality metric. Audio was also checked in one-second neighborhoods around every
source switch, not only over the complete output.

## Verification

**22 automated tests passed** in the initial complete run (about 14 seconds), with
exit status 0. They cover:

- Relative offsets, no omitted/duplicated timeline intervals, containment/unique tails.
- Byte-identical duplicate removal and invariance to graph input order.
- Decoded output frame count, timestamps, image content and global/seam audio alignment.
- Repeated-content ambiguity, static/silent evidence and matching-audio/wrong-picture refusal.
- Separate disjoint groups, refusal to render an invented order and contradictory cycles.
- Invalid trim bounds, source changes and refusal to overwrite an output.
- Actual Blender registration, picture/audio trim offsets, new-scene isolation and markers.
- Actual Blender rendered-frame comparisons at the start and later source boundaries.
- Actual Blender operator launching the separate engine, reading its result and cancellation.

The embedded Blender runtime required an explicit shutdown call after render tests
to release its native render caches/threads before Python teardown. The test hook
preserves pytest's exit status; no failures are hidden by that cleanup.

## Not yet established

- Real footage with speech, music, repeated intros, subtitles, watermarks or crops.
- Long-duration performance, memory measurements, fingerprint caching and indexed search.
- Visual-only inference, mixed/VFR timing, shifted audio and clock drift.
- Exact lossless frame/sample equality baseline from Test 0.
- Reliable ordering of non-overlapping scenes or full-original extent detection.
- Perceptual source-quality ranking (currently a nominal-resolution heuristic).
- Full Blender movie/audio export evaluation (CLI A/V export and Blender still
  rendering/strip timing are tested), interactive installation, Windows/macOS or
  Blender versions newer than 4.5.3.

Reproduce with `python -m pytest -q` after installing the test dependencies and
setting FFmpeg paths. Media, reports and receipts belong under ignored `.local/`.

## Shuffler update (0.1.1)

The expanded suite passed **42 tests in 29.27 seconds**, exit status 0, on the
same workstation. It adds real FFmpeg tests of clean/overlapping samples, multiple
resolutions and source frame rates, fractional-frame cut positions, audio alignment,
repeatable plans, anonymous filenames/folders and metadata removal. It also checks
that source files are unchanged, existing output is refused, failed preparation
leaves an incomplete marker, and answer keys/partial datasets cannot be analyzed.

The real Blender operator now loads clips from randomized subfolders through the
external engine. A 125-second silent source checks preparation beyond the engine's
per-clip input limit; it is not a full-length movie performance benchmark.

The shuffler normalizes source frame rates before cutting. This does not establish
that the reconstruction engine can directly accept arbitrary mixed/VFR footage.
The earlier limitations above still apply, including uncertain ordering of clean,
non-overlapping scenes. See [the shuffler guide](SHUFFLER.md) and
[existing tools to compare](RELATED_TOOLS.md).

## Later real-world and reporting checks

The expanded suite passed **50 tests in 34.32 seconds**, exit status 0. It adds
human-readable source reports and an omitted-piece test that produces disconnected
groups without inventing their relative placement.

On the same workstation a user prepared a two-minute clip from six aligned
resolution versions (144p through 1080p), using five seconds of overlap. The engine
found five accepted overlaps and one connected group. All six relative positions
agreed with the shuffler's separate answer key at the report's recorded precision.
Analysis took about 11 seconds on that run; the final MP4 has 120 seconds of video
and stereo audio. The user reported smooth audio during playback. These are results
from one local, user-supplied test, not a held-out benchmark or a universal quality
measurement; its media and private paths are not published here.

The earlier untested list refers to the initial run: this single real-footage
example is now established, but the breadth of speech/music, other content,
independent encodes and conditions listed there still needs systematic testing.
