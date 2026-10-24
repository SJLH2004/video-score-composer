#!/usr/bin/env python
"""End-to-end self-test.

Renders the bundled example score, validates the audio, checks determinism, and
(if ffmpeg is available) generates a synthetic video and runs the rhythm scan on
it. No network access, no binary fixtures.

Usage:
    python selftest.py
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import wave

import numpy as np

ROOT = os.path.dirname(os.path.abspath(__file__))
SCAN = os.path.join(ROOT, "scripts", "rhythm_scan.py")
RENDER = os.path.join(ROOT, "scripts", "score_engine.py")
EXAMPLE = os.path.join(ROOT, "assets", "example_arrangement.json")

SR = 48000

failures = []


def check(name, fn):
    try:
        fn()
    except Exception as exc:  # noqa: BLE001 - report, never abort the suite
        failures.append(name)
        print("  FAIL  %s" % name)
        print("        %s" % exc)
    else:
        print("  PASS  %s" % name)


def require(cond, msg):
    if not cond:
        raise AssertionError(msg)


def run(cmd, **kwargs):
    proc = subprocess.run(cmd, capture_output=True, text=True, **kwargs)
    if proc.returncode != 0:
        raise AssertionError(
            "command failed: %s\n%s%s" % (" ".join(cmd), proc.stdout, proc.stderr)
        )
    return proc.stdout


def render(arrangement, out_wav):
    run([sys.executable, RENDER, arrangement, out_wav])
    return out_wav


def read_wav(path):
    with wave.open(path, "rb") as w:
        params = {
            "channels": w.getnchannels(),
            "width": w.getsampwidth(),
            "rate": w.getframerate(),
            "frames": w.getnframes(),
        }
        raw = w.readframes(w.getnframes())
    data = np.frombuffer(raw, dtype=np.int16)
    return params, data


def main():
    tmp = tempfile.mkdtemp(prefix="vsc-selftest-")
    try:
        _run_suite(tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print()
    total = 0
    if failures:
        print("FAILED %d check(s): %s" % (len(failures), ", ".join(failures)))
        return 1
    print("all checks passed")
    return 0


def _run_suite(tmp):
    print("video-score-composer self-test")
    print()

    wav_a = os.path.join(tmp, "score_a.wav")
    wav_b = os.path.join(tmp, "score_b.wav")

    state = {}

    def t_schema():
        with open(EXAMPLE, encoding="utf-8") as f:
            arr = json.load(f)
        for key in ("duration", "chords", "events"):
            require(key in arr, "example arrangement is missing %r" % key)
        require(arr["duration"] == 12.0, "example duration should be 12.0 s")
        require(len(arr["events"]) > 50, "example should exercise many events")
        state["arr"] = arr
        state["example"] = EXAMPLE

    def t_render():
        render(state["example"], wav_a)
        params, data = read_wav(wav_a)
        require(params["channels"] == 2, "expected stereo output")
        require(params["width"] == 2, "expected 16-bit output")
        require(params["rate"] == SR, "expected %d Hz" % SR)
        duration = params["frames"] / float(params["rate"])
        require(abs(duration - 12.0) < 0.05, "expected 12.0 s, got %.3f s" % duration)

        float_data = data.astype(np.float32) / 32768.0
        peak = float(np.abs(float_data).max())
        rms = float(np.sqrt((float_data ** 2).mean()))
        require(peak > 0.5, "output is too quiet (peak %.3f)" % peak)
        require(peak <= 1.0, "output clips (peak %.3f)" % peak)
        require(rms > 0.005, "output is silent (rms %.5f)" % rms)

        # stereo image must actually differ, not a mono file duplicated
        left, right = float_data[0::2], float_data[1::2]
        require(np.abs(left - right).mean() > 1e-4, "left and right are identical")

    def t_determinism():
        render(state["example"], wav_b)
        with open(wav_a, "rb") as fa, open(wav_b, "rb") as fb:
            require(fa.read() == fb.read(), "same seed must produce identical audio")

    def t_scan():
        ffmpeg = shutil.which("ffmpeg")
        if not ffmpeg:
            print("  SKIP  rhythm scan (ffmpeg not on PATH)")
            return
        video = os.path.join(tmp, "pattern.mp4")
        run([
            ffmpeg, "-y", "-v", "error",
            "-f", "lavfi", "-i", "testsrc2=size=320x180:rate=25:duration=6",
            "-c:v", "mpeg4", "-q:v", "4", "-pix_fmt", "yuv420p", video,
        ])
        out_json = os.path.join(tmp, "rhythm.json")
        run([sys.executable, SCAN, video, "--out", out_json])
        with open(out_json, encoding="utf-8") as f:
            rhythm = json.load(f)
        for key in ("meta", "action_peaks", "static_windows",
                    "scene_boundaries", "suggested_bpm"):
            require(key in rhythm, "rhythm map is missing %r" % key)
        require(rhythm["meta"]["frames"] > 100, "scan found too few frames")
        require(abs(rhythm["meta"]["duration"] - 6.0) < 0.3,
                "scan duration %.2f != 6.0" % rhythm["meta"]["duration"])
        require(len(rhythm["action_peaks"]) > 0, "scan found no action peaks")
        require(len(rhythm["suggested_bpm"]) > 0, "scan suggested no tempo")

    check("example arrangement is valid", t_schema)
    check("render produces valid 12 s stereo audio", t_render)
    check("render is deterministic for a fixed seed", t_determinism)
    check("rhythm scan produces a usable map", t_scan)


if __name__ == "__main__":
    sys.exit(main())
