#!/usr/bin/env python3
"""Find on-screenshot boxes from OCR. Never eyeball x/y.

Marks are image pixels (space=image). compose.py must not multiply them by dpr.

--find "添加文件" boxes that phrase. --find "保存#2" is the 2nd hit (1-based).
A trailing # + digits is the index; any other # stays in the phrase.
Several hits and no #n: print candidates on stderr and exit 2 (or pass --all).
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

_FIND_INDEX = re.compile(r"#(\d+)$")


def norm(s: str) -> str:
    return re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "", s.lower())


def parse_find(spec: str) -> tuple[str, int | None]:
    """Split '保存#2' → ('保存', 2). 'foo#bar' is the whole phrase."""
    m = _FIND_INDEX.search(spec)
    if not m:
        return spec, None
    return spec[: m.start()], int(m.group(1))


def _parse_tsv(tsv: str) -> list[dict]:
    header = None
    words = []
    for line in tsv.splitlines():
        parts = line.split("\t")
        if header is None:
            header = parts
            continue
        if len(parts) != len(header):
            continue
        d = dict(zip(header, parts))
        text = (d.get("text") or "").strip()
        if not text:
            continue
        try:
            conf = float(d.get("conf") or -1)
        except ValueError:
            continue
        if conf < 20:
            continue
        words.append(
            {
                "text": text,
                "x": int(d["left"]),
                "y": int(d["top"]),
                "w": int(d["width"]),
                "h": int(d["height"]),
                "conf": conf,
            }
        )
    return words


def tesseract_words(image: Path, lang: str = "chi_sim+eng") -> list[dict]:
    if not shutil.which("tesseract"):
        raise SystemExit("tesseract not found. brew install tesseract")
    work = Path(tempfile.mkdtemp(prefix="locate-"))
    src = work / "in.png"
    shutil.copy2(image, src)
    out_base = work / "ocr"
    last_err: subprocess.CalledProcessError | None = None
    tried: list[str | None] = []
    for cand in (lang or None, "eng", "chi_sim", None):
        if cand in tried:
            continue
        tried.append(cand)
        cmd = ["tesseract", str(src), str(out_base)]
        if cand:
            cmd.extend(["-l", cand])
        cmd.append("tsv")
        try:
            subprocess.run(cmd, check=True, capture_output=True, text=True)
        except subprocess.CalledProcessError as e:
            last_err = e
            continue
        tsv_path = work / "ocr.tsv"
        if not tsv_path.exists():
            continue
        if cand != (lang or None):
            label = cand if cand else "default (no -l)"
            print(f"tesseract -l {lang} failed; using {label}", file=sys.stderr)
        return _parse_tsv(tsv_path.read_text(errors="replace"))
    if last_err is not None:
        raise SystemExit(f"tesseract failed: {last_err.stderr or last_err.stdout}") from last_err
    raise SystemExit("tesseract failed: no output")


def _overlap_frac(a: dict, b: dict) -> float:
    x0 = max(a["x"], b["x"])
    y0 = max(a["y"], b["y"])
    x1 = min(a["x"] + a["w"], b["x"] + b["w"])
    y1 = min(a["y"] + a["h"], b["y"] + b["h"])
    inter = max(0, x1 - x0) * max(0, y1 - y0)
    area = min(a["w"] * a["h"], b["w"] * b["h"])
    return inter / area if area else 0.0


def _merge_words(primary: list[dict], extra: list[dict]) -> list[dict]:
    """Keep primary glyphs; add extra boxes that do not sit on the same ink."""
    out = list(primary)
    for w in extra:
        if any(_overlap_frac(w, p) > 0.3 for p in primary):
            continue
        out.append(w)
    return out


def _binarize_png(image: Path, dest: Path) -> None:
    from PIL import Image

    dest.parent.mkdir(parents=True, exist_ok=True)
    Image.open(image).convert("L").point(lambda p: 255 if p > 160 else 0).save(dest)


def collect_words(image: Path, lang: str = "chi_sim+eng") -> list[dict]:
    """OCR the screenshot, then a binarized copy so colored-button glyphs are not dropped."""
    primary = tesseract_words(image, lang)
    work = Path(tempfile.mkdtemp(prefix="locate-bw-"))
    bw = work / "bw.png"
    try:
        _binarize_png(image, bw)
        extra = tesseract_words(bw, lang)
    except SystemExit:
        return primary
    return _merge_words(primary, extra)


def union(rects: list[dict]) -> dict:
    x0 = min(r["x"] for r in rects)
    y0 = min(r["y"] for r in rects)
    x1 = max(r["x"] + r["w"] for r in rects)
    y1 = max(r["y"] + r["h"] for r in rects)
    return {"x": x0, "y": y0, "w": x1 - x0, "h": y1 - y0}


def _same_line_ok(prev: dict, w: dict) -> bool:
    if abs(w["y"] - prev["y"]) > max(prev["h"], w["h"]) * 1.4:
        return False
    if w["x"] < prev["x"] - 4:
        return False
    gap = w["x"] - (prev["x"] + prev["w"])
    if gap > max(prev["h"], w["h"]) * 3:
        return False
    return True


def find_all_phrases(words: list[dict], phrase: str) -> list[dict]:
    """Non-overlapping hits in reading order. Each hit: x,y,w,h,conf,found."""
    target = norm(phrase)
    if not target:
        return []
    n = len(words)
    hits: list[dict] = []
    i = 0
    while i < n:
        acc = ""
        used: list[dict] = []
        matched: dict | None = None
        for j in range(i, n):
            w = words[j]
            if used and not _same_line_ok(used[-1], w):
                break
            acc += w["text"]
            used.append(w)
            if norm(acc) == target:
                box = union(used)
                confs = [u["conf"] for u in used]
                matched = {
                    **box,
                    "conf": sum(confs) / len(confs),
                    "found": "".join(u["text"] for u in used),
                }
                i = j + 1
                break
            if len(norm(acc)) > len(target):
                break
        if matched:
            hits.append(matched)
        else:
            i += 1
    return hits


def find_phrase(words: list[dict], phrase: str) -> dict | None:
    hits = find_all_phrases(words, phrase)
    if not hits:
        return None
    h = hits[0]
    return {"x": h["x"], "y": h["y"], "w": h["w"], "h": h["h"]}


def expand(rect: dict, pad: int, bounds: tuple[int, int]) -> dict:
    x = max(0, rect["x"] - pad)
    y = max(0, rect["y"] - pad)
    x1 = min(bounds[0], rect["x"] + rect["w"] + pad)
    y1 = min(bounds[1], rect["y"] + rect["h"] + pad)
    return {"x": x, "y": y, "w": x1 - x, "h": y1 - y}


def probe(image: Path, marks: list[dict], dest: Path) -> None:
    from PIL import Image

    dest.mkdir(parents=True, exist_ok=True)
    im = Image.open(image)
    for m in marks:
        crop = im.crop((m["x"], m["y"], m["x"] + m["w"], m["y"] + m["h"]))
        path = dest / f"{m['n']:02d}.png"
        crop.save(path)
        print(f"probe {path}  {m['w']}x{m['h']}", file=sys.stderr)


def _print_candidates(spec: str, phrase: str, hits: list[dict]) -> None:
    print(
        f"ambiguous {spec!r}: {len(hits)} hits; use --find '{phrase}#N' or --all",
        file=sys.stderr,
    )
    for i, h in enumerate(hits, 1):
        print(
            f'{i:2d}  {h["conf"]:5.1f}  {h["x"]:5d},{h["y"]:5d}  '
            f'{h["w"]:4d}x{h["h"]:3d}  {h["found"]}',
            file=sys.stderr,
        )


def main() -> None:
    p = argparse.ArgumentParser(description="OCR-locate marks on a screenshot")
    p.add_argument("--image", required=True, type=Path)
    p.add_argument(
        "--find",
        action="append",
        default=[],
        help='Visible text to box. "保存#2" is the 2nd hit (1-based). '
        "Only a trailing # plus digits is the index.",
    )
    p.add_argument(
        "--pad",
        type=int,
        default=12,
        help="Image-pixel air around glyphs (default 12; ≈6 CSS px at 2x). "
        "A little air, not flush and not a fat frame",
    )
    p.add_argument("--out", type=Path, help="Write marks.json (space=image)")
    p.add_argument("--probe-dir", type=Path, help="Save each box crop for Read-check")
    p.add_argument("--dump", action="store_true", help="Print every OCR word")
    p.add_argument(
        "--lang",
        default="chi_sim+eng",
        help="Tesseract -l languages (default chi_sim+eng). "
        "Falls back to eng, then chi_sim, then no -l.",
    )
    p.add_argument(
        "--all",
        action="store_true",
        help="Emit every hit for each --find as consecutive marks 1..n globally. "
        "Without --all, a phrase with several hits and no #n exits 2.",
    )
    args = p.parse_args()

    from PIL import Image

    im = Image.open(args.image)
    words = collect_words(args.image, args.lang)
    if args.dump or not args.find:
        for w in words:
            print(f'{w["conf"]:5.1f}  {w["x"]:5d},{w["y"]:5d}  {w["w"]:4d}x{w["h"]:3d}  {w["text"]}')
        if not args.find:
            return

    planned: list[dict] = []
    missing: list[str] = []
    ambiguous: list[tuple[str, str, list[dict]]] = []

    for spec in args.find:
        phrase, nth = parse_find(spec)
        hits = find_all_phrases(words, phrase)
        if nth is not None:
            if nth < 1 or nth > len(hits):
                missing.append(spec)
                continue
            chosen = [hits[nth - 1]]
        elif not hits:
            missing.append(spec)
            continue
        elif len(hits) > 1 and not args.all:
            ambiguous.append((spec, phrase, hits))
            continue
        else:
            chosen = hits
        planned.extend(chosen)

    if ambiguous:
        for spec, phrase, hits in ambiguous:
            _print_candidates(spec, phrase, hits)
        if missing:
            print("not found: " + ", ".join(missing), file=sys.stderr)
        raise SystemExit(2)

    if missing:
        raise SystemExit("not found: " + ", ".join(missing))

    marks = []
    for i, hit in enumerate(planned, 1):
        box = expand(hit, args.pad, (im.width, im.height))
        marks.append({"n": i, **box, "found": hit.get("found") or ""})

    meta = {
        "space": "image",
        "viewport": {"width": im.width, "height": im.height, "dpr": 1},
        "marks": [{k: m[k] for k in ("n", "x", "y", "w", "h")} for m in marks],
    }
    text = json.dumps(meta, indent=2, ensure_ascii=False)
    if args.out:
        args.out.write_text(text + "\n")
    print(text)
    if args.probe_dir:
        probe(args.image, marks, args.probe_dir)


if __name__ == "__main__":
    main()
