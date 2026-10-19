"""Renders each scene's narration with Kokoro, plus per-word timestamps.

    uv run --python 3.12 --with kokoro --with soundfile --with pip \\
      python -I narrate.py <workdir> [--voice af_heart] [--speed 1.0] [--only 03_range 07_first]

Reads <workdir>/scenes.json: [{"id": "01_intro", "text": "..."}, ...]
Writes <workdir>/tts/<id>.wav (24 kHz) and <workdir>/tts/<id>.words.json ([{"w", "s", "e"}], seconds).
"""
import argparse
import json
from pathlib import Path

import numpy as np
import soundfile as sf
from kokoro import KPipeline

parser = argparse.ArgumentParser()
parser.add_argument("workdir", type=Path)
parser.add_argument("--voice", default="af_heart")
parser.add_argument("--speed", type=float, default=1.0)
parser.add_argument("--only", nargs="*", help="scene ids to re-render")
args = parser.parse_args()

out = args.workdir / "tts"
out.mkdir(parents=True, exist_ok=True)
scenes = json.loads((args.workdir / "scenes.json").read_text())
pipeline = KPipeline(lang_code=args.voice[0], repo_id="hexgrad/Kokoro-82M")

total = 0.0
for scene in scenes:
    if args.only and scene["id"] not in args.only:
        continue
    chunks, words, offset = [], [], 0.0
    for result in pipeline(scene["text"], voice=args.voice, speed=args.speed):
        audio = result.audio.numpy()
        for token in result.tokens:
            if token.start_ts is not None and token.text.strip():
                words.append({"w": token.text + (token.whitespace or ""), "s": offset + token.start_ts,
                              "e": offset + (token.end_ts or token.start_ts)})
        chunks.append(audio)
        offset += len(audio) / 24000
    sf.write(out / f"{scene['id']}.wav", np.concatenate(chunks), 24000)
    (out / f"{scene['id']}.words.json").write_text(json.dumps(words))
    total += offset
    print(f"{scene['id']:<20} {offset:6.2f}s  {len(scene['text'].split())} words")
print(f"{'speech total':<20} {total:6.1f}s")
