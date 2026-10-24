# Sound design and mastering

Everything here is synthesised from oscillators and filtered noise, so there is
no sample library to install and no licence to clear.

## Why the timbres sound real

Pitched percussion is not a sine wave. Each instrument stacks partials at
physical ratios; this is the single biggest difference between "cheap beep" and
"struck wood":

| inst | partials (× fundamental) |
|---|---|
| marimba | 1, 3.99, 6.30, 9.10 |
| kalimba | 1, 2.0, 5.4, 8.1 |
| bell | 1, 2.76, 5.40, 8.93 |
| piano | 1…9 integer harmonics at 1/k^1.3, plus a +0.15 % detuned layer |

Higher partials must decay faster than the fundamental, otherwise it rings like
a synth pad instead of a struck bar.

## The mixes that fail

**Muddy.** 400–1200 Hz dominates and nothing lives above 3.5 kHz. Symptom: it
sounds like the music is behind a blanket. Cause: pad voicings sitting in the C3
octave, plus every instrument lowpassed too hard.

Fix, in order:
1. Drop the lowest pad note (start voicings at G3, not C3).
2. Raise pad `cutoff` and thin the pad gain.
3. Add upper partials to the lead (6.3× and 9.1× on marimba).
4. Only then consider a high shelf.

A top-end shelf on a dull mix just adds hiss — the missing energy is in the
2–5 kHz presence band, not at 12 kHz.

**Harsh.** Too much 5–10 kHz from shaker/clap/riser stacked together. Pull the
shaker to 0.25 and let one percussion layer carry the pulse.

**Pumping.** The limiter is doing the arranging. Lower per-event gains instead of
pushing `tanh` harder.

## Objective checks

Run the engine and read its print line:

```
peak 0.850  rms -16.8 dBFS  rolloff85 1046 Hz
```

- `rolloff85` **is the brightness metric that matters** — 85 % of the energy sits
  below that frequency. Target 1.0–2.0 kHz for wood/percussion scores. Below
  900 Hz is dull; above 3 kHz usually means noise, not brightness.
- Do **not** judge brightness by spectral centroid. A handful of hissy high
  partials drags the centroid up while the mix stays muddy — both readings
  disagree and the centroid lies.
- `rms` between -18 and -15 dBFS is the right zone for background music. The
  delivered 12 s promo sits at -16.7 dBFS / ≈ -14.5 LUFS.
- Peak at -1 dBFS (0.85) leaves headroom for AAC encoding overshoot.

Verify integrated loudness with ffmpeg if needed:

```bash
ffmpeg -hide_banner -i score.wav -af ebur128=peak=true -f null -
```

## Reverb

A convolution IR built from exponentially decaying noise, lowpassed at 5.2 kHz so
the tail is soft rather than bright. `wet` 0.5 for wood, 0.6 for piano. Percussive
hits get 0.3–0.55 send; bass and kick get almost none (0.05–0.06) or the low end
smears.

Long tails are what create depth in a flat illustration — resist the urge to
shorten them just because the song is short.

## Stereo

Pan by musical role, not randomly: low end and pad centred, melody slightly off
centre, sparkle elements alternating ±0.3. Sequence landings across the stereo
field (−0.5 → +0.5) so a run of notes sweeps past the listener.

## Style presets

| style | lead | pad attack | wet | percussion |
|---|---|---|---|---|
| `wood` | marimba + kalimba | 0.45 s | 0.50 | shaker, kick, clap |
| `piano` | piano | 0.85 s | 0.60 | kick only, shaker at 45 % |

`wood` reads as bright, geometric, "Monument Valley". `piano` reads as warm,
narrative, corporate-emotional. Offer both when the brief does not pin the tone.
