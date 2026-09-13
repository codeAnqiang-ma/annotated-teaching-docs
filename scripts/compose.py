#!/usr/bin/env python3
"""Annotate a full app-window screenshot.

Default scene is `multi`: hug-rects and numbered badges. Other scenes
(--scene overview / loupe / compare / …) are the same measured marks,
rendered by drawlib. Never invent x/y by looking at the PNG.

Coordinate space:
- space=css (default): teachingMeasure / getBoundingClientRect, times dpr
- space=image: already image pixels from locate.py; do not scale
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from drawlib import SCENES, compose_to_path, render, resolve_scene, skill_dir


def compose(image_path: Path, meta: dict, out_path: Path, scene: str | None = None) -> dict:
    return compose_to_path(Path(image_path), meta, Path(out_path), scene=scene)


def main() -> None:
    p = argparse.ArgumentParser(description="Annotate a full-window screenshot")
    p.add_argument("--image", type=Path)
    p.add_argument("--meta", type=Path)
    p.add_argument("--out", type=Path)
    p.add_argument("--scene", help=f"one of: {', '.join(SCENES)} (or meta.scene)")
    p.add_argument("--list-scenes", action="store_true")
    args = p.parse_args()
    if args.list_scenes:
        print("\n".join(SCENES))
        print(f"skill_dir={skill_dir()}", file=sys.stderr)
        return
    if not args.image or not args.meta or not args.out:
        p.error("--image, --meta and --out are required unless --list-scenes")
    meta = json.loads(args.meta.read_text())
    info = compose(args.image, meta, args.out, scene=args.scene)
    info["scene"] = resolve_scene(args.scene, meta)
    json.dump(info, sys.stdout, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
