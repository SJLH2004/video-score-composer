# Changelog

## v1.0.0 — 2026-10-24

First public release.

- `scripts/rhythm_scan.py` — extracts frames at 320 px and reports action peaks,
  scene boundaries, static windows and a practical tempo shortlist.
- `scripts/score_engine.py` — renders an arrangement JSON to a 16-bit 48 kHz
  stereo WAV using only numpy: eleven fully synthesised instruments (marimba,
  kalimba, piano, bell, pad, bass, kick, clap, shaker, riser, sweep), a
  convolution reverb built from decaying filtered noise, and a mastering chain
  with fade in/out and peak normalisation.
- `assets/example_arrangement.json` — complete 12 s / 120 BPM / 6 bar score used
  as the starting template and by the self-test.
- `references/` — arrangement schema, sound design and mastering notes, and the
  ffmpeg / After Effects parsing gotchas.
- `selftest.py` — renders the example, validates format, level and stereo image,
  asserts render determinism, and generates a synthetic video with
  `ffmpeg -f lavfi` to exercise the scan when ffmpeg is present.
- `SKILL.md` — agent skill definition for SKILL.md-compatible runtimes.
