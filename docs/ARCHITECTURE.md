# Engine and editor boundary

## Current implementation

```text
Blender sidebar
    | launches a separate local Python process
    v
CLI / engine -> FFmpeg + ffprobe -> NumPy / SciPy matching
    | writes a versioned JSON timeline
    v
Blender adapter -> new scene with trimmed video and sound strips
```

The engine has no Blender imports and no network client. The Blender adapter
has no engine imports and uses only Python's standard library plus Blender's
API. Its subprocess is started without a shell. Analysis can also run headlessly
through the CLI; CLI rendering uses FFmpeg independently of Blender.

The v1 JSON schema stores sources with SHA-256 identities, stream metadata, every
pair's accepted/rejected evidence, and components containing relative positions
and selected intervals. Frame intervals are **zero-based and end-exclusive**.
Blender's one-based timeline is translated at the adapter boundary. Each group
has its own origin; no spacing/order is invented between disconnected groups.

`complete_original` and `absolute_origin_known` remain false. A connected graph
only proves the supported relative coverage, not that the original was complete.

## Why Python first

Python coordinates the work; it does not interpret every pixel/sample in a nested
loop. FFmpeg handles decoding/encoding in native code. NumPy handles array math,
and SciPy performs FFT-based audio correlation in compiled code. Python makes
it inexpensive to adjust algorithms and share contracts with the Blender adapter.

The initial matcher searches all pairs, using normalized audio correlation to
propose offsets, then validates runs of small grayscale frames. It rejects weak
or repeated candidates. Accepted offsets must agree with a common frame grid.
Cycle consistency is checked before building a relative timeline. Selection keeps
each covered time interval once; ties prefer continuity and longer remaining coverage.

Current visual proxies are 32x18 at 8 fps; audio proxies are mono at 8 kHz. The
engine holds these **bounded proxies**, not original high-resolution movies, in
memory. The prototype has explicit duration/clip-count limits. It is not yet a
streaming index for hour-long videos or hundreds of fragments.

## Where Rust could help

A future Rust worker could implement a large fingerprint index, bounded streaming
feature extraction, candidate retrieval or a measured Python-heavy graph/search
bottleneck. The JSON contract permits a separate executable; PyO3 is another
option if direct array sharing becomes necessary. Neither option is implemented.

The first fixture measurements put matching at about 0.02 seconds and probing plus
decoding around 0.7 seconds for four unique short clips. This is a toy benchmark,
but it gives no reason to rewrite the matcher in Rust now. Rust cannot by itself
speed up FFmpeg's existing native decoding or SciPy's existing FFT. First reduce
all-pairs work through indexing/cache and measure real clips; then compare an
isolated Rust implementation with identical correctness tests if justified.

## Local AI later

No model is downloaded or loaded in this prototype. Potential future modules:

- Local speech recognition to compare dialogue around uncertain joins.
- Local visual embeddings to retrieve candidates across heavier transformations.
- Optional scene/narrative descriptions to rank disconnected clips for review.

These are proposed evidence sources, not reliable recovery of unknown chronology.
An AI suggestion must never override a measured conflict or become a claim that
missing footage was recovered. Local models also add RAM/VRAM, installation and
latency costs; they are not needed for the first overlap tests.

## Next work

1. Held-out real clips with speech/music and repeated intros, plus independent encodes.
2. Visual-only alignment and sub-frame refinement, with explicit confidence policy.
3. Persistent fingerprints and an index before increasing clip/duration limits.
4. VFR and different-rate timestamp handling, drift and per-stream A/V offsets.
5. Better source-quality selection, preview comparisons and saved manual decisions.
6. Windows desktop installation and Blender UI checks; then other editor adapters.

ComfyUI is an optional later frontend. Its original planned node graph remains
documented, but Blender is now the first supported editor integration.
