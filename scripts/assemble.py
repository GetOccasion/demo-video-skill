"""Joins recorded takes, places each scene's narration at its recorded start and burns in subtitles.

    uv run --python 3.12 --with pillow python -I assemble.py <workdir> --takes desktop phone outro \\
      [--size 1440x900] [--out demo] [--font /System/Library/Fonts/SFNS.ttf]

Needs, per take, <workdir>/<take>.mp4 and either <take>.holds.json (an untimed recording) or
<take>.timeline.json (a timed one), both written by recorder.py, and <workdir>/tts/<scene>.wav +
.words.json (written by narrate.py). An untimed take is stretched here: the frame at each hold point
is frozen until the narration reaches that point's cue word.
Writes <workdir>/build/<out>.mp4 (burned-in subtitles plus a soft subtitle track) and <out>.srt.
Burns subtitles in with Pillow images and an overlay, so ffmpeg needs no libass or drawtext.
"""
import argparse
import json
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

parser = argparse.ArgumentParser()
parser.add_argument("workdir", type=Path)
parser.add_argument("--takes", nargs="+", required=True)
parser.add_argument("--size", default="1440x900")
parser.add_argument("--out", default="demo")
parser.add_argument("--font", default="/System/Library/Fonts/SFNS.ttf")
parser.add_argument("--canvas", default="0xEEEAF6", help="background behind takes of another size, e.g. a phone")
args = parser.parse_args()

SP = args.workdir.resolve()  # the concat lists need absolute paths
TTS, OUT = SP / "tts", SP / "build"
OUT.mkdir(exist_ok=True)
W, H = map(int, args.size.split("x"))
FPS = 30


def run(*cmd):
    subprocess.run([str(c) for c in cmd], check=True)


def probe(path, entries="format=duration"):
    return subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", entries,
                           "-of", "csv=p=0", str(path)], capture_output=True, text=True, check=True).stdout.strip()


def flashes(src):
    """Frame ranges [first, end) where the recorder's magenta sync flash fills the screen."""
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(src), "-vf", f"fps={FPS},scale=8:5",
                          "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True, check=True).stdout
    size = 8 * 5 * 3
    magenta = [sum(r > 200 and g < 80 and b > 200 for r, g, b in zip(*[iter(raw[i:i + size])] * 3)) > 30
               for i in range(0, len(raw), size)]
    runs, first = [], None
    for frame, on in enumerate(magenta + [False]):
        if on and first is None:
            first = frame
        elif not on and first is not None:
            runs.append((first, frame))
            first = None
    return runs


def plan_holds(take, src, log):
    """Turns an untimed take's hold points into segments of recorded frames, each followed by a frozen frame.

    Logged times are mapped onto the video through the two sync flashes, which are cut out.
    Returns ([[first_frame, end_frame, hold_frames], ...], {scene: start seconds in the stretched take}).
    """
    runs = flashes(src)
    if len(runs) < 2:
        raise SystemExit(f"{take}: expected a sync flash at each end of the recording, found {len(runs)}")
    (open_at, opened), (close_at, _) = runs[0], runs[-1]
    (logged_open, logged_close) = log["sync"]
    rate = (close_at - open_at) / (logged_close - logged_open)

    def frame_of(seconds):
        return round(open_at + (seconds - logged_open) * rate)

    base = cursor = opened + 2
    segments, timeline, shift = [], {}, 0
    for hold in log["holds"]:
        if "start" in hold:
            timeline[hold["scene"]] = (max(frame_of(hold["start"]), cursor) - base + shift) / FPS
            continue
        frame = max(frame_of(hold["at"]) - 1, cursor)
        frames = round((timeline[hold["scene"]] + hold["until"]) * FPS) - (frame - base + shift)
        if frames < -0.3 * FPS:
            print(f"warning: {take}/{hold['scene']}: an action meant for {hold['until']:.1f}s into the narration "
                  f"runs {-frames / FPS:.1f}s late; move earlier actions out of the way")
        if frames > 0:
            if frame > cursor:
                segments.append([cursor, frame, frames])
                cursor = frame
            elif segments:
                segments[-1][2] += frames
            else:
                segments.append([cursor, cursor + 1, frames])
                cursor += 1
            shift += frames
    segments.append([cursor, close_at, 0])
    return segments, timeline


def stretch(src, dst, vf, segments):
    """Encodes each segment with its frozen frame, then joins them without re-encoding."""
    parts = []
    for i, (first, end, frames) in enumerate(segments):
        part = OUT / f"{dst.stem}.part{i:03}.mp4"
        run("ffmpeg", "-v", "error", "-y", "-ss", f"{first / FPS:.4f}", "-t", f"{(end - first) / FPS:.4f}", "-i", src,
            "-vf", f"{vf},fps={FPS},tpad=stop_mode=clone:stop_duration={frames / FPS:.4f},format=yuv420p",
            "-c:v", "libx264", "-crf", "18", "-an", part)
        parts.append(part)
    listing = OUT / f"{dst.stem}.parts.txt"
    listing.write_text("".join(f"file '{part}'\n" for part in parts))
    run("ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", listing, "-c", "copy", dst)
    for part in parts:
        part.unlink()


# 1. Every take becomes WxH at 30 fps. A take of another size (a phone) is fitted onto a canvas.
#    An untimed take is stretched to its narration on the way.
offsets, timelines, total = {}, {}, 0.0
for take in args.takes:
    src, dst = SP / f"{take}.mp4", OUT / f"{take}.mp4"
    width, height = map(int, probe(src, "stream=width,height").split(","))
    if (width, height) == (W, H):
        vf = f"scale={W}:{H}"
    else:
        vf = (f"scale={W - 60}:{H - 60}:force_original_aspect_ratio=decrease,"
              f"pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:color={args.canvas}")
    holds = SP / f"{take}.holds.json"
    if holds.exists():
        segments, timelines[take] = plan_holds(take, src, json.loads(holds.read_text()))
        stretch(src, dst, vf, segments)
    else:
        timelines[take] = json.loads((SP / f"{take}.timeline.json").read_text())
        run("ffmpeg", "-v", "error", "-y", "-i", src, "-vf", f"{vf},fps={FPS},format=yuv420p",
            "-c:v", "libx264", "-crf", "18", "-an", dst)
    offsets[take] = total
    total += float(probe(dst))

# 2. Each scene's narration starts where its take's timeline puts that scene.
placed = [(scene, offsets[take] + start) for take in args.takes for scene, start in timelines[take].items()]
inputs, filters = [], []
for i, (scene, at) in enumerate(placed):
    inputs += ["-i", TTS / f"{scene}.wav"]
    ms = int(at * 1000)
    filters.append(f"[{i}:a]aresample=48000,adelay={ms}|{ms}[a{i}]")
filters.append("".join(f"[a{i}]" for i in range(len(placed))) +
               f"amix=inputs={len(placed)}:normalize=0,apad,atrim=0:{total:.3f}[out]")
run("ffmpeg", "-v", "error", "-y", *inputs, "-filter_complex", ";".join(filters), "-map", "[out]",
    "-ac", "2", "-c:a", "aac", "-b:a", "192k", OUT / "narration.m4a")


# 3. Subtitle cues: a sentence, or a clause once it passes ~55 characters. At most ~80 per cue.
def raw_cues():
    for scene, at in placed:
        cue = []
        for word in json.loads((TTS / f"{scene}.words.json").read_text()):
            cue.append(word)
            text = "".join(w["w"] for w in cue).strip()
            token = word["w"].strip()
            if token in {".", "?", "!", ":"} or len(text) > 80 or (len(text) > 55 and token in {",", ";"}):
                yield at + cue[0]["s"], at + cue[-1]["e"], text
                cue = []
        if cue:
            yield at + cue[0]["s"], at + cue[-1]["e"], "".join(w["w"] for w in cue).strip()


def tidy(text):
    for mark in " . , ? ! : ;".split():
        text = text.replace(f" {mark}", mark)
    return text


cues = []
for start, end, text in raw_cues():
    text = tidy(text)
    if text[0] in ",.;:" and cues:  # punctuation split off a cue belongs to the one before
        cues[-1] = (cues[-1][0], cues[-1][1], cues[-1][2] + text[0])
        text = text[1:].strip()
    cues.append((start, end, text))
# Hold each cue up to 0.8s past its last word, but never into the next cue.
cues = [(s, min(e + 0.8, (cues[i + 1][0] if i + 1 < len(cues) else total) - 0.05), t)
        for i, (s, e, t) in enumerate(cues)]


def timestamp(seconds):
    ms = int(round(seconds * 1000))
    return f"{ms // 3600000:02}:{ms // 60000 % 60:02}:{ms // 1000 % 60:02},{ms % 1000:03}"


srt = OUT / f"{args.out}.srt"
srt.write_text("\n".join(f"{i + 1}\n{timestamp(s)} --> {timestamp(e)}\n{t}\n" for i, (s, e, t) in enumerate(cues)))

# 4. One transparent PNG per cue, strung into an overlay stream with the concat demuxer.
font = ImageFont.truetype(args.font, round(H / 30))
line_height = round(H / 22.5)


def wrap(text, width=W * 0.62):
    lines, line = [], ""
    for word in text.split():
        trial = f"{line} {word}".strip()
        if font.getlength(trial) > width and line:
            lines.append(line)
            line = word
        else:
            line = trial
    return lines + [line]


blank = OUT / "blank.png"
Image.new("RGBA", (W, H), (0, 0, 0, 0)).save(blank)
entries, cursor = [], 0.0
for i, (start, end, text) in enumerate(cues):
    image = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    lines = wrap(text)
    box_w = max(font.getlength(line) for line in lines) + 48
    box_h = line_height * len(lines) + 24
    x0, y0 = (W - box_w) / 2, H - 48 - box_h
    draw.rounded_rectangle([x0, y0, x0 + box_w, y0 + box_h], radius=12, fill=(17, 17, 28, 210))
    for n, line in enumerate(lines):
        draw.text((W / 2, y0 + 12 + n * line_height + line_height / 2), line, font=font, fill="white", anchor="mm")
    path = OUT / f"cue{i:03}.png"
    image.save(path)
    entries += [(blank, start - cursor), (path, end - start)]
    cursor = end
entries.append((blank, total - cursor))
subs = OUT / "subs.txt"
subs.write_text("".join(f"file '{p}'\nduration {max(d, 0.001):.3f}\n" for p, d in entries) + f"file '{blank}'\n")

# 5. Takes + subtitle overlay + narration + soft subtitle track.
takes = OUT / "takes.txt"
takes.write_text("".join(f"file '{OUT / f'{t}.mp4'}'\n" for t in args.takes))
video = OUT / f"{args.out}.mp4"
run("ffmpeg", "-v", "error", "-y",
    "-f", "concat", "-safe", "0", "-i", takes,
    "-f", "concat", "-safe", "0", "-i", subs,
    "-i", OUT / "narration.m4a", "-i", srt,
    "-filter_complex", f"[1:v]fps={FPS},format=rgba[subs];[0:v][subs]overlay=0:0:shortest=1,format=yuv420p[v]",
    "-map", "[v]", "-map", "2:a", "-map", "3:s",
    "-c:v", "libx264", "-crf", "20", "-c:a", "copy", "-c:s", "mov_text",
    "-metadata:s:s:0", "language=eng", "-movflags", "+faststart", video)
print(f"{video}: {total:.1f}s, {len(cues)} subtitle cues")
