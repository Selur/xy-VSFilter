#!/usr/bin/env python3
"""Functional tests for the xy-VSFilter VapourSynth interface (API 4).

Usage: python test/test_xyvsfilter.py [path/to/xy-VSFilter.dll]

Without an argument the plugin is expected to be autoloaded (e.g. from the
installed wheel) or to be found in site-packages/vapoursynth/plugins.

Requires the vapoursynth Python module (R55 or newer) and Windows.
"""
import glob
import hashlib
import os
import sys
import tempfile

import vapoursynth as vs

core = vs.core
HERE = os.path.dirname(os.path.abspath(__file__))

ASS = """[Script Info]
ScriptType: v4.00+
PlayResX: 320
PlayResY: 240

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,40,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,2,0,2,10,10,10,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:00:00.00,0:00:01.00,Default,,0,0,0,,Hello
Dialogue: 0,0:00:02.00,0:00:03.00,Default,,0,0,0,,World
"""


def load_plugin(args):
    if args:
        core.std.LoadPlugin(args[0])
        return
    if hasattr(core, "xyvsf"):
        return
    plugin_dir = os.path.join(os.path.dirname(vs.__file__), "plugins")
    for path in glob.glob(os.path.join(plugin_dir, "**", "xy-VSFilter.dll"), recursive=True):
        core.std.LoadPlugin(path)
        return
    raise SystemExit("FAIL: xyvsf plugin is neither autoloaded nor found below " + plugin_dir)


def check(cond, msg):
    if not cond:
        raise SystemExit("FAIL: " + msg)
    print("ok  ", msg)


def expect_error(fn, msg, contains=""):
    try:
        fn()
    except vs.Error as e:
        text = str(e).strip().splitlines()[-1]
        check(contains in text, "%s (%s)" % (msg, text))
    else:
        raise SystemExit("FAIL: no error raised: " + msg)


def digest(clip, n):
    f = clip.get_frame(n)
    h = hashlib.sha1()
    for p in range(clip.format.num_planes):
        h.update(bytes(f[p]))
    return h.hexdigest()


def main():
    load_plugin(sys.argv[1:])
    check(hasattr(core, "xyvsf"), "plugin loaded (namespace xyvsf)")

    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "test.ass")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(ASS)

        # 25 fps: frames 0-24 show "Hello", 25-49 nothing, 50-74 "World".
        for func in ("TextSub", "TextSubLibass"):
            for fmt in (vs.YUV420P8, vs.YUV420P16, vs.RGB24):
                src = core.std.BlankClip(width=320, height=240, format=fmt, length=80, fpsnum=25, fpsden=1)
                out = getattr(core.xyvsf, func)(src, file=path)
                name = "%s %s" % (func, core.get_video_format(fmt).name)
                check(out.format.id == src.format.id and out.num_frames == 80, "%s: format and length kept" % name)
                check(digest(out, 10) != digest(src, 10), "%s: first line rendered" % name)
                check(digest(out, 35) == digest(src, 35), "%s: frame without a dialogue line unchanged" % name)
                check(digest(out, 60) != digest(src, 60), "%s: second line rendered" % name)

        src = core.std.BlankClip(width=720, height=480, format=vs.YUV420P8, length=50, fpsnum=25, fpsden=1)
        out = core.xyvsf.VobSub(src, file=os.path.join(HERE, "31.idx"))
        check(out.num_frames == 50 and out.format.id == src.format.id, "VobSub: 31.idx opens, format and length kept")

        expect_error(lambda: core.xyvsf.TextSub(src.resize.Point(format=vs.YUV444P8), file=path), "YUV444P8 rejected", "only constant format")
        expect_error(lambda: core.xyvsf.TextSub(src, file=os.path.join(tmp, "missing.ass")), "missing subtitle file rejected", "can't open")

    print("all tests passed")


if __name__ == "__main__":
    main()
