#!/usr/bin/env bash
# Checks everything the demo-video skill needs. Exits non-zero, listing what is missing, when the
# video cannot be made on this machine as it stands.
#
#   bash $SCRIPTS/preflight.sh   (SCRIPTS = the skill's base directory + /scripts)
missing=()
warn=()

command -v agent-browser >/dev/null || missing+=("agent-browser (records the browser): https://github.com/vercel-labs/agent-browser")
if command -v ffmpeg >/dev/null && command -v ffprobe >/dev/null; then
  ffmpeg -hide_banner -encoders 2>/dev/null | grep -q libx264 || missing+=("ffmpeg with libx264 (brew install ffmpeg)")
else
  missing+=("ffmpeg and ffprobe (brew install ffmpeg)")
fi
command -v uv >/dev/null || missing+=("uv (runs Kokoro and Pillow on Python 3.12): https://docs.astral.sh/uv/")

if command -v uv >/dev/null && ! uv python find 3.12 >/dev/null 2>&1; then
  warn+=("Python 3.12 is not installed yet; uv downloads it on first use")
fi
if ! curl -s -o /dev/null --max-time 5 https://huggingface.co; then
  ls ~/.cache/huggingface/hub 2>/dev/null | grep -qi kokoro \
    || missing+=("network access to huggingface.co (the Kokoro model is not cached yet)")
fi
command -v espeak-ng >/dev/null || warn+=("espeak-ng is missing; unknown words such as product names may be mispronounced (brew install espeak-ng)")
[ -f /System/Library/Fonts/SFNS.ttf ] || warn+=("no /System/Library/Fonts/SFNS.ttf; pass --font <a .ttf> to assemble.py")

for w in "${warn[@]}"; do echo "warning: $w"; done
if [ ${#missing[@]} -gt 0 ]; then
  echo "Cannot make a demo video here. Missing:"
  for m in "${missing[@]}"; do echo "  - $m"; done
  exit 1
fi
echo "ok: everything the demo-video skill needs is available"
