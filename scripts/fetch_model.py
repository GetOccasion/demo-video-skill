"""Puts Kokoro's model and voices in the Hugging Face cache at HF_HOME, so narrate.py runs offline.

    HF_HOME=<dir> bash scripts/python scripts/fetch_model.py

The revision is pinned. Kokoro asks for the repository's main branch, so main is pointed at that revision too.
"""
from pathlib import Path

from huggingface_hub import snapshot_download

REPO = "hexgrad/Kokoro-82M"
REVISION = "f3ff3571791e39611d31c381e3a41a3af07b4987"

snapshot = Path(snapshot_download(REPO, revision=REVISION, allow_patterns=["config.json", "kokoro-v1_0.pth", "voices/*.pt"]))
ref = snapshot.parent.parent / "refs" / "main"
ref.parent.mkdir(exist_ok=True)
ref.write_text(REVISION)
print(f"{REPO}@{REVISION} in {snapshot}")
