---
name: video-score-composer
description: Compose original, royalty-free background music for a video or motion-graphics piece, with every musical cue locked to the actual motion in the picture. Use when the user asks to 配乐 / 加背景音乐 / BGM / 配一段音乐 / score a video / sync music to animation, for promos, title sequences, explainers, shorts and AE/PR exports. Synthesises the audio from scratch (numpy, no samples, no downloads) so the result is always usable and never a licensing risk.
agent_created: true
---

# Video Score Composer

Compose a score that fits the cut rather than dropping in a stock loop: read the
picture frame by frame, find where it actually moves, build a tempo grid around
those points, then synthesise original music on top of it.

## When to use

Trigger on: 配乐, 加 BGM, 背景音乐, 配一段音乐, score / soundtrack / sync music
to animation, "节奏对应动画", "音乐风格符合画面".

Do **not** use for: replacing dialogue audio, sound-design cleanup, or picking
out an existing library track the user already owns.

## Workflow

### 1. Probe the asset

```bash
ffprobe -v error -show_entries stream=codec_type,width,height,r_frame_rate,duration,nb_frames -of json <video>
```

Note whether an audio track exists. A `qtrle` / `png` / `prores` export from
After Effects is usually silent, which is exactly the case this skill is for.

### 2. Scan the rhythm

```bash
python scripts/rhythm_scan.py <video> --out rhythm.json
```

Needs `ffmpeg`, `ffprobe`, `numpy`, `pillow`. It extracts every frame at 320 px and reports:

- `action_peaks` — where the picture changes fastest (hit these)
- `scene_boundaries` — `t` is where a transition **starts**, `end` where it settles
- `static_windows` — stretches where nothing moves (leave the score open here)
- `suggested_bpm` — tempo shortlist, already filtered to whole-bar totals

**Treat the tempo shortlist as input, not as the answer.** Choose by picture
tempo: corporate / flat illustration 100–125, fast-cut or 快闪 128–150, lyrical
or 国风 70–95. Confirm the piece is a whole number of bars — a 12 s film at
120 BPM is exactly 6 bars, which is why that tempo felt right.

### 3. Decide the structure

Map the scan onto bars. For each section note what appears, when it lands, and
whether the picture then holds still. Then assign one musical gesture per visual
gesture:

| Picture gesture | Musical gesture |
|---|---|
| Element fades / rises in | soft bell or kalimba on the frame it starts |
| Object drops and settles | struck note (marimba) at the landing frame |
| Several objects land in sequence | ascending scale, one note per landing |
| Hard cut / scene change | noise riser into the cut, impact on settle |
| Data or text popping in | short bell, panned toward where it appears |
| Growth curve drawing | ascending arpeggio spanning the draw |
| Final logo hold | resolved chord decaying into the last frame |

Place cues 20–40 ms *before* a percussive visual landing — the ear accepts early
far better than late.

### 4. Write the arrangement

Copy `assets/example_arrangement.json` and edit it. Every field and instrument is
documented in `references/arrangement_schema.md`.

Two rules matter more than the rest:

- **Keep cues sparse where the picture is still.** Silence and reverb tails are
  what make a 12 s piece feel spacious instead of cluttered.
- **Land the last chord on the resolution and let it decay to the final frame** —
  never hard-cut music.

### 5. Render, then check

```bash
python scripts/score_engine.py arrangement.json score.wav
```

The engine prints peak, RMS and `rolloff85`. Read `references/sound_design.md`
before adjusting. Short version: below ~900 Hz the mix is dull — fix it by
raising upper partials and thinning the pad's low-mids, **not** by shelving up
the top end, which only adds hiss.

### 6. Mux and deliver

```bash
ffmpeg -y -i <video> -i score.wav -map 0:v:0 -map 1:a:0 \
  -c:v libx264 -preset slow -crf 15 -tune animation -pix_fmt yuv420p \
  -c:a aac -b:a 192k -shortest -movflags +faststart out.mp4
```

Always force `-pix_fmt yuv420p` (never leave NVENC on `gbrp`) or some players
read the chroma planes wrong and the picture turns pink-green. Deliver both the
muxed MP4 and the standalone WAV so the user can re-level later.

## Reading an After Effects project

Optional — the rendered video already carries the final timing, and frame
analysis is more faithful than keyframes. If the project itself is needed, read
`references/parsing_notes.md` first: ExtendScript has no `JSON` object, and an
agent sandbox can block the AE launcher outright.

## Resources

- `scripts/rhythm_scan.py` — video to rhythm map
- `scripts/score_engine.py` — arrangement to WAV
- `assets/example_arrangement.json` — full 12 s corporate promo score, use as the starting template
- `references/arrangement_schema.md` — every field and instrument
- `references/sound_design.md` — timbre, spectrum self-check, mastering
- `references/parsing_notes.md` — ffmpeg and After Effects gotchas
