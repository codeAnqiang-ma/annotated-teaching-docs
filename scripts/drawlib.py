#!/usr/bin/env python3
"""Parameterized tutorial-scene renderer.

compose.py and scenes.py both call render(). Marks are measured boxes;
this module never invents x/y. Scene names accept hyphen or underscore.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFilter, ImageFont

PLATE = (18, 21, 28)
RULE = (42, 48, 56)
BRASS = (212, 162, 74)
INK = (18, 21, 28)
RING = (255, 255, 255)
PAPER = (244, 240, 232)
SOOT = (28, 30, 34)
CRIMSON = (196, 54, 48)
OK = (46, 125, 80)
SUMO_RED = (247, 23, 1)

SCENES = (
    "multi",
    "one",
    "overview",
    "spotlight",
    "arrow",
    "bubble",
    "loupe",
    "click",
    "compare",
    "before_after",
    "banner",
    "redact",
    "path",
    "caption",
    "single",
    "leader",
)

SCENE_ALIASES = {
    "window": "multi",
    "numbered": "multi",
    "one-step": "one",
    "one_step": "one",
    "right-wrong": "compare",
    "right_wrong": "compare",
    "before-after": "before_after",
    "step-banner": "banner",
    "step_banner": "banner",
    "mozilla-red": "single",
    "mozilla_red": "single",
    "red": "single",
    "caption-card": "caption",
    "caption_card": "caption",
}

MAX_MARKS_MULTI = 4
MAX_MARKS_HARD = 6


def skill_dir() -> Path:
    return Path(__file__).resolve().parents[1]


def resolve_scene(name: str | None, meta: dict | None = None) -> str:
    raw = (name or (meta or {}).get("scene") or "multi")
    key = str(raw).strip().lower().replace("-", "_")
    if key in SCENE_ALIASES:
        key = SCENE_ALIASES[key]
    key = key.replace("-", "_")
    if key not in SCENES:
        known = ", ".join(SCENES)
        raise SystemExit(f"unknown scene {raw!r}; use one of: {known}")
    return key


def load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in (
        "/System/Library/Fonts/Menlo.ttc",
        "/System/Library/Fonts/SFNSMono.ttf",
        "/System/Library/Fonts/Supplemental/Courier New.ttf",
        "/Library/Fonts/SF-Mono-Regular.otf",
    ):
        try:
            return ImageFont.truetype(path, size=size, index=0)
        except OSError:
            continue
    return ImageFont.load_default()


def font_cn(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in (
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/STHeiti Light.ttc",
        "/System/Library/Fonts/Hiragino Sans GB.ttc",
    ):
        try:
            return ImageFont.truetype(path, size=size, index=0)
        except OSError:
            continue
    return load_font(size)


def clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def k_of(width: int) -> float:
    return width / 900.0


def scales(width: int) -> dict[str, float]:
    """Size marks so they stay readable when the full window is shown ~900px wide."""
    k = k_of(width)
    return {
        "stroke": max(3, int(round(2.4 * k))),
        "badge_r": max(14, int(round(14 * k))),
        "gap": max(6, int(round(5 * k))),
        "radius": max(3, int(round(3 * k))),
        "gutter": max(16, int(round(10 * k))),
        "tab_w": max(28, int(round(20 * k))),
        "tab_h": max(4, int(round(3 * k))),
        "font": max(16, int(round(16 * k))),
        "k": k,
    }


def scale_marks(meta: dict, im: Image.Image) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Return marks in image pixels. Never invent x/y; only apply space/dpr."""
    marks = meta.get("marks") or []
    if not marks:
        raise SystemExit("meta.marks is empty")

    space = (meta.get("space") or "css").strip().lower()
    vw = float((meta.get("viewport") or {}).get("width") or im.width)
    raw_dpr = (meta.get("viewport") or {}).get("dpr")
    if space == "image":
        dpr = 1.0
    else:
        dpr = float(raw_dpr or (im.width / vw))
        farthest = max(float(m["x"]) + float(m["w"]) for m in marks)
        if farthest > vw * 1.25 and farthest <= im.width + 8:
            print(
                "drawlib: marks look like image pixels; not multiplying by dpr. "
                "Set space=image (from locate.py).",
                file=sys.stderr,
            )
            dpr = 1.0
            space = "image"

    scaled: list[dict[str, Any]] = []
    for i, m in enumerate(marks):
        item = dict(m)
        item["n"] = int(m.get("n") or i + 1)
        item["x"] = float(m["x"]) * dpr
        item["y"] = float(m["y"]) * dpr
        item["w"] = float(m["w"]) * dpr
        item["h"] = float(m["h"]) * dpr
        item["kind"] = (m.get("kind") or "region").strip().lower()
        scaled.append(item)

    for m in scaled:
        if m["x"] + m["w"] < 0 or m["y"] + m["h"] < 0 or m["x"] > im.width or m["y"] > im.height:
            raise SystemExit(f"mark {m['n']} is outside the image — wrong origin or space")

    info = {"dpr": dpr, "space": space, "mode": "window", "marks": len(scaled)}
    return scaled, info


def badge_anchor(
    rect: tuple[float, float, float, float], r: float, w: int, h: int, taken: list
) -> tuple[float, float]:
    x, y, rw, rh = rect
    candidates = [
        (x - r * 0.2, y - r * 0.2),
        (x + rw + r * 0.2, y - r * 0.2),
        (x - r * 0.2, y + rh + r * 0.2),
        (x + rw + r * 0.2, y + rh + r * 0.2),
    ]
    for cx, cy in candidates:
        cx = clamp(cx, r + 4, w - r - 4)
        cy = clamp(cy, r + 4, h - r - 4)
        if all((cx - tx) ** 2 + (cy - ty) ** 2 > (r * 2.4) ** 2 for tx, ty in taken):
            return cx, cy
    return candidates[0]


def plate_of(im: Image.Image, g: int | None = None, tab: bool = True) -> tuple[Image.Image, int]:
    s = scales(im.width)
    if g is None:
        g = int(s["gutter"])
    plate = Image.new("RGB", (im.width + g * 2, im.height + g * 2), PLATE)
    plate.paste(im, (g, g))
    draw = ImageDraw.Draw(plate)
    draw.rectangle(
        [g - 1, g - 1, g + im.width, g + im.height],
        outline=RULE,
        width=max(1, int(s["stroke"] / 3)),
    )
    if tab:
        draw.rectangle([0, 0, int(s["tab_w"]), int(s["tab_h"])], fill=BRASS)
    return plate, g


def hug(
    draw: ImageDraw.ImageDraw,
    box: tuple[float, float, float, float],
    color=BRASS,
    width: int = 6,
    radius: int = 8,
    gap: int = 0,
) -> list[float]:
    x, y, w, h = box
    rect = [x - gap, y - gap, x + w + gap, y + h + gap]
    try:
        draw.rounded_rectangle(rect, radius=radius, outline=color, width=width)
    except TypeError:
        draw.rectangle(rect, outline=color, width=width)
    return rect


def badge(draw: ImageDraw.ImageDraw, cx: float, cy: float, n: str, r: int, fill=BRASS) -> None:
    draw.ellipse([cx - r - 3, cy - r - 3, cx + r + 3, cy + r + 3], fill=RING)
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=fill)
    font = load_font(max(12, int(r * 1.15)))
    bb = draw.textbbox((0, 0), n, font=font)
    tw, th = bb[2] - bb[0], bb[3] - bb[1]
    ink = RING if fill == CRIMSON else INK
    draw.text((cx - tw / 2, cy - th / 2 - bb[1] * 0.15), n, fill=ink, font=font)


def arrow(
    draw: ImageDraw.ImageDraw,
    a: tuple[float, float],
    b: tuple[float, float],
    color=BRASS,
    width: int = 8,
) -> None:
    draw.line([a, b], fill=color, width=width)
    ang = math.atan2(b[1] - a[1], b[0] - a[0])
    s = max(14, width * 2.6)
    p1 = (b[0] - s * math.cos(ang - 0.45), b[1] - s * math.sin(ang - 0.45))
    p2 = (b[0] - s * math.cos(ang + 0.45), b[1] - s * math.sin(ang + 0.45))
    draw.polygon([b, p1, p2], fill=color)


def mosaic(im: Image.Image, box: tuple[float, float, float, float], cell: int = 18) -> None:
    x, y, w, h = [int(round(v)) for v in box]
    x = max(0, x)
    y = max(0, y)
    w = max(1, min(im.width - x, w))
    h = max(1, min(im.height - y, h))
    crop = im.crop((x, y, x + w, y + h))
    small = crop.resize((max(1, w // cell), max(1, h // cell)), Image.Resampling.NEAREST)
    im.paste(small.resize((w, h), Image.Resampling.NEAREST), (x, y))


def area_overlap(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> float:
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    x0, y0 = max(ax, bx), max(ay, by)
    x1, y1 = min(ax + aw, bx + bw), min(ay + ah, by + bh)
    return max(0.0, x1 - x0) * max(0.0, y1 - y0)


def place_away(
    canvas: tuple[int, int],
    avoid: list[tuple[float, float, float, float]],
    w: int,
    h: int,
    pad: int = 24,
) -> tuple[int, int]:
    W, H = canvas
    w = min(w, max(8, W - pad * 2))
    h = min(h, max(8, H - pad * 2))
    xs = [pad, max(pad, (W - w) // 2), max(pad, W - w - pad)]
    ys = [pad, max(pad, (H - h) // 2), max(pad, H - h - pad)]
    candidates = [(x, y) for x in xs for y in ys]
    def score(xy: tuple[int, int]) -> float:
        box = (xy[0], xy[1], w, h)
        return sum(area_overlap(box, a) for a in avoid)
    return min(candidates, key=score)


def _boxes(marks: list[dict], g: int = 0) -> list[tuple[float, float, float, float]]:
    return [(m["x"] + g, m["y"] + g, m["w"], m["h"]) for m in marks]


def _draw_multi(plate: Image.Image, marks: list[dict], g: int, numbered: bool = True) -> Image.Image:
    draw = ImageDraw.Draw(plate)
    s = scales(plate.width)
    stroke = int(s["stroke"])
    r = int(s["badge_r"])
    gap = int(s["gap"])
    taken: list[tuple[float, float]] = []
    for m in marks:
        if m["kind"] == "redact":
            continue
        color = CRIMSON if m["kind"] == "wrong" else OK if m["kind"] == "right" else BRASS
        box = hug(draw, (m["x"] + g, m["y"] + g, m["w"], m["h"]), color=color, width=stroke, radius=int(s["radius"]), gap=gap)
        if numbered:
            cx, cy = badge_anchor((box[0], box[1], m["w"] + gap * 2, m["h"] + gap * 2), r, plate.width, plate.height, taken)
            taken.append((cx, cy))
            badge(draw, cx, cy, str(m["n"]), r, fill=color if m["kind"] in ("wrong", "right") else BRASS)
    return plate


def _scene_multi(im: Image.Image, marks: list[dict], meta: dict, numbered: bool = True) -> Image.Image:
    plate, g = plate_of(im)
    return _draw_multi(plate, marks, g, numbered=numbered)


def _scene_overview(im: Image.Image, marks: list[dict], meta: dict) -> Image.Image:
    k = k_of(im.width)
    left = int(meta.get("label_left") or max(160, 140 * max(1.0, k * 0.35)))
    top = int(meta.get("label_top") or max(56, 48 * max(1.0, k * 0.35)))
    canvas = Image.new("RGB", (im.width + left + 40, im.height + top + 40), PLATE)
    canvas.paste(im, (left, top))
    overlay = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    d = ImageDraw.Draw(canvas)
    d.rectangle([left - 1, top - 1, left + im.width, top + im.height], outline=RULE, width=2)
    chip = font_cn(max(22, int(28 * min(k, 2.2) / max(k, 1.0) * 1.1)))
    if k >= 2:
        chip = font_cn(34)
    for m in marks:
        x, y, w, h = m["x"], m["y"], m["w"], m["h"]
        od.rectangle([left + x, top + y, left + x + w, top + y + h], outline=(*BRASS, 255), width=5)
        od.rectangle([left + x, top + y, left + x + w, top + y + h], fill=(212, 162, 74, 50))
    canvas = Image.alpha_composite(canvas.convert("RGBA"), overlay).convert("RGB")
    d = ImageDraw.Draw(canvas)
    for m in marks:
        label = str(m.get("label") or f"区域 {m['n']}")
        lx = int(left + m["x"] + 16)
        ly = int(top + m["y"] + 16)
        bb = d.textbbox((0, 0), label, font=chip)
        tw, th = bb[2] - bb[0], bb[3] - bb[1]
        d.rounded_rectangle([lx, ly, lx + tw + 28, ly + th + 20], radius=8, fill=PLATE, outline=BRASS, width=3)
        d.text((lx + 14, ly + 8 - bb[1]), label, fill=BRASS, font=chip)
    title = meta.get("title") or meta.get("banner", {}).get("title")
    if title:
        d.text((24, 20), str(title), fill=PAPER, font=font_cn(max(22, int(28 * min(2.0, k)))))
    return canvas


def _scene_leader(im: Image.Image, marks: list[dict], meta: dict) -> Image.Image:
    """Short labels in empty space, thin leaders to controls. Apple / Tango."""
    plate, g = plate_of(im)
    d = ImageDraw.Draw(plate)
    s = scales(im.width)
    stroke = max(2, int(s["stroke"] * 0.6))
    font = font_cn(max(18, int(20 * min(2.0, s["k"]))))
    avoid = _boxes(marks, g)
    for m in marks:
        hug(d, (m["x"] + g, m["y"] + g, m["w"], m["h"]), width=int(s["stroke"]), radius=int(s["radius"]), gap=int(s["gap"]))
        label = str(m.get("label") or m.get("text") or m["n"])
        bb = d.textbbox((0, 0), label, font=font)
        tw, th = bb[2] - bb[0], bb[3] - bb[1]
        pad = 12
        px, py = place_away(plate.size, avoid, tw + pad * 2, th + pad * 2, pad=20)
        box = (px, py, tw + pad * 2, th + pad * 2)
        avoid.append(box)
        d.rounded_rectangle([px, py, px + box[2], py + box[3]], radius=8, fill=PLATE, outline=BRASS, width=2)
        d.text((px + pad, py + pad - bb[1]), label, fill=PAPER, font=font)
        start = (px + box[2] / 2, py + box[3])
        end = (m["x"] + g + m["w"] / 2, m["y"] + g)
        if py > m["y"] + g + m["h"]:
            start = (px + box[2] / 2, py)
            end = (m["x"] + g + m["w"] / 2, m["y"] + g + m["h"])
        d.line([start, end], fill=BRASS, width=stroke)
    return plate


def _scene_spotlight(im: Image.Image, marks: list[dict], meta: dict) -> Image.Image:
    target = next((m for m in marks if m["kind"] != "redact"), marks[0])
    base = im.convert("RGBA")
    x, y, w, h = target["x"], target["y"], target["w"], target["h"]
    pad = 22
    mask = Image.new("L", im.size, 120)
    md = ImageDraw.Draw(mask)
    md.rounded_rectangle([x - pad, y - pad, x + w + pad, y + h + pad], radius=20, fill=0)
    mask = mask.filter(ImageFilter.GaussianBlur(16))
    dark = Image.new("RGBA", im.size, (8, 10, 14, 255))
    dark.putalpha(mask)
    out = Image.alpha_composite(base, dark).convert("RGB")
    plate, g = plate_of(out)
    hug(ImageDraw.Draw(plate), (x + g, y + g, w, h), width=6)
    return plate


def _scene_arrow(im: Image.Image, marks: list[dict], meta: dict) -> Image.Image:
    plate, g = plate_of(im)
    d = ImageDraw.Draw(plate)
    m = marks[0]
    s = scales(im.width)
    hug(d, (m["x"] + g, m["y"] + g, m["w"], m["h"]), width=max(4, int(s["stroke"])), gap=int(s["gap"]))
    end = (m["x"] + g - 8, m["y"] + g + m["h"] / 2)
    start = place_away(plate.size, _boxes(marks, g), 8, 8)
    # prefer a start that is clearly in empty space to the side of the target
    if m["x"] > im.width * 0.45:
        start = (max(g + 20, m["x"] + g - max(180, m["w"])), m["y"] + g + m["h"] / 2 + 40)
    else:
        start = (min(plate.width - 20, m["x"] + g + m["w"] + max(120, m["w"])), m["y"] + g + m["h"] / 2 + 40)
    arrow(d, start, end, width=max(6, int(s["stroke"])))
    return plate


def _scene_bubble(im: Image.Image, marks: list[dict], meta: dict) -> Image.Image:
    plate, g = plate_of(im)
    d = ImageDraw.Draw(plate)
    m = marks[0]
    s = scales(im.width)
    k = max(1.0, min(2.4, s["k"]))
    hug(d, (m["x"] + g, m["y"] + g, m["w"], m["h"]), width=max(4, int(s["stroke"])), gap=int(s["gap"]))
    text = str(m.get("text") or meta.get("bubble") or meta.get("title") or "看这里")
    font = font_cn(max(18, int(22 * min(k, 1.8))))
    pad = max(10, int(16 * min(k, 1.4)))
    bb = d.textbbox((0, 0), text, font=font)
    tw, th = bb[2] - bb[0], bb[3] - bb[1]
    bw, bh = tw + pad * 2, th + pad * 2
    avoid = _boxes(marks, g)
    bx, by = place_away(plate.size, avoid, bw, bh, pad=16)
    box = [bx, by, bx + bw, by + bh]
    d.rounded_rectangle(box, radius=int(10 * min(k, 1.6)), fill=PAPER, outline=BRASS, width=max(3, int(3 * min(k, 1.5))))
    d.text((bx + pad, by + pad - bb[1]), text, fill=INK, font=font)
    tail = (m["x"] + g + 20, m["y"] + g + 8)
    cx = (box[0] + box[2]) / 2
    cy = box[3] if by <= m["y"] + g else box[1]
    if by <= m["y"] + g:
        d.polygon([(cx - 14, box[3]), (cx + 14, box[3]), tail], fill=PAPER)
        d.line([(cx - 14, box[3]), tail, (cx + 14, box[3])], fill=BRASS, width=max(3, int(s["stroke"] * 0.5)))
    else:
        d.polygon([(cx - 14, box[1]), (cx + 14, box[1]), tail], fill=PAPER)
        d.line([(cx - 14, box[1]), tail, (cx + 14, box[1])], fill=BRASS, width=max(3, int(s["stroke"] * 0.5)))
    return plate


def _scene_loupe(im: Image.Image, marks: list[dict], meta: dict) -> Image.Image:
    plate, g = plate_of(im)
    m = marks[0]
    pad = 20
    x, y, w, h = int(m["x"]), int(m["y"]), int(m["w"]), int(m["h"])
    crop = im.crop((max(0, x - pad), max(0, y - pad), min(im.width, x + w + pad), min(im.height, y + h + pad)))
    zoom = float(meta.get("zoom") or 2.4)
    loupe = crop.resize((max(8, int(crop.width * zoom)), max(8, int(crop.height * zoom))), Image.Resampling.LANCZOS)
    px, py = place_away(plate.size, _boxes(marks, g), loupe.width, loupe.height, pad=32)
    shadow = Image.new("RGBA", plate.size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.rounded_rectangle([px + 10, py + 12, px + loupe.width + 10, py + loupe.height + 12], radius=16, fill=(0, 0, 0, 90))
    plate = Image.alpha_composite(plate.convert("RGBA"), shadow).convert("RGB")
    plate.paste(loupe, (px, py))
    d = ImageDraw.Draw(plate)
    d.rounded_rectangle([px, py, px + loupe.width, py + loupe.height], radius=12, outline=BRASS, width=8)
    hug(d, (m["x"] + g, m["y"] + g, m["w"], m["h"]), width=5)
    arrow(d, (m["x"] + g + m["w"] / 2, m["y"] + g + m["h"] + 6), (px + loupe.width / 2, py), width=6)
    return plate


def _scene_click(im: Image.Image, marks: list[dict], meta: dict) -> Image.Image:
    plate, g = plate_of(im)
    m = marks[0]
    d = ImageDraw.Draw(plate)
    hug(d, (m["x"] + g, m["y"] + g, m["w"], m["h"]), width=5)
    cx = m["x"] + g + m["w"] / 2 + 20
    cy = m["y"] + g + m["h"] / 2 + 10
    for rad, alpha in ((46, 40), (30, 70)):
        ring = Image.new("RGBA", plate.size, (0, 0, 0, 0))
        rd = ImageDraw.Draw(ring)
        rd.ellipse([cx - rad, cy - rad, cx + rad, cy + rad], outline=(*BRASS, 180), width=5)
        plate = Image.alpha_composite(plate.convert("RGBA"), ring).convert("RGB")
        d = ImageDraw.Draw(plate)
    pts = [
        (cx + 8, cy + 4),
        (cx + 78, cy + 92),
        (cx + 48, cy + 92),
        (cx + 62, cy + 128),
        (cx + 48, cy + 132),
        (cx + 34, cy + 96),
        (cx + 8, cy + 96),
    ]
    d.polygon(pts, fill=RING, outline=INK)
    return plate


def _scene_compare(im: Image.Image, marks: list[dict], meta: dict) -> Image.Image:
    wrong = next((m for m in marks if m["kind"] == "wrong"), marks[0])
    right = next((m for m in marks if m["kind"] == "right"), marks[-1])
    if wrong is right and len(marks) > 1:
        right = marks[1]

    def one(mark: dict, title: str, color: tuple[int, int, int]) -> Image.Image:
        copy = im.copy()
        d = ImageDraw.Draw(copy)
        hug(d, (mark["x"], mark["y"], mark["w"], mark["h"]), color=color, width=10)
        copy = copy.resize((1500, max(1, int(1500 * copy.height / copy.width))), Image.Resampling.LANCZOS)
        d = ImageDraw.Draw(copy)
        font = font_cn(36)
        bb = d.textbbox((0, 0), title, font=font)
        d.rectangle([0, 0, copy.width, 70], fill=color)
        d.text((20, 16 - bb[1]), title, fill=RING, font=font)
        return copy

    left_title = str(wrong.get("label") or meta.get("wrong_title") or "错")
    right_title = str(right.get("label") or meta.get("right_title") or "对")
    left = one(wrong, left_title, CRIMSON)
    right_im = one(right, right_title, OK)
    gap = 20
    canvas = Image.new("RGB", (left.width + right_im.width + gap + 40, left.height + 64), PLATE)
    canvas.paste(left, (20, 48))
    canvas.paste(right_im, (20 + left.width + gap, 48))
    ImageDraw.Draw(canvas).text(
        (20, 10),
        str(meta.get("title") or "容易点错时左右对照，不要只圈对的"),
        fill=PAPER,
        font=font_cn(26),
    )
    return canvas


def _redact_marks(im: Image.Image, marks: list[dict]) -> Image.Image:
    out = im.copy()
    boxes = [m for m in marks if m["kind"] == "redact"] or marks
    for m in boxes:
        mosaic(out, (m["x"], m["y"], m["w"], m["h"]))
    return out


def _scene_before_after(im: Image.Image, marks: list[dict], meta: dict) -> Image.Image:
    before = im.copy()
    after = _redact_marks(im, marks)

    def card(src: Image.Image, title: str) -> Image.Image:
        src = src.resize((1500, max(1, int(1500 * src.height / src.width))), Image.Resampling.LANCZOS)
        card_h = 64
        out = Image.new("RGB", (src.width, src.height + card_h), PLATE)
        out.paste(src, (0, card_h))
        ImageDraw.Draw(out).text((16, 16), title, fill=PAPER, font=font_cn(32))
        return out

    a = card(before, str(meta.get("before_title") or "发出前"))
    b = card(after, str(meta.get("after_title") or "发出后"))
    gap = 20
    canvas = Image.new("RGB", (a.width + b.width + gap + 40, a.height + 40), PLATE)
    canvas.paste(a, (20, 20))
    canvas.paste(b, (20 + a.width + gap, 20))
    return canvas


def _scene_banner(im: Image.Image, marks: list[dict], meta: dict) -> Image.Image:
    plate, g = plate_of(im)
    bar_h = int(meta.get("banner", {}).get("height") or 120)
    canvas = Image.new("RGB", (plate.width, plate.height + bar_h), PLATE)
    canvas.paste(plate, (0, bar_h))
    d = ImageDraw.Draw(canvas)
    d.rectangle([0, 0, canvas.width, bar_h], fill=SOOT)
    d.rectangle([0, 0, 16, bar_h], fill=BRASS)
    banner = meta.get("banner") or {}
    step = banner.get("step")
    total = banner.get("total")
    step_line = str(banner.get("step_label") or (f"第 {step} 步 / 共 {total} 步" if step and total else "步骤"))
    title = str(banner.get("title") or meta.get("title") or "")
    d.text((40, 16), step_line, fill=BRASS, font=font_cn(28))
    if title:
        d.text((40, 58), title, fill=PAPER, font=font_cn(40))
    s = scales(im.width)
    for m in marks:
        if m["kind"] == "redact":
            continue
        hug(d, (m["x"] + g, m["y"] + g + bar_h, m["w"], m["h"]), width=6, gap=int(s["gap"]))
    return canvas


def _scene_redact(im: Image.Image, marks: list[dict], meta: dict) -> Image.Image:
    redacted = _redact_marks(im, marks)
    plate, g = plate_of(redacted)
    note = meta.get("title") or meta.get("redact_note")
    if note:
        d = ImageDraw.Draw(plate)
        y = plate.height - g - max(36, int(28 * k_of(im.width)))
        d.text((g + 24, max(g, y)), str(note), fill=PAPER, font=font_cn(28))
    return plate


def _scene_path(im: Image.Image, marks: list[dict], meta: dict) -> Image.Image:
    plate, g = plate_of(im)
    d = ImageDraw.Draw(plate)
    s = scales(im.width)
    live = [m for m in marks if m["kind"] != "redact"]
    if len(live) < 2:
        return _draw_multi(plate, live, g)
    pts: list[tuple[float, float]] = []
    for i, m in enumerate(live):
        if i == 0:
            pts.append((m["x"] + g + m["w"] + 8, m["y"] + g + m["h"] / 2))
        elif i == len(live) - 1:
            pts.append((m["x"] + g - 12, m["y"] + g + m["h"] / 2))
        else:
            pts.append((m["x"] + g + m["w"] / 2, m["y"] + g + m["h"] / 2))
    # route via empty header band when marks jump across the window
    if live[0]["x"] + live[0]["w"] < live[-1]["x"] - 80:
        mid_y = g + min(m["y"] for m in live) - 40
        mid_y = max(g + 20, mid_y)
        routed = [pts[0], (pts[0][0] + 40, pts[0][1]), (pts[0][0] + 40, mid_y), (pts[-1][0], mid_y), pts[-1]]
        pts = routed
    d.line(pts, fill=BRASS, width=max(6, int(s["stroke"])), joint="curve")
    arrow(d, pts[-2], pts[-1], width=max(6, int(s["stroke"])))
    r = int(s["badge_r"])
    for m in live:
        hug(d, (m["x"] + g, m["y"] + g, m["w"], m["h"]), width=5, gap=int(s["gap"]))
        badge(d, m["x"] + g, m["y"] + g, str(m["n"]), r)
    return plate


def _scene_caption(im: Image.Image, marks: list[dict], meta: dict) -> Image.Image:
    marked = _scene_multi(im, marks, meta)
    marked = marked.resize((1600, max(1, int(1600 * marked.height / marked.width))), Image.Resampling.LANCZOS)
    side = 72
    intro_h = 210
    live = [m for m in marks if m["kind"] != "redact"]
    legend_h = 40 + 40 * max(1, len(live))
    canvas = Image.new("RGB", (marked.width + side * 2, intro_h + marked.height + legend_h + 40), PAPER)
    d = ImageDraw.Draw(canvas)
    title = str(meta.get("title") or "这一页")
    body_lines = meta.get("intro") or []
    if isinstance(body_lines, str):
        body_lines = [body_lines]
    d.text((side, 36), title, fill=INK, font=font_cn(36))
    body = font_cn(22)
    for i, line in enumerate(body_lines[:3]):
        d.text((side, 88 + i * 34), str(line), fill=(70, 66, 60), font=body)
    canvas.paste(marked, (side, intro_h))
    y = intro_h + marked.height + 24
    for i, m in enumerate(live):
        line = str(m.get("label") or m.get("text") or f"第 {m['n']} 处")
        badge(d, side + 22, y + 28 + i * 40, str(m["n"]), 16)
        d.text((side + 50, y + 14 + i * 40), line, fill=INK, font=body)
    return canvas


def _scene_single(im: Image.Image, marks: list[dict], meta: dict) -> Image.Image:
    plate, g = plate_of(im)
    d = ImageDraw.Draw(plate)
    color = SUMO_RED if str(meta.get("color") or "red").lower() in ("red", "sumo", "#f71701") else BRASS
    if str(meta.get("color") or "").lower() in ("brass", "gold"):
        color = BRASS
    m = marks[0]
    d.rectangle(
        [m["x"] + g - 6, m["y"] + g - 6, m["x"] + g + m["w"] + 6, m["y"] + g + m["h"] + 6],
        outline=color,
        width=8,
    )
    return plate


_SCENE_FNS = {
    "multi": lambda im, marks, meta: _scene_multi(im, marks, meta, numbered=True),
    "one": lambda im, marks, meta: _scene_multi(im, marks[:1] or marks, meta, numbered=True),
    "overview": _scene_overview,
    "leader": _scene_leader,
    "spotlight": _scene_spotlight,
    "arrow": _scene_arrow,
    "bubble": _scene_bubble,
    "loupe": _scene_loupe,
    "click": _scene_click,
    "compare": _scene_compare,
    "before_after": _scene_before_after,
    "banner": _scene_banner,
    "redact": _scene_redact,
    "path": _scene_path,
    "caption": _scene_caption,
    "single": _scene_single,
}


def render(im: Image.Image, meta: dict, scene: str | None = None) -> Image.Image:
    src = im.convert("RGB")
    marks, _info = scale_marks(meta, src)
    kind = resolve_scene(scene, meta)
    return _SCENE_FNS[kind](src, marks, meta)


def compose_to_path(image_path: Path, meta: dict, out_path: Path, scene: str | None = None) -> dict:
    im = Image.open(image_path).convert("RGB")
    marks, info = scale_marks(meta, im)
    kind = resolve_scene(scene, meta)
    if kind == "multi" and len(marks) > MAX_MARKS_MULTI:
        print(
            f"drawlib: {len(marks)} marks on a multi scene; skill default is ≤{MAX_MARKS_MULTI}, split the window.",
            file=sys.stderr,
        )
    if len(marks) > MAX_MARKS_HARD:
        raise SystemExit(f"refusing {len(marks)} marks (hard max {MAX_MARKS_HARD})")
    out = _SCENE_FNS[kind](im, marks, meta)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out.save(out_path, "PNG")
    info.update({"out": str(out_path), "scene": kind, "size": list(out.size)})
    return info
