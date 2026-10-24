#!/usr/bin/env python
"""Render an original score from an arrangement JSON.

No samples, no libraries, no downloads - every instrument is synthesised from
oscillators and noise, so the result is always usable and never a licensing risk.

Usage:
    python score_engine.py arrangement.json out.wav

Arrangement schema lives in references/arrangement_schema.md.
"""
import json
import sys

import numpy as np
import wave

SR = 48000

_PC = {'C': 0, 'D': 2, 'E': 4, 'F': 5, 'G': 7, 'A': 9, 'B': 11}

CHORDS = {
    'C': ['G3', 'E4', 'D5'], 'F': ['C4', 'A4', 'E5'], 'G': ['D4', 'B4', 'F5'],
    'Am': ['E4', 'A4', 'C5'], 'Em': ['E4', 'G4', 'B4'], 'Dm': ['D4', 'A4', 'F5'],
    'Fmaj7': ['C4', 'A4', 'E5'], 'G7': ['D4', 'F4', 'B4'], 'Cmaj9': ['G3', 'E4', 'D5'],
}


def hz(name):
    if isinstance(name, (int, float)):
        return float(name)
    p = _PC[name[0].upper()]
    i = 1
    if len(name) > 1 and name[1] in '#b':
        p += 1 if name[1] == '#' else -1
        i = 2
    midi = (int(name[i:]) + 1) * 12 + p
    return 440.0 * 2 ** ((midi - 69) / 12.0)


def env_exp(n, tau, attack=0.004):
    t = np.arange(n) / SR
    return np.exp(-t / tau) * np.clip(t / max(attack, 1e-5), 0, 1)


def fft_lp(x, cut, order=2):
    n = len(x)
    if not n:
        return x
    f = np.fft.rfftfreq(n, 1 / SR)
    return np.fft.irfft(np.fft.rfft(x) * (1 / np.sqrt(1 + (f / max(cut, 20)) ** (2 * order))), n)


def fft_hp(x, cut, order=2):
    n = len(x)
    f = np.fft.rfftfreq(n, 1 / SR)
    return np.fft.irfft(np.fft.rfft(x) * (1 / np.sqrt(1 + (max(cut, 20) / np.maximum(f, 1e-6)) ** (2 * order))), n)


def conv(x, ir):
    n = len(x) + len(ir) - 1
    size = 1 << int(np.ceil(np.log2(n)))
    return np.fft.irfft(np.fft.rfft(x, size) * np.fft.rfft(ir, size), size)[:len(x)]


class Instruments:
    """Marimba/kalimba/bell use non-integer partials - that is what makes them
    sound like struck wood and metal instead of plain sine beeps."""

    def __init__(self, rng):
        self.rng = rng

    def marimba(self, f, dur=1.1, soft=1.0):
        n = int(SR * dur)
        t = np.arange(n) / SR
        s = (np.sin(2 * np.pi * f * t)
             + 0.30 * np.sin(2 * np.pi * f * 3.99 * t) * np.exp(-t / (dur * 0.18))
             + 0.16 * np.sin(2 * np.pi * f * 9.10 * t) * np.exp(-t / (dur * 0.07))
             + 0.10 * np.sin(2 * np.pi * f * 6.30 * t) * np.exp(-t / (dur * 0.10)))
        return fft_lp(s * env_exp(n, dur * 0.42, 0.002), 11000) * soft

    def kalimba(self, f, dur=1.2, soft=1.0):
        n = int(SR * dur)
        t = np.arange(n) / SR
        s = (np.sin(2 * np.pi * f * t)
             + 0.22 * np.sin(2 * np.pi * f * 2.0 * t)
             + 0.14 * np.sin(2 * np.pi * f * 5.4 * t) * np.exp(-t / (dur * 0.2))
             + 0.07 * np.sin(2 * np.pi * f * 8.1 * t) * np.exp(-t / (dur * 0.12)))
        return fft_lp(s * env_exp(n, dur * 0.5, 0.003), 12000) * soft

    def piano(self, f, dur=2.0, soft=1.0):
        n = int(SR * dur)
        t = np.arange(n) / SR
        s = np.zeros(n)
        for k in range(1, 10):
            s += (1.0 / k ** 1.3) * np.sin(2 * np.pi * f * k * t + self.rng.uniform(0, 6.28)) \
                 * np.exp(-t / (dur * 0.55 / (1 + 0.30 * k)))
        s += 0.22 * np.sin(2 * np.pi * f * 1.0015 * t) * np.exp(-t / (dur * 0.55))
        return fft_lp(s * np.clip(t / 0.005, 0, 1), 9000) * soft * 0.42

    def bell(self, f, dur=2.4, soft=1.0):
        n = int(SR * dur)
        t = np.arange(n) / SR
        s = np.zeros(n)
        for mult, amp, dec in [(1.0, 1.0, 1.0), (2.76, 0.42, 0.55), (5.40, 0.20, 0.32), (8.93, 0.10, 0.20)]:
            s += amp * np.sin(2 * np.pi * f * mult * t) * np.exp(-t / (dur * dec * 0.5))
        return s * np.clip(t / 0.002, 0, 1) * soft * 0.30

    def pad(self, freqs, dur, soft=1.0, cutoff=3400, attack=0.5, release=0.3):
        n = int(SR * dur)
        t = np.arange(n) / SR
        s = np.zeros(n)
        for f in freqs:
            for det in (-0.004, 0.0, 0.005):
                s += np.sin(2 * np.pi * f * (1 + det) * t + self.rng.uniform(0, 6.28)) / len(freqs)
        s *= 1 + 0.12 * np.sin(2 * np.pi * 0.35 * t + 1.1)
        s *= np.clip(t / attack, 0, 1) * np.clip((dur - t) / release, 0, 1)
        return fft_lp(s, cutoff) * soft * 0.26

    def bass(self, f, dur=0.7, soft=1.0):
        n = int(SR * dur)
        t = np.arange(n) / SR
        s = np.sin(2 * np.pi * f * t) + 0.28 * np.sin(2 * np.pi * f * 2 * t)
        return fft_lp(s * env_exp(n, dur * 0.5, 0.008), 900) * soft * 0.5

    def kick(self, soft=1.0):
        n = int(0.4 * SR)
        t = np.arange(n) / SR
        ph = 2 * np.pi * np.cumsum(48 + 95 * np.exp(-t * 22)) / SR
        s = np.sin(ph) * np.exp(-t * 8.5) + self.rng.standard_normal(n) * np.exp(-t * 260) * 0.22
        return s * soft * 0.8

    def clap(self, soft=1.0):
        n = int(0.3 * SR)
        s = np.zeros(n)
        for d in (0.0, 0.008, 0.016):
            idx = int(d * SR)
            tt = np.arange(n - idx) / SR
            s[idx:] += self.rng.standard_normal(n - idx) * np.exp(-tt * 55)
        return fft_hp(fft_lp(s, 6000), 1100) * soft * 0.3

    def shaker(self, soft=1.0):
        n = int(0.11 * SR)
        t = np.arange(n) / SR
        return fft_hp(self.rng.standard_normal(n) * np.exp(-t * 70), 5600) * soft * 0.26

    def riser(self, dur, soft=1.0, f0=350, f1=9000):
        n = int(SR * dur)
        noise = self.rng.standard_normal(n)
        bs, blocks = n // 40, 40
        out = np.zeros(n)
        for i in range(blocks):
            out[i * bs:(i + 1) * bs] = fft_lp(noise[i * bs:(i + 1) * bs], f0 * (f1 / f0) ** (i / (blocks - 1)))
        t = np.arange(n) / SR
        out *= (t / dur) ** 2.2
        out[-int(0.01 * SR):] *= np.linspace(1, 0, int(0.01 * SR))
        return out * soft * 0.28

    def sweep(self, dur, soft=1.0):
        n = int(SR * dur)
        t = np.arange(n) / SR
        f = 1200 * np.exp(-t * 9) + 180
        return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 5.5) * np.clip(t / 0.004, 0, 1) * soft * 0.15


DEFAULT_DUR = {'marimba': 1.2, 'kalimba': 1.3, 'piano': 2.0, 'bell': 2.2, 'bass': 0.62,
               'kick': 0.4, 'clap': 0.3, 'shaker': 0.11, 'riser': 0.6, 'sweep': 0.8}


def render(arr, path):
    style = arr.get("style", "wood")
    dur_total = float(arr.get("duration", 12.0))
    N = int(round(SR * dur_total))
    rng = np.random.default_rng(arr.get("seed", 1))
    inst = Instruments(rng)
    buf = np.zeros((N, 2))
    send = np.zeros((N, 2))

    atk_extra = 0.40 if style == "piano" else 0.0

    def place(sig, t0, gain=1.0, pan=0.0, rev=0.22):
        i0 = int(round(t0 * SR))
        if i0 >= N or i0 < 0:
            return
        n = min(len(sig), N - i0)
        s = sig[:n] * gain
        ang = (np.clip(pan, -1, 1) + 1) * np.pi / 4
        l, r = np.cos(ang), np.sin(ang)
        buf[i0:i0 + n, 0] += s * l
        buf[i0:i0 + n, 1] += s * r
        send[i0:i0 + n, 0] += s * l * rev
        send[i0:i0 + n, 1] += s * r * rev

    # sustained harmony
    for c in arr.get("chords", []):
        name = c["name"]
        freqs = [hz(p) for p in CHORDS.get(name, c.get("voicing", CHORDS['C']))]
        d = float(c.get("dur", 2.2))
        g = float(c.get("g", 0.85))
        cut = c.get("cutoff", 3400)
        place(inst.pad(freqs, d, g, cutoff=cut, attack=0.45 + atk_extra, release=0.35),
              c["t"], 1.0, 0.0, rev=0.3)
        place(inst.pad([f * 2 for f in freqs[:2]], d, g * 0.35, cutoff=cut * 1.3,
                       attack=0.75 + atk_extra, release=0.4), c["t"], 1.0, 0.0, rev=0.35)

    # one-shot events
    for e in arr.get("events", []):
        name = e["inst"]
        g = float(e.get("g", 0.5))
        pan = float(e.get("pan", 0.0))
        rev = float(e.get("rev", 0.22))
        if "t0" in e:  # repeating pattern
            t = float(e["t0"])
            step = float(e.get("step", 0.25))
            n = 0
            while t < float(e.get("t1", dur_total)):
                fn = getattr(inst, name)
                place(fn(g), t, 1.0, pan, rev)
                t += step
                n += 1
            continue
        t = float(e["t"])
        fn = getattr(inst, name)
        if name == "pad":
            freqs = [hz(p) for p in CHORDS.get(e.get("chord"), e.get("voicing", CHORDS['C']))]
            place(fn(freqs, float(e.get("dur", 2.2)), g, cutoff=e.get("cutoff", 3400),
                     attack=e.get("attack", 0.45 + atk_extra)), t, 1.0, pan, rev)
            continue
        if name in ("riser", "sweep"):
            d = float(e.get("dur", 0.6))
            place(fn(d, g, e.get("f0", 350), e.get("f1", 9000)) if name == "riser" else fn(d, g),
                  t, 1.0, pan, rev)
            continue
        d = float(e.get("dur", DEFAULT_DUR.get(name, 1.0)))
        if name in ("kick", "clap", "shaker"):
            place(fn(g), t, 1.0, pan, rev)
        else:
            place(fn(hz(e["pitch"]), d, g), t, 1.0, pan, rev)

    # reverb
    ir_n = int(float(arr.get("reverb", {}).get("length", 1.6)) * SR)
    ir_t = np.arange(ir_n) / SR
    ir = rng.standard_normal(ir_n) * np.exp(-ir_t * float(arr.get("reverb", {}).get("decay", 3.4)))
    ir = fft_lp(ir, 5200)
    ir[:int(0.012 * SR)] *= np.linspace(0, 1, int(0.012 * SR))
    ir /= np.sqrt((ir ** 2).sum())
    wet = float(arr.get("reverb", {}).get("wet", 0.6 if style == "piano" else 0.5))
    for c in range(2):
        buf[:, c] += conv(send[:, c], ir) * wet

    # master
    mix = buf
    m = arr.get("master", {})
    for c in range(2):
        mix[:, c] = fft_hp(mix[:, c], 30)
        if m.get("bright_shelf", True):
            X = np.fft.rfft(mix[:, c])
            fr = np.fft.rfftfreq(len(mix[:, c]), 1 / SR)
            shelf = 1 + 0.6 / (1 + (2600 / np.maximum(fr, 1)) ** 2) + 0.30 / (1 + (9000 / np.maximum(fr, 1)) ** 2)
            mix[:, c] = np.fft.irfft(X * shelf, len(mix[:, c]))
        mix[:, c] = fft_lp(mix[:, c], 19500)

    fi = int(float(m.get("fade_in", 0.008)) * SR)
    if fi:
        mix[:fi] *= np.linspace(0, 1, fi)[:, None]
    fo = int(float(m.get("fade_out", 0.30)) * SR)
    if fo:
        mix[-fo:] *= np.linspace(1, 0, fo)[:, None] ** 1.4

    mix /= np.abs(mix).max() / 1.25
    mix = np.tanh(mix * 0.72)
    mix *= float(m.get("peak", 0.85)) / np.abs(mix).max()

    mono = mix.mean(1)
    rms = 20 * np.log10(np.sqrt((mono ** 2).mean()) + 1e-12)
    X = np.abs(np.fft.rfft(mono))
    f = np.fft.rfftfreq(len(mono), 1 / SR)
    roll = f[np.searchsorted(np.cumsum(X ** 2), (X ** 2).sum() * 0.85)]
    print("peak %.3f  rms %.1f dBFS  rolloff85 %.0f Hz%s"
          % (np.abs(mix).max(), rms, roll, "  (dull - raise upper partials)" if roll < 900 else ""))

    data = (np.clip(mix, -1, 1) * 32767).astype(np.int16)
    with wave.open(path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(data.tobytes())
    print("wrote %s (%.2fs)" % (path, len(data) / SR))


if __name__ == "__main__":
    if len(sys.argv) < 3:
        raise SystemExit("usage: score_engine.py arrangement.json out.wav")
    with open(sys.argv[1], encoding="utf-8") as f:
        render(json.load(f), sys.argv[2])
