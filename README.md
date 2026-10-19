# demo-video

A [Claude Code](https://claude.com/claude-code) skill that turns a web app feature into a narrated, subtitled demo video. Claude scripts real interactions in a real browser, writes and voices the narration, and burns in subtitles. Everything runs locally.

- **Browser:** [agent-browser](https://github.com/vercel-labs/agent-browser) drives and records the page.
- **Voice:** [Kokoro](https://huggingface.co/hexgrad/Kokoro-82M) renders the narration, with per-word timestamps.
- **Assembly:** ffmpeg and Pillow join the takes, place the narration and burn in the subtitles.

## How it works

The narration is the clock. The voiceover is rendered first, and every browser action is cued to the word that talks about it.

Recording doesn't wait for the narration. Actions run back to back, and each cue is logged as a hold point. Assembly then freezes the frame at each hold point until the narration reaches that word. A two-minute video records in under a minute, and a broken step fails within seconds.

A magenta flash at each end of a take lines the recording's clock up with the logged cues. The pointer glides between targets and scrolls are animated, so every motion is recorded in full before a frame is frozen.

## Install

Clone it into your skills directory:

```bash
git clone https://github.com/GetOccasion/demo-video-skill ~/.claude/skills/demo-video
```

Then ask Claude Code for a demo video of a feature. The skill checks its own requirements first (`scripts/preflight.sh`):

- `agent-browser`
- `ffmpeg` and `ffprobe` with libx264
- [`uv`](https://docs.astral.sh/uv/), which runs Kokoro and Pillow on Python 3.12
- Network access to Hugging Face the first time, to download the Kokoro model
- Optional: `espeak-ng`, for better pronunciation of unusual words

## Contents

- `SKILL.md`: the workflow Claude follows, from picking the story to reviewing the result.
- `scripts/narrate.py`: renders each scene's narration and its word timings.
- `scripts/recorder.py`: the scenario API (`Demo`, takes, scenes, cues, menu helpers).
- `scripts/assemble.py`: freezes frames to the narration, adds subtitles and audio.
- `references/example_scenario.py`: a full example scenario for a fictional app.

## License

MIT
