"""Create an installable Blender extension zip without vendoring the engine."""
from pathlib import Path
import zipfile

root = Path(__file__).resolve().parents[1]
source = root / "blender_addon" / "video_repair_lab"
destination = root / ".local" / "dist" / "video-repair-lab-blender.zip"
destination.parent.mkdir(parents=True, exist_ok=True)
with zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED) as archive:
    for path in sorted(source.iterdir()):
        if path.suffix in (".py", ".toml") or path.name == "LICENSE":
            archive.write(path, path.name)
print(destination)
