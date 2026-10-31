# Design

Date: 2026-10-27. This document describes the broader target architecture. A bounded
Python/FFmpeg prototype and separate Blender add-on now exist; see
[measured scope](docs/PROTOTYPE_RESULTS.md) for what has actually been tested.

## Scope and assumptions

The initial problem is assembling playable excerpts from the same underlying edit. Container repair of an unplayable partial MP4, reconstruction from arbitrary download byte ranges, missing codec initialization data, damaged frames, different cuts of a film, and regenerated missing footage are separate problems. Probe inputs first and report undecodable files rather than treating them as empty videos.

Start with Linux and Windows. Keep the engine usable without Blender, ComfyUI, DSH, cloud APIs or GPU models. Blender's Video Sequence Editor is the first visual interface; ComfyUI is now an optional later adapter. Acquisition is a separate optional step: the assembler consumes local files and does not need to know where they were downloaded.

## Evidence hierarchy

1. Verified visual sequence matches and audio matches establish overlap and relative offsets.
2. Trusted supplied reference/timecode can anchor otherwise disconnected clips, but this is an explicitly separate reference-assisted mode.
3. Motion continuity, audio continuity, speech transcription and narrative similarity can rank non-overlapping neighbors. These are weaker clues and cannot guarantee an original edit.
4. If evidence is ambiguous or contradictory, retain alternatives and request a placement decision. Never force all clips into one confident order.

Scene boundaries are useful for previews, candidate indexing and selecting clean edit points. They do not themselves reveal scene order. Whole-clip similarity is insufficient: match repeated sequences and local offsets, not a single similar frame. Repeated intros, credits, black frames, silence, music loops and shot/reverse-shot editing are explicit confounders.

## Proposed processing pipeline

### 1. Probe and index

Use ffprobe for streams, timestamps, dimensions, rotation, sample aspect ratio, frame rate, audio channel layout and sample rate. Record a content hash, decoder health and input identity. Interpret presentation timestamps; do not assume `frame number / nominal FPS` represents variable-rate material. Keep external identifiers out of blind benchmark inference.

### 2. Make inexpensive analysis copies

Stream reduced-resolution grayscale frames at a configurable sample rate, preserving timestamp mappings. Normalize rotation/aspect ratio and identify borders. Decode a mono, consistently resampled audio proxy while retaining original audio for output. Cache fingerprints by content hash, parameters and tool version. Do not load a long video as one giant ComfyUI image batch or keep it all in VRAM.

Initial candidates: perceptual frame hashes or FFmpeg MPEG-7 signatures for picture; short-window spectral features/audio landmarks for sound. Evaluate Chromaprint as an additional retrieval baseline for near-identical recordings; it is not assumed to solve short speech-only overlaps or exact cut alignment. Candidate retrieval must be followed by temporal verification.

### 3. Align overlapping sequences

Find matching runs of several frames/audio windows, then refine proposed offsets at native timestamps near a seam. Require agreement over a span, not one frame or one audio peak. Initially assume an offset-only relation between clips. Later allow a small fitted time-scale change and local residual checks for clock drift, frame-rate conversions or changed playback speed; different edits require piecewise alignment or refusal.

Use audio-only and video-only evidence when one channel is unavailable, with separate confidence and explicit reduced support. Conflicting sound and image must not silently resolve to a confident match. Downweighted low-information windows cannot anchor a timeline alone.

### 4. Solve timeline components

Represent each verified overlap as an edge carrying matched intervals, offset/time scale, residual, evidence type and competing matches. Check consistency around cycles and reject conflicting edges. An overlap-connected group has a relative timeline; its absolute start is unknown unless anchored. Keep disconnected groups separate until a user or trusted reference orders them. Do not invent durations for gaps between unanchored groups.

Store scores as uncalibrated evidence scores until measured on held-out data. A probability percentage requires calibration. Report distinct states such as verified overlap, suggested neighbor, unresolved component and known gap.

### 5. Select unique coverage and quality

Resolve intervals on the common timeline. For each covered interval, choose a usable source based on decode health, actual detail/compression damage, dimensions, frame cadence and continuity. Pixel dimensions alone do not prove quality; an upscaled file can be worse.

Example: A covers 00:00-10:00 and B covers 08:00-15:00. Preserve A through 10:00 and B's unique 10:00-15:00 portion, or use B earlier where its quality is better. Never discard the whole B clip because its beginning overlaps. A fully contained C clip can be omitted unless it provides better picture or sound.

Avoid unnecessary source switching. The renderer must not duplicate or drop content merely to make a visually attractive transition. A fixed output resolution is an export choice; lower-resolution source regions remain lower-detail even when enlarged.

### 6. Handle audio independently on the same timeline

Audio is both alignment evidence and output content. Preserve source A/V timing. Use decoded-audio correlation for fine alignment after coarse matching, handling encoder delay/padding and leading silence. Frame-accurate video alignment and audio-sample alignment have separate tolerances.

Prefer a continuous original audio track when available and validated. Otherwise choose contiguous audio intervals from the best synchronized source. Do not mix overlapping copies: that can produce echo, comb filtering and doubled speech. Permit a very short crossfade only inside genuinely aligned overlap, with a plain-cut baseline; never use a crossfade to hide an unmeasured gap or missing word. Detect drift over time. Do not combine different languages/dubs/commentaries as if they were interchangeable.

If an interval has picture but no sound, report an audio gap. If it has sound but no picture, report a video gap. Retain a single-channel recovery option and explicit user export policy for gaps; default verified export requires a resolved timeline. Incomplete preview exports must be labeled and their missing coverage recorded, never disguised as the original complete movie.

### 7. Review, then render

Export a timeline JSON containing source IDs, per-stream source in/out times, output times, time transforms, selected quality, seam evidence, uncertainty, gaps and decisions. Provide side-by-side seam previews with sound and a small timeline visualization. Support manual anchors, reorder, source preference and rejection; modifications invalidate affected validation.

Decode/trim/re-encode for the first accurate baseline. Packet stream copy is a later optimization only for compatible streams and valid packet/keyframe cuts; arbitrary MP4 concatenation is not the design. Normalize export codec, frame cadence, pixel format, canvas and audio format. Preserve known A/V offsets. Decode the finished output and validate timestamps, duration, seam neighborhoods and audio continuity.

## First editor integration: Blender

The initial add-on launches the independent engine as an external process and
imports its versioned JSON report. Each connected group gets a new Blender scene
with synchronized picture/audio strips and source-change markers. It supports
canceling analysis and importing existing reports. Original files and existing
scenes remain intact. This adapter has been exercised with Blender 4.5.3's real
Python runtime; interactive Linux/Windows installation is a further verification step.

Longer-term review work includes side-by-side comparisons, source preferences,
explicit manual anchors and writing Blender decisions back to the engine. Current
manual timeline changes stay in Blender's project and use Blender's own renderer.

## Optional later ComfyUI nodes

These are node specifications, not existing installed nodes or a ready workflow:

`Load Clip Set -> Probe/Index -> Find Audio + Video Matches -> Solve Timeline -> Review Timeline -> Render Assembly -> Validate Output`

Pass file/cache handles, an evidence table and a timeline object between nodes. Preview only selected frames/short clips. Persist results so an interrupted ComfyUI session can resume. A review decision can be saved as a timeline file for headless/API runs rather than requiring a live UI interaction inside a backend node. Pin a supported ComfyUI API version when implementation begins.

Optional local AI nodes can propose scene descriptions, transcript continuity or candidate order for disconnected groups. They cannot override measured overlap conflicts or label invented material as recovered. Generative interpolation/inpainting and speech synthesis are outside the initial recovery pipeline.

## Performance strategy

Use coarse-to-fine matching and an index to reduce candidate comparisons; compare adjacent short windows at full quality only after coarse retrieval. Record indexing time, alignment time, render time, peak RAM/VRAM and cache size separately. Use bounded queues and streaming decode. Start on CPU; add GPU acceleration only when benchmarks identify a benefit. Video downloads and first dependency/model acquisition need network access, but reconstruction is designed to work offline afterward.

## Milestones

1. **Fixture/evaluator foundation:** reproducible cuts, hidden truth, anonymous inputs, version/seed records, input probing, timeline format and a manual-timeline render. Prove audio/video are rendered accurately before evaluating inference.
2. **Overlap reconstruction:** same-resolution overlapping clips, duplicate/contained clip handling, audio and picture offsets, ambiguity refusal, reconstruction and objective comparison. First real proof of feasibility.
3. **Mixed-quality reconstruction:** resolution/codec changes, source selection, then frame-rate differences and mild crop/border changes; measure each change separately.
4. **Disjoint ordering and review:** boundary continuity proposals, disconnected components, manual anchors, optional local speech/vision inference, and deliberately impossible ordering cases.
5. **Blender integration:** a separate add-on wrapping the engine, new-scene import, Windows/Linux setup, cancellation, bounded previews and saved review decisions. Initial operator/import/cancellation implemented; full review UX and desktop verification pending. ComfyUI remains an optional later adapter.
6. **Real-source robustness:** independent encodes/downloads, decoder damage, repeated scenes, music/silence, long clips and partial coverage. Publish supported scope and failures along with benchmark results.

First deliverable achieved on short synthetic same-resolution and mixed-resolution
fixtures: blind overlap analysis, report, A/V render and hidden-reference scoring.
This does not complete all gates in milestones 1–3: exact lossless baseline,
held-out real footage, longer inputs, drift and frame-rate variation remain pending.
No claim that every shuffled movie can be uniquely reconstructed.
