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
- A Chrome that agent-browser finds (`agent-browser install` gets one)
- [`uv`](https://docs.astral.sh/uv/), which runs Kokoro and Pillow on Python 3.12 from `uv.lock`
- Network access to Hugging Face the first time, to download the Kokoro model
- A subtitle font: macOS's system font or DejaVu Sans (`fonts-dejavu-core` on Debian and Ubuntu), or `--font`
- Optional: `espeak-ng`, for better pronunciation of unusual words

## Preinstall it in an image

To make videos in a container or CI runner that has no network, or should not download a few GB per job, install the environment and the model when the image is built, then point the scripts at them:

```dockerfile
COPY demo-video /opt/demo-video/skill
RUN cd /opt/demo-video/skill \
 && UV_PROJECT_ENVIRONMENT=/opt/demo-video/venv UV_PYTHON_INSTALL_DIR=/opt/demo-video/python \
    UV_PYTHON_PREFERENCE=only-managed UV_COMPILE_BYTECODE=1 uv sync --frozen \
 && HF_HOME=/opt/demo-video/hf /opt/demo-video/venv/bin/python scripts/fetch_model.py
ENV DEMO_VIDEO_VENV=/opt/demo-video/venv DEMO_VIDEO_HF_HOME=/opt/demo-video/hf
```

With `DEMO_VIDEO_VENV` set, `scripts/python` runs that environment with Hugging Face offline, so a missing model fails instead of downloading. Chrome's sandbox usually can't start in a container; `AGENT_BROWSER_ARGS=--no-sandbox` turns it off. An image whose users add Chrome some way of their own can set `DEMO_VIDEO_CHROME_HINT` to that instruction, and the preflight prints it when Chrome is missing.

## Contents

- `SKILL.md`: the workflow Claude follows, from picking the story to reviewing the result.
- `scripts/preflight.sh`: checks everything above before any work starts.
- `scripts/python`: runs the Python scripts on the locked environment, or a preinstalled one.
- `scripts/narrate.py`: renders each scene's narration and its word timings.
- `scripts/recorder.py`: the scenario API (`Demo`, takes, scenes, cues, menu helpers).
- `scripts/assemble.py`: freezes frames to the narration, adds subtitles and audio.
- `scripts/fetch_model.py`: puts a pinned revision of the Kokoro model in a Hugging Face cache.
- `references/example_scenario.py`: a full example scenario for a fictional app.

## License

MIT
