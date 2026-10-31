# Related tools and reuse candidates

Reviewed 2026-10-27 against primary project documentation. These tools have not
been installed or benchmarked in this project yet; documented capabilities are
not claims of success on our fragment-reconstruction tests.

| Tool | Documented capability | Potential role here |
|---|---|---|
| [LosslessCut](https://github.com/mifi/lossless-cut) | GUI for cutting/merging media; scene detection; segment import/export | Existing interactive sample-cutting UI. Our shuffler adds repeatable multi-resolution cases, anonymous folder distribution and a hidden answer key. |
| [PySceneDetect](https://www.scenedetect.com/docs/latest/cli.html) | Detect shot changes/fades, export scene lists and split video | Add natural-scene cut points to test preparation instead of writing a new shot detector. Current shuffler uses random or explicit cut positions. |
| [Align](https://github.com/FedyaLight/align) | Local Rust app/CLI; waveform/fingerprint matching, timing metadata, separate groups, cached fingerprints, drift correction and editor exports | Closest complete synchronization application found; candidate external alignment backend and comparison baseline. |
| [AudioAlign / Aurio](https://protyposis.net/projects/audioalign/) | Audio fingerprint overlap discovery, drift refinement, manual timeline inspection and EDL export | Research reference and baseline for overlap alignment/drift. |
| [audalign](https://github.com/benfmiller/audalign) | Python audio fingerprinting/correlation with coarse/fine alignment | Practical library candidate for improving audio matching/caching. Its “visual” recognizer compares audio spectrograms, not video footage. |
| [FFmpeg signature filter](https://github.com/FFmpeg/FFmpeg/blob/master/libavfilter/vf_signature.c) | MPEG-7 visual signatures and matching video segments | Candidate visual matching baseline; already uses our FFmpeg dependency. |

The common existing use case is synchronizing multiple cameras or microphones
recording the same event. Our intended output additionally needs to choose one
usable copy of each interval, retain unique tails, distinguish unknown placement
from known gaps, and avoid inventing an order for disconnected material.

No verified turnkey replacement for that entire combined workflow was established
by this review. That is a search result, not a claim that none exists.

## Comparison plan

1. Feed Align and audalign the same anonymous overlapping fragments that our engine
   receives. Keep the original/reference and answer key available only to the evaluator.
2. Disable source-name/timecode/creation-order inference in the comparison where
   supported: those clues have intentionally been removed from our test samples.
3. Score offset accuracy, missing/duplicated coverage, false matches on repetitions,
   audio drift, time and peak memory, not just whether a timeline was produced.
4. Compare both regular and mixed-resolution cases. Include soundless or conflicting
   audio/video cases to expose the limits of audio-only matching.
5. If an existing backend is better, integrate through a stable data interface and
   keep Blender review, interval selection and our evaluator independent of it.

Align is relevant to the earlier Rust question: it offers an existing Rust
implementation to measure before deciding whether to write one ourselves. Its
language alone does not establish a speed or accuracy advantage.
