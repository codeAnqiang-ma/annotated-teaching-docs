#!/usr/bin/env python3
"""Build the redacted Dify document-list tutorial figures."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent
SKILL = HERE.parents[1]
SRC = Path("/tmp/dify-window.png")
OUT = HERE / "images"
COMPOSE = SKILL / "scripts" / "compose.py"
SCENES = SKILL / "scripts" / "scenes.py"

# Measured on the 3840×2160 window capture. Image pixels.
REDACT = [
    (140, 0, 3680, 126),      # tabs + URL (ids, other titles)
    (168, 150, 400, 58),      # workspace name
    (1920, 150, 400, 58),     # header knowledge-base name
    (20, 292, 400, 210),      # sidebar library title + QA note
    (548, 575, 420, 530),     # document titles
    (3728, 148, 100, 64),     # account chip
]


def mosaic(im: Image.Image, box: tuple[int, int, int, int], cell: int = 16) -> None:
    x, y, w, h = box
    crop = im.crop((x, y, x + w, y + h))
    small = crop.resize((max(1, w // cell), max(1, h // cell)), Image.Resampling.NEAREST)
    im.paste(small.resize((w, h), Image.Resampling.NEAREST), (x, y))


def load_mod(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main() -> None:
    im = Image.open(SRC).convert("RGB")
    for box in REDACT:
        mosaic(im, box)
    redacted = Path("/tmp/dify-docs-redacted.png")
    im.save(redacted)
    OUT.mkdir(parents=True, exist_ok=True)

    scenes = load_mod(SCENES, "scenes")
    compose = load_mod(COMPOSE, "compose")

    scenes.scene_overview(im).save(OUT / "01-overview.png")

    meta = {
        "space": "image",
        "viewport": {"width": im.width, "height": im.height, "dpr": 1},
        "marks": [
            {"n": 1, "x": 24, "y": 567, "w": 381, "h": 64},
            {"n": 2, "x": 3584, "y": 393, "w": 208, "h": 64},
            {"n": 3, "x": 36, "y": 708, "w": 176, "h": 52},
        ],
    }
    Path("/tmp/dify-docs-actions.json").write_text(json.dumps(meta, indent=2))
    compose.compose(redacted, meta, OUT / "02-actions.png")
    scenes.scene_right_wrong(im).save(OUT / "03-add-not-meta.png")

    # probe redacted name column — must not be readable
    im.crop((548, 575, 968, 1105)).save("/tmp/probe-redact-names.png")
    im.crop((160, 148, 580, 214)).save("/tmp/probe-redact-ws.png")
    print("wrote", OUT)
    for p in sorted(OUT.glob("*.png")):
        print(p.name, Image.open(p).size)


if __name__ == "__main__":
    sys.exit(main() or 0)
