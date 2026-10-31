# Public release checklist

This document tracks the proposed **experimental release**, not a
claim that the software can reliably repair all incomplete downloads. Check off
items only with dated evidence; describe limitations in the release notes.

## Already established on one Linux workstation

- [x] Fifty automated tests passed, including synthetic audio/picture overlap,
  mixed resolution, explicit missing pieces, no-overwrite behavior and real
  Blender 4.5.3 Python API tests. See [prototype results](PROTOTYPE_RESULTS.md).
- [x] One user-supplied, 120-second real-world mixed-resolution sample reconstructed
  into a single timeline; six measured offsets agreed with its shuffler answer key.
  This was not a held-out accuracy benchmark. The separately identified Gamers Nexus demonstration is included; other source footage and reports stay local.
- [x] README/setup, test plan, licenses, ignored local outputs and contributor,
  security, change and third-party documentation are present.

## Before publishing the source repository

- [ ] Establish a private vulnerability reporting channel and replace the pending
  text in SECURITY.md with its real address; decide who monitors it.
- [ ] Initialize the intended repository, inspect the exact staged file list,
  scan for secrets and personal paths, and confirm no downloads, `.local/`,
  `.venv/`, unapproved media or Blender project files are included. The reviewed demonstration media is the sole exception. Audit any git
  history as well; ignore rules do not remove data from history.
- [ ] Run the Linux GitHub Actions jobs on the actual repository and fix failures.
  The workflow has been prepared, not yet run on GitHub. No Windows/macOS support
  or interactive Blender check follows from a Linux CI pass.
- [ ] Test a clean installation from the generated wheel and the Blender ZIP,
  review the exact source/binary package contents and recheck third-party licenses.
- [ ] Review source handling, FFmpeg/Blender subprocesses, symlinks/output paths,
  temporary data, untrusted reports and dependency advisories. Record findings;
  no external audit or comprehensive security assessment has been completed.
- [ ] Use a clean Linux desktop to install and play/review/export a Blender timeline;
  document exact Blender and FFmpeg versions. Record other OS support as unverified
  until native checks have actually passed.
- [ ] State the current 2–24 clips, 1–120 seconds each and 1,200 seconds total
  bounds; audio + picture matching, fixed frame rates, and unplaced groups/gaps.
  Do not imply non-overlap ordering, broken-download salvage, subtitle preservation,
  guaranteed original coverage or AI-based reconstruction already works.

## Next correctness and performance experiments

- [ ] Use several unrelated, locally held-out videos with dialogue, music, silence,
  scene changes and repeated intros. Separate threshold tuning from evaluation;
  report correct matches, false matches, refusals, offset error and coverage.
- [ ] Test independently encoded sources, mixed codecs, frame rates, audio rates,
  channel layouts, shifted tracks, crop/letterboxing and differing edits. Unsupported
  inputs must be rejected or marked uncertain, never silently joined incorrectly.
- [ ] Test missing start, middle and end, disconnected groups, repeated scenes and
  clean cuts without overlap. Confirm unknown placement/gap length are labeled as
  unknown; document manual Blender review and whether a user can arrange groups.
- [ ] Verify every join for frame accuracy and local audio continuity, including
  speech and music at boundaries. Listen as well as compare samples. Verify
  subtitle and multichannel handling explicitly; current export does not preserve
  subtitle tracks and downmixes audio to stereo.
- [ ] Measure cold/warm processing time, peak RAM and temporary/output disk use
  on representative 720p, 1080p and 4K inputs, plus inputs at the documented
  limits. Test cancellation, low disk space and interrupted jobs safely.
- [ ] Compare existing tools using the same blind datasets, including false matches
  and missing coverage, not only whether they produced a file. See
  [comparison candidates](RELATED_TOOLS.md).
- [ ] Test corrupt/truncated containers and real incomplete downloads independently
  from playable-clip reconstruction. SABnzbd integration depends on recovery of
  usable fragments and is not implemented.

See [TEST_PLAN.md](../TEST_PLAN.md) for fixtures, scenarios and metrics.
