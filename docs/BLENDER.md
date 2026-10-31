# Blender setup

Tested with the real Blender **4.5.3 LTS Python runtime** on Linux, including
registration, the external analysis operator, cancellation, import and rendered
frame comparisons. Interactive desktop usability and Windows installation are
not yet verified. No desktop Blender program was installed on this machine.

## 1. Install the engine separately

Follow the engine installation in [README](../README.md). Confirm that its Python
can run `-m video_repair_lab --help`, and that FFmpeg and ffprobe work. Blender
does not need NumPy/SciPy installed in its own Python environment for this add-on.

## 2. Build and install the extension

Run `python scripts/package_addon.py` from the project. In Blender:

1. Open **Edit → Preferences → Add-ons**.
2. Use the menu's **Install from Disk** and choose
   `.local/dist/video-repair-lab-blender.zip`.
3. Enable **Video Repair Lab** and expand its preferences.
4. Set **Engine Python** to the engine virtual environment's executable:
   - Linux: `/path/to/video-repair-lab/.venv/bin/python`
   - Windows: `C:\path\to\video-repair-lab\.venv\Scripts\python.exe`
5. If FFmpeg isn't on Blender's inherited PATH, set **FFmpeg folder** to the
   directory containing both `ffmpeg` and `ffprobe` (or their `.exe` variants).

No cloud key or local language/vision model is needed. The extension zip contains
only the adapter, manifest and license; the independently installed engine does
the analysis. Installing the zip alone does not install the engine or FFmpeg.

## 3. Reconstruct

1. Open Blender's **Video Editing** workspace.
2. Place the pointer over the Sequencer and press **N** to open its sidebar.
3. Select **Reconstruct → Video Repair Lab**.
4. Choose the folder containing your fragments and click **Analyze Fragments**.
   For video-shuffler samples, select a case's `inputs/` folder and enable
   **Search subfolders**. See the [shuffler guide](SHUFFLER.md).
5. Analysis runs in a separate process. The sidebar offers **Cancel Analysis**.
6. Once complete, the report path and number of overlap-connected groups appear.
7. Select a group (numbering starts at **0**) and click **Import Group into New Scene**.

You can also select a `timeline.json` produced by the CLI and import it directly.
Import creates a fresh scene and switches to it; it does not replace an existing
timeline. Picture is on channel 2 and sound on channel 1. The first marker warns
that original extent is unknown; subsequent markers identify source changes.
Disconnected groups are imported separately. Contradictory groups cannot be imported.

Scrub and listen at every marker. Original media remains untouched. Standard
Blender timeline editing can resolve uncertain order manually. Save your `.blend`
and render through Blender when satisfied. Manual Blender edits are **not yet
exported back to the engine's JSON**, so use Blender's render for an edited timeline.

## Logs and moved files

Engine logs and reports are stored under Blender's user data directory in
`video-repair-lab/analysis-*/`. The sidebar shows the exact log path if analysis
fails. These are individual job outputs, not source or application version folders.

Reports refer to absolute local source paths. Moving source files requires
reanalyzing them. Import verifies source SHA-256 hashes before creating strips;
changed files cannot silently reuse old offsets. Reports can reveal local paths;
keep them local unless you deliberately want to share them.

## FFmpeg setup

Use the FFmpeg and ffprobe binaries installed for your operating system. If they
are not available to Blender through PATH, set the FFmpeg folder in the add-on
preferences as described above. A local package under the project's ignored
`.local/` directory is machine-specific and is not part of this source release.
