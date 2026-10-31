"""Blender frontend. Engine runs in the user's separate Python environment."""
import json
import os
from pathlib import Path
import signal
import subprocess
import tempfile

import bpy
from bpy.props import BoolProperty, IntProperty, PointerProperty, StringProperty
from bpy.types import AddonPreferences, Operator, Panel, PropertyGroup

from .timeline_import import import_component

_job = None


class VRLPreferences(AddonPreferences):
    bl_idname = __package__
    engine_python: StringProperty(name="Engine Python", subtype="FILE_PATH",
                                 description="Python executable inside the separate video-repair-lab virtual environment")
    ffmpeg_directory: StringProperty(name="FFmpeg folder (optional)", subtype="DIR_PATH",
                                     description="Folder containing ffmpeg and ffprobe; leave blank to use PATH")

    def draw(self, context):
        self.layout.prop(self, "engine_python")
        self.layout.prop(self, "ffmpeg_directory")


class VRLSettings(PropertyGroup):
    input_directory: StringProperty(name="Fragments folder", subtype="DIR_PATH")
    recursive: BoolProperty(name="Search subfolders", default=False,
                            description="Include shuffled fragments inside the selected inputs folder's subfolders")
    report_path: StringProperty(name="Timeline report", subtype="FILE_PATH")
    component: IntProperty(name="Group (starts at 0)", default=0, min=0)
    status: StringProperty(default="Choose fragments, then Analyze")


def _redraw():
    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            if area.type == "SEQUENCE_EDITOR":
                area.tag_redraw()


def _poll():
    global _job
    if _job is None:
        return None
    job = _job
    code = job["process"].poll()
    if code is None:
        return 0.5
    job["log"].close()
    scene = bpy.data.scenes.get(job["scene"])
    if scene:
        settings = scene.vrl_settings
        if code == 0:
            settings.report_path = str(job["report"])
            try:
                report = json.loads(job["report"].read_text(encoding="utf-8"))
                settings.status = f"{len(report['components'])} group(s). Select a group and Import. Original extent unknown."
            except (OSError, ValueError, KeyError):
                settings.status = "Engine output unreadable. See " + str(job["log_path"])
        else:
            settings.status = "Analysis failed. See " + str(job["log_path"])
    _job = None
    _redraw()
    return None


def _stop_job():
    global _job
    if _job is None:
        return
    process = _job["process"]
    if process.poll() is None:
        if os.name == "nt":
            subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], capture_output=True, timeout=10)
        else:
            # Only the dedicated process group we launched, including its FFmpeg child.
            os.killpg(process.pid, signal.SIGTERM)
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=3)
    _job["log"].close()
    _job = None


class VRL_OT_analyze(Operator):
    bl_idname = "vrl.analyze"
    bl_label = "Analyze Fragments"
    bl_description = "Run local picture/audio matching in the independent engine"

    @classmethod
    def poll(cls, context):
        return _job is None

    def execute(self, context):
        global _job
        prefs = context.preferences.addons[__package__].preferences
        settings = context.scene.vrl_settings
        python = Path(bpy.path.abspath(prefs.engine_python))
        folder = Path(bpy.path.abspath(settings.input_directory))
        if not prefs.engine_python or not python.is_file() or not settings.input_directory or not folder.is_dir():
            self.report({"ERROR"}, "Set Engine Python in add-on preferences and choose a fragments folder")
            return {"CANCELLED"}
        base = bpy.utils.user_resource("DATAFILES", path="video-repair-lab", create=True)
        job_dir = Path(tempfile.mkdtemp(prefix="analysis-", dir=base))
        report_path, log_path = job_dir / "timeline.json", job_dir / "engine.log"
        env = os.environ.copy()
        if prefs.ffmpeg_directory:
            ffdir = Path(bpy.path.abspath(prefs.ffmpeg_directory))
            suffix = ".exe" if os.name == "nt" else ""
            env["VRL_FFMPEG"] = str(ffdir / ("ffmpeg" + suffix))
            env["VRL_FFPROBE"] = str(ffdir / ("ffprobe" + suffix))
        log = log_path.open("wb")
        try:
            command = [str(python), "-m", "video_repair_lab", "analyze", str(folder.resolve()), "--output", str(report_path)]
            if settings.recursive:
                command.append("--recursive")
            process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=log, stderr=log,
                                       env=env, start_new_session=os.name != "nt",
                                       creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0)
        except OSError as exc:
            log.close()
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        _job = {"process": process, "log": log, "report": report_path, "scene": context.scene.name, "log_path": log_path}
        settings.status = "Analyzing locally… Log: " + str(log_path)
        bpy.app.timers.register(_poll, first_interval=0.5)
        return {"FINISHED"}


class VRL_OT_cancel(Operator):
    bl_idname = "vrl.cancel"
    bl_label = "Cancel Analysis"

    def execute(self, context):
        _stop_job()
        if bpy.app.timers.is_registered(_poll):
            bpy.app.timers.unregister(_poll)
        context.scene.vrl_settings.status = "Canceled. Source media unchanged."
        return {"FINISHED"}


class VRL_OT_import(Operator):
    bl_idname = "vrl.import_timeline"
    bl_label = "Import Group into New Scene"
    bl_description = "Create an editable picture/audio timeline; keep disconnected groups separate"

    def execute(self, context):
        settings = context.scene.vrl_settings
        try:
            report = json.loads(Path(bpy.path.abspath(settings.report_path)).read_text(encoding="utf-8"))
            scene = import_component(report, settings.component)
        except (ValueError, OSError, KeyError, TypeError, RuntimeError) as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        scene.vrl_settings.report_path = settings.report_path
        scene.vrl_settings.input_directory = settings.input_directory
        scene.vrl_settings.recursive = settings.recursive
        scene.vrl_settings.component = settings.component
        scene.vrl_settings.status = "Review the source joins before rendering. Original extent unknown."
        context.window.scene = scene
        self.report({"INFO"}, "Imported relative timeline in a new scene")
        return {"FINISHED"}


class VRL_PT_panel(Panel):
    bl_label = "Video Repair Lab"
    bl_idname = "VRL_PT_panel"
    bl_space_type = "SEQUENCE_EDITOR"
    bl_region_type = "UI"
    bl_category = "Reconstruct"

    def draw(self, context):
        layout = self.layout
        settings = context.scene.vrl_settings
        layout.label(text="Local overlap reconstruction (prototype)")
        layout.prop(settings, "input_directory")
        layout.prop(settings, "recursive")
        layout.operator("vrl.analyze", icon="VIEWZOOM")
        if _job is not None:
            layout.operator("vrl.cancel", icon="CANCEL")
        layout.separator()
        layout.prop(settings, "report_path")
        layout.prop(settings, "component")
        layout.operator("vrl.import_timeline", icon="SEQUENCE")
        # Wrapping prevents long paths/status from being inaccessible in a narrow sidebar.
        import textwrap
        for line in textwrap.wrap(settings.status, width=42):
            layout.label(text=line)
        layout.label(text="No automatic order between disconnected groups.")


CLASSES = (VRLPreferences, VRLSettings, VRL_OT_analyze, VRL_OT_cancel, VRL_OT_import, VRL_PT_panel)


def register():
    for cls in CLASSES:
        bpy.utils.register_class(cls)
    bpy.types.Scene.vrl_settings = PointerProperty(type=VRLSettings)


def unregister():
    _stop_job()
    if bpy.app.timers.is_registered(_poll):
        bpy.app.timers.unregister(_poll)
    del bpy.types.Scene.vrl_settings
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)
