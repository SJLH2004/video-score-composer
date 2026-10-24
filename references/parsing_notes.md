# Parsing notes — ffmpeg and After Effects

Hard-won details that cost time when forgotten.

## ffmpeg

**Frame extraction for analysis.** Extract small grayscale frames, never the full
resolution — 300 frames at 320 px is a few MB and loads instantly:

```bash
ffmpeg -y -v error -i in.mov -vf "scale=320:-1,format=gray" frames/g_%05d.png
ffmpeg -y -v error -i in.mov -vf "scale=320:-1"            frames/c_%05d.png
```

The grayscale set drives motion and brightness maths; the colour set is only
needed when tracking a coloured object.

**Contact sheets beat reading frames one by one.** To see a dense action sequence
at a glance:

```bash
ffmpeg -y -ss 3.0 -t 2.6 -i in.mov -vf "fps=5,scale=300:-1,tile=4x4" -frames:v 1 sheet.png
```

Tiles fill row-major, so frame *n* is at row `n//4`, column `n%4`, time
`3.0 + n*0.2`.

**`drawtext` needs fontconfig.** On a machine without it, ffmpeg exits with
`Fontconfig error: Cannot load default config file` and writes nothing. Drop the
label and count tiles instead, or burn timestamps with PIL afterwards.

**Colour-locating an object.** Threshold per channel rather than by hue. A flat
orange ball (#F5B54A) on cream (#F7EEDC) is cleanest as
`R>200 & 130<G<218 & B<165` — background blue channel sits near 220, so `B<165`
separates them with no colour-space conversion.

**Average brightness per frame** without writing frames at all:

```bash
ffmpeg -v error -i in.mov -vf "signalstats,metadata=print:key=lavfi.signalstats.YAVG:file=yavg.txt" -an -f null -
```

**Scene-change detection is unreliable on flat 2D animation.**
`select='gt(scene,0.06)'` returns zero cuts on a flat-colour AE export because
every pixel that changes is already a solid block; the histogram barely moves.
Use frame-to-frame mean absolute difference instead (what `rhythm_scan.py` does),
and detect section changes as a **sliding-window brightness step**, not a
single-frame jump — a 0.4 s window on each side survives slow cross-fades.

**NVENC output can break phone playback.** Encoding with `h264_nvenc` may produce
`gbrp` / High 4:4:4 Predictive. Local players cope, WeChat mobile shows
pink-green. Always force `-pix_fmt yuv420p`.

## After Effects

**ExtendScript has no `JSON` object.** `JSON.stringify()` throws
`"JSON"未定义` and the script dies mid-run. Write a recursive serialiser by hand:

```javascript
function esc(s){ return String(s).replace(/\\/g,"\\\\").replace(/"/g,'\\"').replace(/[\r\n\t]/g," "); }
function ser(v){
  if (v === null || v === undefined) return "null";
  var t = typeof v;
  if (t === "number") return isFinite(v) ? String(v) : "null";
  if (t === "boolean") return v ? "true" : "false";
  if (t === "string") return '"' + esc(v) + '"';
  if (v instanceof Array){ var a=[]; for (var i=0;i<v.length;i++) a.push(ser(v[i])); return "["+a.join(",")+"]"; }
  if (t === "object"){ var o=[]; for (var k in v){ if (v.hasOwnProperty(k)) o.push('"'+esc(k)+'":'+ser(v[k])); } return "{"+o.join(",")+"}"; }
  return "null";
}
```

**The launcher can be blocked by an agent sandbox.** `AfterFX.exe -r script.jsx`
dies with `PROGRAM BLOCKED BY SECURITY POLICY ... WMIC.exe` when launched from
inside a restricted sandbox — AE itself invokes WMIC at startup and the blocklist
kills it, exiting with code 0 and no output. It only starts with the sandbox
disabled, which prompts the user.

**A modal error blocks the instance.** Once a script throws, AE sits behind an
alert dialog and every later `-r` invocation queues silently. Do not kill the
process blindly — the user may have their own project open with unsaved work.
Ask them to dismiss it, or skip project parsing entirely.

**Prefer not to open the project at all.** The rendered video already contains
the final timing; keyframes tell you when a property was animated, not when it is
visible after parenting, pre-comps, time remapping and motion blur. Frame analysis
of the output is both simpler and more accurate.

**If a project must be read**, copy the `.aep` to an ASCII path first (Chinese
paths break `File` objects in some builds), `app.open()` it explicitly inside the
script, run with dialogs suppressed, and close with `DO_NOT_SAVE_CHANGES`:

```javascript
try { app.beginSuppressDialogs(); } catch(e){}
var proj = app.open(new File("C:/Temp/work/proj.aep"));
// ... read comps / layers / keyTimes ...
proj.close(CloseOptions.DO_NOT_SAVE_CHANGES);
try { app.endSuppressDialogs(false); } catch(e){}
```

Write results to a file with `f.encoding = "UTF-8"`; do not return them via
`alert()`, which blocks the instance again.
