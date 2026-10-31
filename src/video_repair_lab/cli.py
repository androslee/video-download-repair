import argparse
import json
from pathlib import Path
import sys

from .engine import analyze
from .media import RepairError
from .render import render
from .shuffler import prepare_shuffle
from .source_report import format_report


def main(argv=None):
    parser = argparse.ArgumentParser(description="Local fragment reconstruction. No AI model or cloud required.")
    commands = parser.add_subparsers(dest="command", required=True)
    a = commands.add_parser("analyze", help="Find supported overlaps and write a reviewable timeline")
    a.add_argument("clips", type=Path)
    a.add_argument("--output", required=True, type=Path)
    a.add_argument("--recursive", action="store_true", help="Read fragments in randomized subfolders")
    r = commands.add_parser("render", help="Render a connected relative timeline to a new MP4")
    r.add_argument("timeline", type=Path)
    r.add_argument("--output", required=True, type=Path)
    r.add_argument("--component", type=int, help="Explicitly export only this unresolved group")
    p = commands.add_parser("report", help="Describe sources used by an existing timeline")
    p.add_argument("timeline", type=Path)
    p.add_argument("--output", required=True, type=Path, help="New text report file")
    p.add_argument("--answer-key", type=Path, help="Optional shuffler truth/manifest.json to identify original sample files")
    s = commands.add_parser("shuffle", help="Cut full local videos into blind clean/overlapping test samples")
    s.add_argument("videos", type=Path, nargs="+", help="Video files and/or folders to scan recursively for aligned copies of the same edit")
    s.add_argument("--output", required=True, type=Path, help="New dataset directory")
    s.add_argument("--exclude", action="append", default=[], metavar="GLOB", help="Skip matching filenames or relative paths during folder discovery; repeat as needed")
    s.add_argument("--mode", choices=("clean", "overlap", "both"), default="both")
    s.add_argument("--min-seconds", dest="minimum", type=float, default=20)
    s.add_argument("--max-seconds", dest="maximum", type=float, default=40)
    s.add_argument("--overlap", type=float, default=5, help="Extend each non-final piece forward by this many seconds")
    s.add_argument("--folders", type=int, default=3)
    s.add_argument("--seed", type=int, help="Repeatable cut positions, anonymous names and folder distribution")
    s.add_argument("--variants", choices=("all", "mixed"), default="all", help="Every cut from every source, or one source per cut")
    s.add_argument("--start", type=float, default=0, help="Start of the common source window, in seconds")
    s.add_argument("--duration", type=float, help="Length of the common source window; default is the full available video")
    s.add_argument("--fps", help="Shared output frame rate, e.g. 24 or 30000/1001; default is first source rate")
    s.add_argument("--cuts", type=float, nargs="+", help="Explicit cut seconds relative to the selected window instead of random lengths")
    s.add_argument("--omit-pieces", type=int, nargs="+", help="Omit these 1-based base piece numbers to simulate missing coverage")
    s.add_argument("--keep-references", action="store_true", help="Keep normalized references under truth/ for evaluation")
    s.add_argument("--dry-run", action="store_true", help="Show sample counts/warnings without encoding or creating output")
    args = parser.parse_args(argv)
    try:
        if args.output.exists():
            raise RepairError("Output already exists. Choose a new path; originals and reports are never overwritten.")
        progress = lambda text: print(text, file=sys.stderr, flush=True)
        if args.command == "shuffle":
            settings = {k: v for k, v in vars(args).items() if k not in ("command", "videos", "output")}
            print(json.dumps(prepare_shuffle(args.videos, args.output, progress=progress, **settings)))
        elif args.command == "analyze":
            source_path = args.output.with_suffix(".sources.txt")
            if source_path.exists():
                raise RepairError(f"Source report already exists: {source_path}. Choose another output name.")
            report = analyze(args.clips, progress=progress, recursive=args.recursive)
            detail = format_report(report)
            args.output.parent.mkdir(parents=True, exist_ok=True)
            with source_path.open("x", encoding="utf-8") as stream:
                stream.write(detail)
            try:
                with args.output.open("x", encoding="utf-8") as stream:
                    json.dump(report, stream, indent=2, allow_nan=False)
            except Exception:
                source_path.unlink(missing_ok=True)
                raise
            print(detail, file=sys.stderr, flush=True)
            print(json.dumps({"timeline": str(args.output.resolve()), "source_report": str(source_path.resolve()), "groups": len(report["components"]),
                              "status": report["status"], "timings_seconds": report["timings_seconds"]}))
        elif args.command == "report":
            report = json.loads(args.timeline.read_text(encoding="utf-8"))
            key = json.loads(args.answer_key.read_text(encoding="utf-8")) if args.answer_key else None
            detail = format_report(report, key)
            args.output.parent.mkdir(parents=True, exist_ok=True)
            with args.output.open("x", encoding="utf-8") as stream:
                stream.write(detail)
            print(detail, file=sys.stderr, flush=True)
            print(json.dumps({"source_report": str(args.output.resolve())}))
        else:
            report = json.loads(args.timeline.read_text(encoding="utf-8"))
            print(format_report(report), file=sys.stderr, flush=True)
            print(json.dumps(render(report, args.output, args.component, progress=progress)))
    except (RepairError, OSError, KeyError, TypeError, json.JSONDecodeError) as exc:
        print(f"Video Repair Lab: {exc}", file=sys.stderr)
        return 2
    return 0
