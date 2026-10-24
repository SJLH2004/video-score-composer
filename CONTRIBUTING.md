# Contributing

Issues and pull requests are welcome, especially:

- **New instruments.** Add a method to `Instruments` in `scripts/score_engine.py`
  using physical partial ratios (not a plain sine), document it in
  `references/sound_design.md`, and add it to the instrument table in
  `references/arrangement_schema.md`.
- **Better tempo estimation** in `scripts/rhythm_scan.py`. The current shortlist
  scores whole-bar fit plus boundary alignment; it is deliberately capped to
  5-BPM steps because nobody scores at 81 BPM.
- **Style presets** beyond `wood` and `piano`.

## Ground rules

1. **No audio files, ever.** Everything is synthesised from oscillators and
   filtered noise. A PR that adds a sample library will not be merged.
2. **Keep `score_engine.py` numpy-only.** The render step must work in a bare
   Python environment with no ffmpeg installed.
3. **Run `python selftest.py` before opening a PR.** It renders the example
   twice and validates level, duration, stereo image and determinism.
4. **Document new fields** in `references/arrangement_schema.md`. The JSON schema
   is the public API.

## Reporting a problem

Include the arrangement JSON (or the smallest version that reproduces it), the
engine's printed `peak / rms / rolloff85` line, and your Python + numpy versions.
