# Primary sources consulted

Reviewed 2026-10-27. These establish available building blocks, not a working end-to-end assembler or measured performance.

- [FFmpeg signature filter implementation](https://github.com/FFmpeg/FFmpeg/blob/master/libavfilter/vf_signature.c): existing MPEG-7 video signature calculation and sequence lookup. Candidate baseline; cross-resolution and offset accuracy still need our experiments.
- [FFmpeg filters documentation](https://ffmpeg.org/ffmpeg-filters.html): reference for matching, trim, resampling and rendering filters; verify available filters in the selected build during implementation.
- [PySceneDetect detector documentation](https://www.scenedetect.com/docs/latest/api/detectors.html): content, adaptive, histogram, threshold and hash-based shot-change detection. Detecting a change does not determine where an unrelated shot belongs.
- [Chromaprint upstream](https://github.com/acoustid/chromaprint): near-identical audio fingerprinting, with an explicit robustness/search-performance tradeoff. Evaluate short-window use rather than assuming suitability for every sound track. Local library use does not require an AcoustID web lookup.
- [ComfyUI custom node architecture](https://docs.comfy.org/custom-nodes/overview): Python backend nodes and optional frontend extensions support exposing a separate local analysis engine. The proposed workflow requires custom implementation.

- [Blender Sequencer Python API](https://docs.blender.org/api/4.5/bpy.ops.sequencer.html): programmatic video/audio timeline operations. The local adapter is tested against the actual Blender 4.5.3 runtime.
- [Blender extension manifests](https://docs.blender.org/manual/en/latest/advanced/extensions/getting_started.html): extension packaging and metadata reference; desktop install still needs validation.
- [Kdenlive timeline import](https://docs.kdenlive.org/en/user_interface/menu/file_menu.html) and [roadmap](https://kdenlive.org/roadmap/): a possible later OpenTimelineIO bridge; general scripting is on the roadmap.
- [NumPy FFT documentation](https://numpy.org/doc/stable/reference/routines.fft.html): native numerical tools, with SciPy providing the correlation used in this prototype.

The alignment graph, confidence policy, audio/video selection, evaluation protocol
and milestone ordering are this project's design decisions. Consult the measured
prototype results for which parts have been implemented and tested.
