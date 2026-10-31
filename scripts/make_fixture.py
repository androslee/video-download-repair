"""Create local blind inputs and a separate evaluator truth file. No online media."""
import argparse
import json
from pathlib import Path
import random
import wave

import numpy as np

from video_repair_lab.media import ffmpeg


def make_fixture(root, mixed=False):
    root = Path(root)
    root.mkdir(parents=True, exist_ok=False)
    inputs, truth_dir = root / "inputs", root / "truth"
    inputs.mkdir()
    truth_dir.mkdir()
    fps, duration, w, h, rate = 24, 16, 320, 180, 48000
    yy, xx = np.mgrid[0:h, 0:w]
    raw = truth_dir / "picture.rgb"
    with raw.open("wb") as stream:
        for frame in range(fps * duration):
            t = frame / fps
            # Textured motion, crossing objects and changing light; no frame number/timecode.
            channels = [80 + 45 * np.sin(xx / (13 + c * 3) + yy / 23 + t * (0.7 + c * 0.13)) for c in range(3)]
            image = np.stack(channels, axis=-1)
            for k in range(5):
                cx = (40 + k * 59 + t * (13 + k * 4)) % w
                cy = 30 + k * 25 + 19 * np.sin(t * (0.3 + k * 0.17))
                mask = (xx - cx) ** 2 + (yy - cy) ** 2 < (12 + k * 3) ** 2
                image[mask] = [(k * 61 + 91) % 256, (k * 93 + 180) % 256, (k * 47 + 51) % 256]
            stream.write(np.clip(image, 0, 255).astype(np.uint8).tobytes())
    rng = np.random.default_rng(813)
    t = np.arange(duration * rate) / rate
    # Nonrepeating audio; intentionally no speech/real-footage robustness claim.
    noise = rng.normal(size=len(t))
    noise = np.convolve(noise, np.ones(5) / 5, mode="same")
    sound = 0.22 * np.sin(2 * np.pi * (180 * t + 13 * t * t)) + 0.21 * noise
    sound += 0.12 * np.sin(2 * np.pi * (390 * t + 0.7 * t ** 3))
    audio = truth_dir / "sound.wav"
    with wave.open(str(audio), "wb") as wav:
        wav.setparams((1, 2, rate, 0, "NONE", "not compressed"))
        wav.writeframes((np.clip(sound, -1, 1) * 28000).astype("<i2").tobytes())
    reference = truth_dir / "reference.mkv"
    ffmpeg("-f", "rawvideo", "-pixel_format", "rgb24", "-video_size", f"{w}x{h}", "-framerate", fps,
           "-i", raw, "-i", audio, "-c:v", "libx264", "-preset", "fast", "-crf", 0,
           "-pix_fmt", "yuv420p", "-c:a", "pcm_s16le", "-map_metadata", "-1", "-n", reference)
    raw.unlink()
    audio.unlink()
    cuts = [(0, 7), (4, 11), (8, 16), (5, 9)]
    names = ["c8d4", "a2e9", "f7b1", "d5a3"]
    random.Random(61).shuffle(names)
    manifest = {}
    for i, ((start, end), name) in enumerate(zip(cuts, names)):
        width, height = [(320, 180), (256, 144), (160, 90), (320, 180)][i] if mixed else (320, 180)
        path = inputs / f"{name}.mp4"
        ffmpeg("-i", reference, "-ss", start, "-t", end - start, "-vf", f"scale={width}:{height}",
               "-c:v", "libx264", "-preset", "fast", "-crf", "18", "-c:a", "aac", "-b:a", "128k",
               "-map_metadata", "-1", "-n", path)
        manifest[path.name] = {"start": start, "end": end}
    # A byte-identical copy must be removed by identity, independent of matching.
    first = inputs / f"{names[0]}.mp4"
    (inputs / "b0e6.mp4").write_bytes(first.read_bytes())
    manifest["b0e6.mp4"] = dict(manifest[first.name])
    # Filesystem creation/modification timestamps cannot reveal original positions.
    import os
    for path in inputs.iterdir():
        os.utime(path, (1700000000, 1700000000))
    truth = {"fps": fps, "duration": duration, "clips": manifest, "reference": str(reference.resolve()),
             "fixture": "synthetic-motion-and-nonrepeating-audio", "mixed_resolution": mixed}
    (truth_dir / "manifest.json").write_text(json.dumps(truth, indent=2))
    return truth


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--mixed", action="store_true")
    args = parser.parse_args()
    make_fixture(args.directory, args.mixed)
    print(args.directory / "inputs")
