#!/usr/bin/env bash
# Checks everything the demo-video skill needs. Exits non-zero, listing what is missing, when the
# video cannot be made on this machine as it stands.
#
#   bash "$SCRIPTS/preflight.sh"
#
# In an image that preinstalled the skill's environment (DEMO_VIDEO_VENV is set), anything missing but the
# browser is a fault of the image, not something to install by hand. Such an image can set
# DEMO_VIDEO_CHROME_HINT to say how its users add a Chrome.
missing=()
warn=()
fonts=(/System/Library/Fonts/SFNS.ttf /usr/share/fonts/truetype/dejavu/DejaVuSans.ttf) # assemble.py's FONTS

# hint <what> <how to install it outside such an image>
hint() {
  if [[ -n "${DEMO_VIDEO_VENV:-}" ]]; then
    echo "$1 (this image should have it; tell the user)"
  else
    echo "$1 ($2)"
  fi
}

command -v agent-browser >/dev/null ||
  missing+=("$(hint "agent-browser (records the browser)" "https://github.com/vercel-labs/agent-browser")")
if command -v ffmpeg >/dev/null && command -v ffprobe >/dev/null; then
  ffmpeg -hide_banner -encoders 2>/dev/null | grep -q libx264 ||
    missing+=("$(hint "ffmpeg with libx264" "your package manager's ffmpeg")")
else
  missing+=("$(hint "ffmpeg and ffprobe" "your package manager's ffmpeg")")
fi

if command -v agent-browser >/dev/null; then
  chrome="$(agent-browser --json doctor --offline --quick 2>/dev/null | python3 -c '
import json, sys
checks = json.load(sys.stdin)["checks"]
print(next((check["status"] for check in checks if check["id"] == "chrome.installed"), "fail"))' 2>/dev/null)"
  [[ "$chrome" == pass ]] ||
    missing+=("a Chrome for agent-browser (${DEMO_VIDEO_CHROME_HINT:-agent-browser install})")
fi

if [[ -n "${DEMO_VIDEO_VENV:-}" ]]; then
  [[ -x "$DEMO_VIDEO_VENV/bin/python" ]] || missing+=("$(hint "the Python environment at $DEMO_VIDEO_VENV")")
  ls "${DEMO_VIDEO_HF_HOME:-}/hub" 2>/dev/null | grep -qi kokoro ||
    missing+=("$(hint "Kokoro's model in ${DEMO_VIDEO_HF_HOME:-DEMO_VIDEO_HF_HOME}")")
else
  command -v uv >/dev/null || missing+=("uv (runs Kokoro and Pillow on Python 3.12): https://docs.astral.sh/uv/")
  if command -v uv >/dev/null && ! uv python find 3.12 >/dev/null 2>&1; then
    warn+=("Python 3.12 is not installed yet; uv downloads it on first use")
  fi
  if ! ls "${HF_HOME:-$HOME/.cache/huggingface}/hub" 2>/dev/null | grep -qi kokoro; then
    curl -s -o /dev/null --max-time 5 https://huggingface.co ||
      missing+=("network access to huggingface.co (the Kokoro model is not cached yet)")
  fi
fi

command -v espeak-ng >/dev/null ||
  warn+=("espeak-ng is missing; unknown words such as product names may be mispronounced")
has_font=""
for font in "${fonts[@]}"; do
  [[ -f "$font" ]] && has_font=1
done
[[ -n "$has_font" ]] || warn+=("none of ${fonts[*]} exists; pass --font <a .ttf> to assemble.py")

for w in "${warn[@]}"; do echo "warning: $w"; done
if [ ${#missing[@]} -gt 0 ]; then
  echo "Cannot make a demo video here. Missing:"
  for m in "${missing[@]}"; do echo "  - $m"; done
  exit 1
fi
echo "ok: everything the demo-video skill needs is available"
