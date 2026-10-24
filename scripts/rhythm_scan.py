#!/usr/bin/env python
"""Scan a video and emit a machine-readable rhythm map.

Extracts every frame at low resolution, then derives:
  - brightness curve   -> hard section boundaries (scene / background changes)
  - frame-to-frame diff-> action peaks (when something actually moves)
  - static windows     -> where the picture holds still (leave space in the score)
  - suggested BPM      -> the tempo whose bar lines best fit the section boundaries

Usage:
    python rhythm_scan.py <video> [--out rhythm.json] [--workdir DIR] [--peak-z 1.6]

Requires: ffmpeg/ffprobe on PATH, numpy, pillow.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys

import numpy as np
from PIL import Image


def run(cmd):
    p = subprocess.run(cmd, capture_output=True)
    if p.returncode != 0:
        sys.stderr.write(p.stderr.decode("utf-8", "replace"))
        raise SystemExit("command failed: %s" % " ".join(cmd))
    return p.stdout.decode("utf-8", "replace")


def probe(path):
    out = run(["ffprobe", "-v", "error", "-show_entries",
               "stream=codec_type,width,height,r_frame_rate,nb_frames,duration",
               "-of", "json", path])
    st = json.loads(out)["streams"]
    v = next(s for s in st if s["codec_type"] == "video")
    num, den = v["r_frame_rate"].split("/")
    fps = float(num) / float(den) if float(den) else 25.0
    dur = float(v.get("duration") or 0)
    nf = int(v.get("nb_frames") or round(dur * fps))
    has_audio = any(s["codec_type"] == "audio" for s in st)
    return {"width": v["width"], "height": v["height"], "fps": fps,
            "duration": dur, "frames": nf, "has_audio": has_audio}


def extract(path, workdir, scale=320):
    gray = os.path.join(workdir, "g")
    rgb = os.path.join(workdir, "c")
    for d in (gray, rgb):
        shutil.rmtree(d, ignore_errors=True)
        os.makedirs(d)
    run(["ffmpeg", "-y", "-v", "error", "-i", path,
         "-vf", "scale=%d:-1,format=gray" % scale,
         os.path.join(gray, "g_%05d.png")])
    run(["ffmpeg", "-y", "-v", "error", "-i", path,
         "-vf", "scale=%d:-1" % scale,
         os.path.join(rgb, "c_%05d.png")])
    return sorted(os.listdir(gray)), sorted(os.listdir(rgb))


def load_gray(dirpath, names):
    return [np.asarray(Image.open(os.path.join(dirpath, n)), dtype=np.float32)
            for n in names]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("--out", default="rhythm.json")
    ap.add_argument("--workdir", default=None)
    ap.add_argument("--peak-z", type=float, default=1.6)
    ap.add_argument("--static-eps", type=float, default=0.06)
    args = ap.parse_args()

    meta = probe(args.video)
    fps, nf = meta["fps"], meta["frames"]
    workdir = args.workdir or os.path.join(os.path.dirname(os.path.abspath(args.out)), "_frames")
    os.makedirs(workdir, exist_ok=True)

    gray_names, rgb_names = extract(args.video, workdir)
    frames = load_gray(os.path.join(workdir, "g"), gray_names)
    if not frames:
        raise SystemExit("no frames extracted")
    nf = len(frames)
    meta["frames"] = nf
    meta["duration"] = nf / fps

    bright = np.array([f.mean() for f in frames])
    diff = np.abs(np.diff(np.array(frames), axis=0)).mean(axis=(1, 2))
    k = np.ones(3) / 3
    ds = np.convolve(diff, k, mode="same")

    thr = ds.mean() + args.peak_z * ds.std()
    peaks = []
    i = 1
    while i < len(ds) - 1:
        if ds[i] > thr and ds[i] >= ds[i - 1] and ds[i] >= ds[i + 1]:
            lo, hi = max(0, i - 8), min(len(ds), i + 9)
            if ds[i] >= ds[lo:hi].max():
                t = (i + 1) / fps
                if not peaks or t - peaks[-1]["t"] > 0.16:
                    peaks.append({"t": round(t, 3), "strength": round(float(ds[i]), 3)})
                i += 9
                continue
        i += 1

    # static windows: consecutive frames with essentially no change
    still = diff < args.static_eps
    statics, s = [], None
    for idx, flag in enumerate(still):
        if flag and s is None:
            s = idx
        elif not flag and s is not None:
            if (idx - s) / fps >= 0.30:
                statics.append({"start": round(s / fps, 2), "end": round(idx / fps, 2)})
            s = None
    if s is not None and (len(still) - s) / fps >= 0.30:
        statics.append({"start": round(s / fps, 2), "end": round(len(still) / fps, 2)})

    # section boundaries: sliding-window brightness step (robust to slow fades
    # and to alpha-heavy renders where a single-frame delta stays small)
    w = max(3, int(round(0.4 * fps)))
    hot = [False] * len(bright)
    for i in range(w, len(bright) - w):
        hot[i] = abs(float(bright[i:i + w].mean() - bright[i - w:i].mean())) > 5.0
    segs, cur = [], None
    for i, h in enumerate(hot):
        if h:
            cur = [i, i] if cur is None else [cur[0], i]
        elif cur is not None:
            if (cur[1] - cur[0]) / fps >= 0.08:
                segs.append(cur)
            cur = None
    if cur is not None:
        segs.append(cur)
    # the START of a transition is where the music cue belongs; the END is where
    # the new picture settles (a second cue often lands there)
    merged = [{"t": round(s[0] / fps, 2), "end": round(s[1] / fps, 2)} for s in segs]

    # tempo candidates: prefer a tempo where the whole piece is a whole number
    # of bars AND the boundaries land near bar lines. Treat the output as a
    # shortlist to choose from, never as an automatic answer.
    bounds = [m["t"] for m in merged]
    cand = []
    for bpm in range(70, 151):
        bar = 240.0 / bpm
        bars_total = (nf / fps) / bar
        nearest = max(1, round(bars_total))
        int_err = abs(bars_total - nearest) / nearest
        if int_err > 0.02:
            int_err *= 3  # a piece that is not a whole number of bars always sounds unfinished
        if bounds:
            beat = 60.0 / bpm
            be = []
            for b in bounds:
                x = (b % beat) / beat
                be.append(min(x, 1 - x))
            bound_err = float(np.mean(be))
        else:
            bound_err = 0.0
        cand.append({"bpm": bpm, "bar_sec": round(bar, 3), "bars_total": round(bars_total, 2),
                     "fit": round(0.6 * int_err + 0.4 * bound_err, 3)})
    cand.sort(key=lambda c: (c["fit"], -c["bpm"]))
    # only surface practical tempo steps - 81 BPM is technically a better fit
    # than 120 here but nobody scores to it
    practical = [c for c in cand if c["bpm"] % 5 == 0][:5]

    out = {
        "video": os.path.abspath(args.video),
        "meta": meta,
        "action_peaks": peaks,
        "static_windows": statics,
        "scene_boundaries": merged,
        "brightness_curve": [round(float(b), 1) for b in bright[::max(1, nf // 120)]],
        "suggested_bpm": practical,
    }
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    print("frames %d  fps %.2f  duration %.2fs" % (nf, fps, nf / fps))
    print("action peaks   : %s" % ", ".join("%.2fs" % p["t"] for p in peaks[:12]))
    print("scene boundary : %s" % ", ".join("%.2fs" % m["t"] for m in merged))
    print("static windows : %s" % ", ".join("%.2f-%.2f" % (s["start"], s["end"]) for s in statics))
    print("tempo shortlist: %s" % ", ".join("%d BPM (bar %.2fs, %.1f bars)"
                                            % (c["bpm"], c["bar_sec"], c["bars_total"])
                                            for c in practical[:4]))
    print("-> pick by picture tempo, not by fit alone: corporate/flat 100-125, fast-cut 128-150, lyrical 70-95")
    print("wrote %s" % args.out)


if __name__ == "__main__":
    main()
