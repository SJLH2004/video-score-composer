# Arrangement schema

One JSON file describes the whole score. All times are in seconds from frame 0.

```json
{
  "duration": 12.0,
  "bpm": 120,
  "key": "C",
  "style": "wood",
  "seed": 20261020,
  "reverb": { "length": 1.6, "decay": 3.4, "wet": 0.5 },
  "master": { "peak": 0.85, "fade_in": 0.008, "fade_out": 0.30, "bright_shelf": true },
  "chords": [ { "t": 0.0, "dur": 2.2, "name": "C", "g": 0.85, "cutoff": 3400 } ],
  "events": [ { "inst": "marimba", "t": 3.28, "pitch": "G4", "g": 0.62, "pan": -0.5, "rev": 0.3 } ]
}
```

`duration` must equal the video length exactly — the engine allocates a buffer
of that size and appends reverb inside it, so nothing spills past the cut.

## Top level

| Field | Meaning |
|---|---|
| `duration` | total length in seconds, match the video |
| `bpm` | only used for your own bar maths; the engine reads absolute times |
| `style` | `wood` (marimba/kalimba lead) or `piano` (piano lead, slower pad attack, wetter) |
| `seed` | fixes detune/partial randomness, so re-renders are identical |
| `reverb` | `length` IR seconds, `decay` higher = shorter tail, `wet` 0–1 |
| `master` | `peak` target, fades, `bright_shelf` high-frequency lift |

## chords — sustained harmony

Each entry renders a pad plus a quiet octave layer an octave up. The voicing
comes from the built-in table, so `"name": "C"` is enough:

| name | voicing |
|---|---|
| `C` | G3 E4 D5 |
| `F` | C4 A4 E5 |
| `G` | D4 B4 F5 |
| `Am` | E4 A4 C5 |
| `Em` | E4 G4 B4 |
| `Dm` | D4 A4 F5 |

Add `"voicing": ["G3","E4"]` to override. Keep pad voicings **above C4** —
stacking thirds in the C3 octave is the fastest way to make the mix muddy.

`g` per section is the loudness arc: start ~0.85, rise to ~1.2 by the final bar.
`cutoff` opens as the film builds (3400 → 4400 → 5800) so the pad gets brighter
as the story resolves.

## events — one-shots and patterns

Common fields: `inst`, `g` (gain), `pan` (-1 left … 1 right), `rev` (0–1 reverb
send), `t` (start). Melodic instruments also take `pitch` ("C4", "F#2") and
optional `dur`.

### Instruments

| inst | character | good for |
|---|---|---|
| `marimba` | struck wood, fast decay, non-integer partials | object landings, main theme |
| `kalimba` | brighter, longer ring | sparkle, high countermelody |
| `piano` | additive harmonics, pedal-like tail | warm narration, closing chord |
| `bell` | inharmonic partials, long tail | logo hits, data pop-ins |
| `pad` | detuned sines, slow attack | only via `chords` normally; usable raw with an explicit `chord` |
| `bass` | sine + octave, lowpassed | root motion from bar 2 onward |
| `kick` | pitch-swept sine | beats 1 and 3 |
| `clap` | three noise bursts, bandpassed | backbeat from bar 3 |
| `shaker` | short highpassed noise | 8th-note pulse, quiet |
| `riser` | noise sweep, `f0`→`f1` | into a cut |
| `sweep` | descending tone burst | object entering from above |

### Patterns

Use `t0` / `t1` / `step` instead of `t` to repeat an instrument:

```json
{ "inst": "shaker", "t0": 1.0, "t1": 11.7, "step": 0.25, "g": 0.45, "pan": 0.25 }
```

## Timing practice

- Cue on the **landing frame**, minus 20–40 ms for percussive actions.
- One note per landing when objects arrive in sequence; walk the scale upward so
  each arrival feels like progress (G4 B4 D5 E5 G5 across five landings).
- Transitions get two cues: a riser starting where the picture starts changing,
  and an impact exactly where the new frame settles.
- Leave every `static_window` from the scan rhythmically thin — pad plus tail,
  no new attacks.
