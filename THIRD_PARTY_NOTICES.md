# Third-party software and licenses

The source project uses external dependencies; their copyrights and licenses
remain with their authors. No FFmpeg, Blender or third-party model binaries are
included in the Blender add-on package. Installing Python dependencies obtains
their own distribution files and notices.

| Software | Role | License information |
|---|---|---|
| [NumPy](https://numpy.org/) | Python engine numerical operations | BSD-3-Clause; see its distribution notices. |
| [SciPy](https://scipy.org/) | Python engine signal processing | BSD-3-Clause; see its distribution notices and bundled library notices. |
| [pytest](https://docs.pytest.org/) | Development tests | MIT. |
| [Blender / bpy](https://www.blender.org/) | Optional editing and adapter tests | GPL; the tested `bpy` 4.5.3 distribution declares GPL-3.0. Consult the exact distribution's notices. |
| [FFmpeg](https://ffmpeg.org/legal.html) | User-installed media tools | LGPL or GPL depending on build configuration; consult the exact build's notices. |

The engine and project scripts are MIT-licensed; the separately distributed
Blender add-on is GPL-3.0-or-later. See [LICENSE](LICENSE) and the add-on's
[license](blender_addon/video_repair_lab/LICENSE). Gamers Nexus footage in the example remains subject to the original creator’s
rights and is not licensed under these software licenses. This inventory must be
rechecked against exact dependencies and artifacts before redistributing binaries.
