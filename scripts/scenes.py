#!/usr/bin/env python3
"""Render tutorial-scene specimens from one measured window shot."""

from __future__ import annotations

import math
import sys
from pathlib import Path

from PIL import Image, ImageDraw

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import drawlib

ROOT = Path(__file__).resolve().parents[1]
SRC = Path("/tmp/dify-window.png")
OUT = ROOT / "examples" / "scenes" / "images"

PLATE = (18, 21, 28)
BRASS = (212, 162, 74)
PAPER = (244, 240, 232)

DOCS = (24, 567, 381, 64)
ADD = (3584, 393, 208, 64)
RECALL = (36, 708, 176, 52)
META = (3392, 391, 176, 67)
SEARCH = (720, 393, 520, 64)
ROW1 = (468, 580, 620, 64)


def _box(box: tuple[int, int, int, int], **extra) -> dict:
    x, y, w, h = box
    return {"x": x, "y": y, "w": w, "h": h, **extra}


def _render(src: Image.Image, scene: str, marks: list[dict], **fields) -> Image.Image:
    meta = {"space": "image", "marks": marks, **fields}
    return drawlib.render(src.convert("RGB"), meta, scene=scene)


def save(im: Image.Image, name: str) -> Path:
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / name
    im.save(path, "PNG")
    print(path.name, im.size)
    return path


def scene_overview(src: Image.Image) -> Image.Image:
    return _render(
        src,
        "overview",
        [
            _box((0, 220, 420, 1860), n=1, label="侧栏 · 换页"),
            _box((420, 360, 3380, 160), n=2, label="查找与操作"),
            _box((420, 540, 3380, 720), n=3, label="文件表"),
        ],
        title="这一页三块：先认位置，再动手",
        label_left=280,
        label_top=90,
    )


def scene_multi(src: Image.Image) -> Image.Image:
    return _render(
        src,
        "multi",
        [
            _box(DOCS, n=1),
            _box(ADD, n=2),
            _box(RECALL, n=3),
        ],
    )


def scene_one_step(src: Image.Image) -> Image.Image:
    return _render(src, "one", [_box(ADD, n=2)])


def scene_spotlight(src: Image.Image) -> Image.Image:
    return _render(src, "spotlight", [_box(ADD)])


def scene_arrow(src: Image.Image) -> Image.Image:
    return _render(src, "arrow", [_box(ADD)])


def scene_bubble(src: Image.Image) -> Image.Image:
    return _render(
        src,
        "bubble",
        [_box(ADD, text="点这里导入材料，不要点旁边的元数据")],
    )


def scene_loupe(src: Image.Image) -> Image.Image:
    return _render(src, "loupe", [_box(ADD)])


def scene_click(src: Image.Image) -> Image.Image:
    return _render(src, "click", [_box(ADD)])


def scene_right_wrong(src: Image.Image) -> Image.Image:
    return _render(
        src,
        "compare",
        [
            _box(META, kind="wrong", label="错 · 不要点「元数据」"),
            _box(ADD, kind="right", label="对 · 点「添加文件」"),
        ],
        title="容易点错时左右对照，不要只圈对的",
    )


def scene_before_after(src: Image.Image) -> Image.Image:
    return _render(
        src,
        "before_after",
        [
            _box((500, 575, 720, 520), kind="redact"),
            _box((180, 248, 280, 90), kind="redact"),
        ],
        before_title="发出前 · 文件名还在",
        after_title="发出后 · 名称已打码",
    )


def scene_banner(src: Image.Image) -> Image.Image:
    return _render(
        src,
        "banner",
        [_box(ADD)],
        banner={
            "step": 2,
            "total": 3,
            "title": "点右上角「添加文件」，把材料导进这个知识库",
        },
    )


def scene_redact(src: Image.Image) -> Image.Image:
    return _render(
        src,
        "redact",
        [
            _box((500, 575, 720, 520), kind="redact"),
            _box((180, 248, 280, 90), kind="redact"),
            _box((1680, 148, 420, 56), kind="redact"),
        ],
        title="对外教程：人名、库名、未发布文件名打码",
    )


def scene_path(src: Image.Image) -> Image.Image:
    return _render(
        src,
        "path",
        [
            _box(DOCS, n=1),
            _box(ADD, n=2),
        ],
    )


def scene_caption_card(src: Image.Image) -> Image.Image:
    return _render(
        src,
        "caption",
        [
            _box(DOCS, n=1, label="确认左侧停在「文档」"),
            _box(ADD, n=2, label="点右上「添加文件」导入"),
            _box(RECALL, n=3, label="要试效果再去「召回测试」"),
        ],
        title="把材料推进这个知识库",
        intro=[
            "这一页是文档列表。左侧是知识库菜单，中间是已有文件，",
            "右上才能导入。先确认停在「文档」，再点「添加文件」。",
        ],
    )


def scene_mozilla_red(src: Image.Image) -> Image.Image:
    return _render(src, "single", [_box(ADD)], color="red")


def contact_sheet(paths: list[Path]) -> Image.Image:
    thumbs = []
    tw = 640
    for p in paths:
        im = Image.open(p).convert("RGB")
        th = int(tw * im.height / im.width)
        thumbs.append((p.stem, im.resize((tw, th), Image.Resampling.LANCZOS)))
    cols = 3
    gap = 28
    title_h = 48
    rows = math.ceil(len(thumbs) / cols)
    cell_h = max(t[1].height for t in thumbs) + title_h
    W = cols * tw + (cols + 1) * gap
    H = 80 + rows * (cell_h + gap)
    canvas = Image.new("RGB", (W, H), PLATE)
    d = ImageDraw.Draw(canvas)
    d.text((gap, 24), "同一张 Dify 整窗 · 十五种教程图手法", fill=PAPER, font=drawlib.font_cn(32))
    labels = {
        "01-overview": "1 方位总览",
        "02-multi-number": "2 一图多编号",
        "03-one-step": "3 一图一步",
        "04-spotlight": "4 聚光变暗",
        "05-arrow": "5 箭头指向",
        "06-bubble": "6 气泡说明",
        "07-loupe": "7 局部放大",
        "08-click": "8 点击热区",
        "09-right-wrong": "9 对错对照",
        "10-before-after": "10 操作前后",
        "11-step-banner": "11 步骤条",
        "12-redact": "12 打码",
        "13-path": "13 动线",
        "14-caption-card": "14 介绍+图+图注",
        "15-mozilla-red": "15 红框（SUMO）",
    }
    for i, (stem, im) in enumerate(thumbs):
        r, c = divmod(i, cols)
        x = gap + c * (tw + gap)
        y = 80 + r * (cell_h + gap)
        d.text((x, y), labels.get(stem, stem), fill=BRASS, font=drawlib.font_cn(22))
        canvas.paste(im, (x, y + title_h))
    return canvas


def main() -> None:
    if not SRC.exists():
        raise SystemExit(f"missing source screenshot: {SRC}")
    src = Image.open(SRC).convert("RGB")
    jobs = [
        ("01-overview.png", scene_overview),
        ("02-multi-number.png", scene_multi),
        ("03-one-step.png", scene_one_step),
        ("04-spotlight.png", scene_spotlight),
        ("05-arrow.png", scene_arrow),
        ("06-bubble.png", scene_bubble),
        ("07-loupe.png", scene_loupe),
        ("08-click.png", scene_click),
        ("09-right-wrong.png", scene_right_wrong),
        ("10-before-after.png", scene_before_after),
        ("11-step-banner.png", scene_banner),
        ("12-redact.png", scene_redact),
        ("13-path.png", scene_path),
        ("14-caption-card.png", scene_caption_card),
        ("15-mozilla-red.png", scene_mozilla_red),
    ]
    paths = []
    for name, fn in jobs:
        paths.append(save(fn(src), name))
    save(contact_sheet(paths), "00-contact-sheet.png")


if __name__ == "__main__":
    main()
