# Mixed-resolution reconstruction example

This is a 120-second reconstruction from six overlapping, playable fragments of
one Gamers Nexus video, encoded at 144p, 240p, 360p, 480p, 720p and 1080p. The
input clips total approximately 31 MiB, and `reconstructed.mp4` is approximately
63 MiB. The fragments were created from aligned copies of the same edit; this is
a demonstration, not an independent accuracy benchmark or a recovered full video.

**Footage:** Gamers Nexus, “Own Everything & Be Happy, Ep. 1 | DIY Router Guide”,
[original video](https://www.youtube.com/watch?v=sJidlu3pPb4). Footage and audio
are third-party material; the project's code licenses do not grant rights to it.
Attribution by itself does not establish permission for further redistribution.

To analyze the shuffled inputs and render your own result from the repository root:

```bash
.venv/bin/python -m video_repair_lab analyze examples/gamers-nexus-mixed-resolution/inputs --output .local/example-timeline.json
.venv/bin/python -m video_repair_lab render .local/example-timeline.json --output .local/example-render.mp4
```

The filenames are content hashes rather than chronology. Analysis and render require
FFmpeg, ffprobe and the engine dependencies described in the main README. The
input directory contains just the six fragments, no complete source downloads;
the prepared reconstruction is outside it. The `.local/` output paths must not
already exist. Generated timelines contain machine-local absolute paths and should
be inspected before sharing.
