# Video shuffler

`video-repair shuffle` creates blind reconstruction tests from **local full videos**.
It does not download videos, modify your originals, load AI models or contact a
cloud service. Use the Python/FFmpeg setup from the [README](../README.md).

## One video: clean cuts and overlaps

On Linux, `.venv` is a hidden folder: in a file manager press **Ctrl+H** to show
hidden files. Follow the [README setup](../README.md#install-the-independent-engine)
to create it. Open a terminal and enter your project directory first (the commands
below use relative paths):

```bash
cd /path/to/video-repair-lab
.venv/bin/python -m video_repair_lab shuffle --help
```

Replace `/path/to/video-repair-lab` with your actual project directory. The second
command prints the options without processing a video.

Next run this command, replacing `/path/to/full-video.mp4` with the **actual path**
to your video. You can drag a video from your file manager into the terminal to
insert its path. The output folder must not already exist:

```bash
.venv/bin/python -m video_repair_lab shuffle "/path/to/full-video.mp4" \
  --output .local/samples-one \
  --mode both --min-seconds 20 --max-seconds 40 --overlap 5 \
  --folders 3 --seed 42
```

Processing messages appear in the terminal. The output is under
`video-repair-lab/.local/samples-one/`, another hidden folder. If the command
immediately returns, read the error text above the prompt. To retry, use a new
`--output` folder name; a failed run may leave an `INCOMPLETE.txt` marker.

The project looks for FFmpeg on `PATH`, then in the local FFmpeg package under
`.local/tools/ffmpeg-package/usr/bin/` if it exists. Explicit `VRL_FFMPEG` and
`VRL_FFPROBE` environment variables take priority. Other installations must
install FFmpeg or set those variables as described in the README.

Windows PowerShell (one line):

```powershell
.\.venv\Scripts\python.exe -m video_repair_lab shuffle "C:\Videos\full-video.mp4" --output .local\samples-one --mode both --min-seconds 20 --max-seconds 40 --overlap 5 --folders 3 --seed 42
```

This makes two separate tests sharing the same base cut positions:

- **clean:** adjacent pieces, each moment present once, with no gaps or overlap.
- **overlap:** each piece extends forward five seconds into the next piece,
  capped at the end of the video. Unique tails remain present.

“Clean” means non-overlapping chronological intervals. It does **not** automatically
detect shot changes. Use `--cuts` below when you want exact known scene boundaries.

`--min-seconds` and `--max-seconds` set the target random base-piece lengths.
The final piece may be shorter to preserve the entire ending. An overlapping
piece can be up to `max-seconds + overlap` long. Times are snapped to output frames.

## Multiple resolutions of the same video

Put aligned versions of the same video in one folder, then pass the folder:

```bash
.venv/bin/python -m video_repair_lab shuffle "/path/to/video-versions" \
  --output .local/samples-multiple --mode both \
  --min-seconds 20 --max-seconds 40 --overlap 5 --folders 4 --seed 42
```

The folder is searched recursively, including subfolders. Supported video files
are listed in the console before processing; non-video files and symlinks found
within the folder are skipped. Explicitly supplied file paths can be mixed with
folders, and duplicate paths are included only once. Discovery uses a stable
order; the first discovered source supplies the default output frame rate.

Every discovered video is treated as a version of the **same edit**. A folder
containing unrelated videos, previous outputs or other episodes is not suitable.
Use a separate folder, list only the intended files, or skip unwanted discoveries
with `--exclude 'filename.mp4'` (repeatable; shell-style glob patterns supported).
Exclusions apply to folder scans, not files supplied explicitly. Use `--dry-run`
to print the chosen files and planned counts before encoding. The maximum is 32
distinct sources.

You may still list individual files instead:

```bash
.venv/bin/python -m video_repair_lab shuffle \
  "/path/to/video-1080p.mp4" "/path/to/video-720p.mp4" "/path/to/video-360p.mp4" \
  --output .local/samples-multiple --mode both \
  --min-seconds 20 --max-seconds 40 --overlap 5 --folders 4 --seed 42
```

The same cut positions are used for every resolution. By default, `--variants all`
makes each piece from every source and mixes all those files into each test's
random folders. This also tests redundant coverage from multiple sources.

Use **`--variants mixed`** to make only one source version of each base piece,
with source choices balanced and shuffled across the timeline. This produces a
smaller test in which the available resolution changes from piece to piece.
There must be at least as many pieces as input versions in mixed mode.

The sources must be **aligned copies of the same edit**, starting at the same
moment. Different resolutions/frame rates are supported by normalization. Different
introductions, ad insertions or edits are not equivalent copies. Duration mismatch
is checked, but the shuffler does not prove that two similar-length files contain
the same content. Unrelated videos should get separate shuffle runs.

## Start with a short excerpt

For an initial reconstruction test, select two minutes from a longer recording:

```bash
.venv/bin/python -m video_repair_lab shuffle "/path/to/full-video.mp4" \
  --output .local/short-test --start 300 --duration 120 \
  --mode both --min-seconds 20 --max-seconds 30 --overlap 5 --seed 42
```

This selects 05:00–07:00 of each source. The answer key's frame 0 corresponds to
the beginning of the selected window. `--start` and `--duration` apply equally to
all source versions; they are not a tool for aligning independently shifted copies.

Use `--dry-run` with any command to see counts and compatibility warnings before
encoding. It creates no output files. The shuffler can prepare full-length inputs;
the reconstruction prototype still has separate limits of 2–24 input clips,
1–120 seconds each and 20 minutes combined. Large samples are retained for future
engine tests, with warnings. Preparing them does not expand the engine's limits.

## Choose exact boundaries or output frame rate

```bash
.venv/bin/python -m video_repair_lab shuffle "/path/to/video.mp4" \
  --output .local/known-cuts --duration 60 --cuts 10 25 45 \
  --mode both --overlap 3 --fps 30000/1001 --seed 10
```

The clean intervals are [0,10), [10,25), [25,45), [45,60), after snapping to the
chosen frame grid. `--cuts` are relative to the selected window and override the
random-length controls. They must be increasing and strictly inside that window.

By default, output FPS comes from the first source. Each selected source window
is normalized once to that common constant rate before cutting, so independently
cut fragments cannot acquire different resampling phases. This can drop/duplicate
frames when the input rate differs, but keeps playback speed. Each version retains
its displayed pixel dimensions (odd dimensions are rounded down for H.264).

## Simulate a missing section

To make a repeatable two-minute test with a missing middle section:

```bash
.venv/bin/python -m video_repair_lab shuffle "/path/to/video.mp4" \
  --output .local/missing-example --duration 120 \
  --cuts 20 40 60 80 100 --omit-pieces 3 \
  --mode overlap --overlap 5 --seed 42
```

Piece numbers are one-based base intervals: piece 3 is [40,60) in this example.
The preceding piece extends into it by five seconds, so the missing coverage is
approximately [45,60). Omission applies to all supplied versions. Overlapping
neighbors can cover part or even all of an omitted interval; inspect the separate
answer key to evaluate actual coverage. The tool does not infer the gap length:
it returns disconnected groups, which need manual review.

## Where the files go

```text
samples-one/
  clean/inputs/
    set-<random>/clip-<random>.mp4
    set-<random>/clip-<random>.mp4
  overlap/inputs/
    set-<random>/clip-<random>.mp4
    set-<random>/clip-<random>.mp4
  truth/
    manifest.json
    references/                 only with --keep-references
  README.txt
```

Each case's folders are **one distributed input set**. Analyze them together;
an individual random folder is not guaranteed to contain the whole movie.

Names do not encode the source name, resolution or timeline position. Creation
order is shuffled, filesystem modification/access times are normalized, source
metadata/chapters are removed and local playback timestamps start at zero. Original
source IDs, cut positions, seed, file hashes and FFmpeg version stay in the private
`truth/manifest.json`. These steps remove obvious ordering hints; they are not a
forensic anonymization guarantee.

The seed repeats the cut plan, source choices, names and folder distribution for
the same arguments. Encoded bytes are not guaranteed identical across FFmpeg
versions/platforms. A missing seed is randomly generated and recorded in the key.

## Reconstruct the shuffled set

```bash
.venv/bin/python -m video_repair_lab analyze .local/samples-one/overlap/inputs \
  --recursive --output .local/overlap-result.json
```

This command writes a **JSON timeline report** and a readable
`overlap-result.sources.txt` next to it, and prints the source timeline to the
console. The text lists time ranges, input clip paths, source trim times, nominal
resolutions, and other clips that cover some of those ranges. It does not create a
joined video. Check its
`status` and `groups` output: a `relative_timeline` with one group can be
rendered to an MP4 with the following separate command:

```bash
.venv/bin/python -m video_repair_lab render .local/overlap-result.json \
  --output .local/reconstructed.mp4
```

Choose new names for the report and MP4 on later runs; existing files are not
overwritten. If analysis reports `review_required` or multiple groups, the
tool has not determined how to join every clip and will not invent an order.
Inspect the report or review individual groups in Blender. In particular, the
`clean/inputs` set contains **no overlaps**, so the current overlap matcher will
normally leave those clips unplaced. Start with `overlap/inputs` for this test.

To create a readable report from an existing JSON timeline without reanalyzing:

```bash
.venv/bin/python -m video_repair_lab report .local/overlap-result.json \
  --output .local/overlap-sources.txt
```

For shuffler datasets only, add `--answer-key .local/samples-one/truth/manifest.json`
to show which full source file produced each selected fragment. This explicitly
uses the answer key **after** analysis; it must not be used as evidence for
matching. For real-world fragments, the report names the fragment files you supplied.

In Blender, choose that same `overlap/inputs` folder and enable **Search subfolders**
in the updated add-on. Do not select the dataset root or `truth/`: the engine
refuses those answer-key locations. Clean pieces may remain as disconnected groups
because non-overlapping scenes do not necessarily reveal their original order.

## Audio, disk space and failed jobs

Picture and audio use the same time boundaries. Sources without sound stay silent;
no audio is invented. Inputs with multiple audio tracks or significant nonzero/
unequal stream start times currently require preprocessing and produce an error.

Normalization uses H.264 CRF16 and lossless ALAC audio; final samples use H.264
CRF18/AAC192k. Video therefore undergoes two encodes. This is intentional test
preparation, not a lossless archival splitter. Temporary normalized sources need
additional disk space and are removed when preparation ends or fails. With
`--keep-references`, they instead remain under `truth/references` for an evaluator.

The tool checks output frame counts, audio presence/timing and records hashes.
It refuses existing dataset directories and never overwrites originals. An error
or interruption leaves `INCOMPLETE.txt` and no completed answer key; do not use
that partial dataset as a successful test. After a hard process kill, temporary
files may need manual cleanup. Choose a new destination when retrying.
