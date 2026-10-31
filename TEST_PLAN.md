# Technical experiments

Status: initial synthetic overlap experiments executed; see
[prototype results](docs/PROTOTYPE_RESULTS.md). The broader targets below remain
provisional engineering gates, not claims that all cases have passed.

## Benchmark integrity

A fixture generator receives the complete reference and creates cut/transcoded inputs plus a truth manifest. The assembler receives only the anonymous clip directory and declared mode/settings. The evaluator alone sees the original video, source-to-reference time mappings, cut boundaries and intended order. Keep those processes and paths separate.

Shuffle input enumeration; give clips random names; strip absolute source timecodes, ordering comments and metadata hints; normalize filesystem timestamps. Keep local stream timestamps needed for decoding but reset absolute reference offsets. Do not burn source frame numbers into blind test images. Re-run with different names/order to expose accidental ordering leaks. Record seeds, FFmpeg build/commands and hashes so fixtures are reproducible.

Use at least three content types: continuous camera motion with speech, a multi-scene edited video, and repeated/low-information material. Establish development fixtures and separate held-out fixtures; tune thresholds only on development data. Begin with 60-180 seconds, then 10-30 minutes once the short tests pass. A user-selected downloaded YouTube video can be a local reference; downloading is separate from inference. Test independently encoded copies later so the benchmark does not only measure artifacts of our own splitter.

## User-requested experiments

| Test | Input | What it should establish | Correct handling of uncertainty |
|---|---|---|---|
| 1a | Same-resolution, adjacent non-overlapping chunks cut inside continuous shots; shuffled | Whether motion/audio continuity can rank neighboring chunks | Low confidence or review where boundaries are indistinct |
| 1b | Same-resolution, non-overlapping clips cut exactly at independent scene boundaries; shuffled | Limits of order inference without shared content | Do not require guessed order to be confidently accepted; show unresolved alternatives |
| 2 | Same-resolution overlapping segments; shuffle; include fully contained and exact duplicate clips | Offset recovery, deduplication and retention of unique tails | Repeated-content collisions must be flagged |
| 3 | Repeat 1a/1b with 360p/480p/720p/1080p encodes of available source resolution | Cross-resolution continuity and ambiguity behavior | A larger frame size alone cannot justify confidence |
| 4 | Repeat 2 at mixed resolutions/bitrates | Cross-resolution overlap matching and quality selection | Unsupported crops/edits or conflicting matches require review |

All four families include synchronized audio. Preserve test numbering, but implement the easier overlap tests 2 and 4 before ambitious disjoint ordering in 1 and 3.

## Test 0: establish rendering and evaluation

Use a supplied correct timeline, lossless video/PCM audio fixtures and exactly known boundaries to validate trim, timestamps, concatenation and muxing. This is the sole explicitly truth-assisted pipeline test. Require exact expected frame/sample counts and no accidental A/V shift. Then introduce lossy video/AAC and evaluate decoded content/alignment rather than encoded byte equality. Codec delay/padding must not be counted as recovered source content.

## Overlap fixture details

For a longer fixture, A=[0,600), B=[480,900), C=[540,660), D=[840,1200) seconds.
Expected coverage is [0,1200) with each original moment once. B's tail and D's tail must survive; C is redundant unless it offers a preferable source interval. Short initial fixtures use the same pattern scaled to their duration.

Vary overlap span (approximately 0.5, 2, 5 and 15 seconds where duration permits), contained duplicates, three-way overlaps and clip count. Unknown short overlaps may be refused; refusal and false acceptance are separate metrics. A single common black frame or repeated music phrase cannot count as a positive anchor.

## Additional cases before calling it reliable

- Shared audio with different picture encodes; shared picture with silent or missing audio.
- Stereo/mono, 44.1/48 kHz, different audio compression, encoder delay and leading silence.
- A deliberate A/V shift and gradual audio-clock drift; estimate and report them rather than applying arbitrary time stretching.
- Speech crossing a seam; interrupted music; applause; silence; repeated soundtrack sections.
- Repeated shot/intro, credits, still slides and black frames: reject incorrect duplicate removal.
- Missing middle interval, missing start/end and disconnected components: distinguish known gaps from unknown placement. Do not assert full original coverage without an anchored extent.
- Mixed 24/25/30/60 fps and variable-rate clips; same playback speed versus intentional speed change tested separately.
- Letterboxing, mild crop, watermark, color/compression changes, held-out independently encoded sources.
- Different-language audio or a different edit sharing some scenes: keep incompatible tracks/versions distinct.
- Unreadable/truncated containers and decode failures: explicit failure or salvageable ranges, never fabricated success.

## Measurement and initial gates

- **Overlap precision/recall:** evaluate proposed aligned spans against truth. For controlled supported fixtures, require no falsely accepted overlap and full expected coverage. Broader acceptance targets are chosen only after held-out results; zero observed errors is not a universal guarantee.
- **Relative timing:** report coarse and refined offset error. Initial supported constant-rate target is <=1 output frame at each accepted video join; measure audio residual separately, targeting <=20 ms and no accumulating drift beyond 20 ms over a 10-minute fixture. These are targets, not established capabilities.
- **Coverage:** compare recovered source-time intervals to truth; report omitted and duplicated duration independently. Fully covered controlled overlaps should contain each intended interval once, within measured boundary tolerance.
- **Order:** adjacent-pair accuracy and complete-order accuracy. Score suggested and auto-accepted joins separately. Ambiguous/underdetermined cases should be explicitly unresolved, not included as confident successes.
- **Audio:** word/transient continuity, no doubled sound, gap duration, local alignment, long-run drift and channel continuity. Include listening checks at every seam in addition to numerical checks.
- **Picture quality:** compare rendered frames to time-aligned reference frames; record which source was chosen and quality loss. Report scaling separately from true recovered detail. SSIM/PSNR are evaluation aids, not sole correspondence evidence.
- **Export validity:** decode the entire output, check monotonic timestamps, expected duration, frame/sample counts and seam neighborhoods. Plain successful muxing is insufficient.
- **Performance:** wall time and peak memory for indexing, candidate search, refinement and render; cold-cache and warm-cache runs separately. No speed promise until measured.

Save a machine-readable report, timeline, accepted/rejected evidence, tool versions and short seam previews under `.local/experiments/<stable-test-name>/`. Keep test media and generated reports out of source control. Public documentation should summarize both successes and failures.

## First implementation acceptance

A short same-resolution overlap dataset must reconstruct the recoverable video and audio once each, match the hidden truth at declared tolerances, and correctly refuse an ambiguous repeated-content case. Only then proceed to mixed resolution and Blender integration. A manual timeline smoke test alone does not satisfy this gate.

## Implemented prototype tests

The general-purpose `video-repair shuffle` command now prepares user-provided
full videos and aligned resolution variants. See [the shuffler guide](docs/SHUFFLER.md).
It supports clean/overlapping/both modes, shared frame-grid normalization, random
folders/names, repeatable seeds, explicit cuts and a separate truth manifest.
Inference consumes only the case's `inputs/` tree with `--recursive`.

Shuffler tests verify decoded video/audio against the private normalized reference,
coverage and unique tails, fractional-frame cuts, frame-rate/resolution variants,
long-source excerpt preparation, dry runs, failure marking and no-overwrite behavior.

`scripts/make_fixture.py` builds a 16-second synthetic moving scene with
nonrepeating sound and four anonymous overlapping fragments plus a byte-identical
duplicate. The original and truth manifest stay outside the input directory.
The suite repeats with mixed resolutions, measures picture/audio content and seams,
checks repeat-content refusal, wrong-picture/shared-audio refusal, contradictory
cycles, disconnected groups and changed-source rejection. Blender tests exercise
the real 4.5.3 API, operator subprocess/cancellation, trim bounds and rendered frames.

These are development fixtures, not held-out real-world accuracy measurements.
Run `python -m pytest -q`; media are generated locally. Install the optional `bpy`
test dependency to exercise Blender; otherwise those tests explicitly skip.
