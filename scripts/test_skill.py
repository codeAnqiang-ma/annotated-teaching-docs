#!/usr/bin/env python3
"""Self-test for annotated-teaching-docs scripts. No Dify fixture required."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import traceback
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))

import drawlib  # noqa: E402
from drawlib import SCENES, compose_to_path, render, scale_marks, skill_dir  # noqa: E402


def font(size: int):
    for path in (
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/Hiragino Sans GB.ttc",
        "/System/Library/Fonts/Helvetica.ttc",
    ):
        try:
            return ImageFont.truetype(path, size=size, index=0)
        except OSError:
            continue
    return ImageFont.load_default()


def fake_ui(path: Path) -> dict:
    """Synthetic admin window: sidebar + two same buttons + one unique."""
    im = Image.new("RGB", (1200, 800), (32, 36, 44))
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, 220, 800], fill=(22, 24, 30))
    d.rectangle([0, 0, 1200, 56], fill=(18, 20, 26))
    f = font(28)
    d.text((24, 14), "控制台", fill=(240, 236, 228), font=f)
    d.text((36, 120), "文档", fill=(212, 162, 74), font=f)
    d.rounded_rectangle([920, 80, 1160, 140], radius=8, fill=(46, 125, 80))
    d.text((948, 94), "添加文件", fill=(255, 255, 255), font=f)
    d.rounded_rectangle([700, 80, 900, 140], radius=8, fill=(70, 74, 82))
    d.text((740, 94), "元数据", fill=(230, 230, 230), font=f)
    d.rounded_rectangle([260, 200, 420, 252], radius=6, fill=(50, 54, 62))
    d.text((290, 210), "保存", fill=(240, 236, 228), font=f)
    d.rounded_rectangle([460, 200, 620, 252], radius=6, fill=(50, 54, 62))
    d.text((490, 210), "保存", fill=(240, 236, 228), font=f)
    d.rectangle([240, 320, 1160, 760], fill=(40, 44, 52))
    d.text((260, 340), "文件表", fill=(180, 180, 180), font=font(22))
    # private-looking name for redact tests
    d.text((260, 400), "张三的合同.pdf", fill=(220, 220, 220), font=f)
    im.save(path, "PNG")
    marks = {
        "space": "image",
        "viewport": {"width": 1200, "height": 800, "dpr": 1},
        "marks": [
            {"n": 1, "x": 20, "y": 110, "w": 160, "h": 48, "label": "侧栏 · 文档"},
            {"n": 2, "x": 920, "y": 80, "w": 240, "h": 60, "label": "添加文件", "kind": "right"},
            {"n": 3, "x": 700, "y": 80, "w": 200, "h": 60, "label": "元数据", "kind": "wrong"},
        ],
    }
    return marks


class Checks:
    def __init__(self) -> None:
        self.failed: list[str] = []
        self.passed = 0

    def check(self, name: str, cond: bool, detail: str = "") -> None:
        if cond:
            self.passed += 1
            print(f"  ok  {name}")
        else:
            self.failed.append(f"{name}: {detail}")
            print(f"  FAIL {name}  {detail}")

    def expect_raises(self, name: str, fn) -> None:
        try:
            fn()
        except (SystemExit, ValueError, KeyError):
            self.check(name, True)
            return
        self.check(name, False, "expected SystemExit/ValueError")


def run(cmd: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=cwd or SCRIPTS, capture_output=True, text=True)


def test_drawlib(c: Checks, work: Path, marks: dict, src: Path) -> None:
    im = Image.open(src)
    for scene in SCENES:
        meta = dict(marks)
        if scene == "bubble":
            meta = {**marks, "bubble": "别点元数据"}
        if scene == "banner":
            meta = {**marks, "banner": {"step": 2, "total": 3, "title": "点添加文件"}}
        if scene == "redact":
            meta = {
                **marks,
                "marks": [{"n": 1, "x": 250, "y": 390, "w": 280, "h": 50, "kind": "redact"}],
            }
        if scene == "before_after":
            meta = {
                **marks,
                "marks": [{"n": 1, "x": 250, "y": 390, "w": 280, "h": 50, "kind": "redact"}],
            }
        if scene == "path":
            meta = {**marks, "marks": marks["marks"][:2]}
        if scene == "single":
            meta = {**marks, "color": "red", "marks": [marks["marks"][1]]}
        out = render(im, meta, scene)
        dest = work / f"scene-{scene}.png"
        out.save(dest)
        c.check(f"scene {scene} nonempty", out.size[0] >= 200 and out.size[1] >= 200, str(out.size))

    scaled, info = scale_marks(marks, im)
    c.check("scale image space dpr=1", info["dpr"] == 1.0 and info["space"] == "image")
    c.check("scale keeps 3 marks", len(scaled) == 3)

    css = {
        "space": "css",
        "viewport": {"width": 600, "height": 400, "dpr": 2},
        "marks": [{"n": 1, "x": 10, "y": 10, "w": 50, "h": 20}],
    }
    css_im = Image.new("RGB", (1200, 800), (0, 0, 0))
    sc, info2 = scale_marks(css, css_im)
    c.check("css * dpr", abs(sc[0]["x"] - 20) < 0.01 and abs(sc[0]["w"] - 100) < 0.01, str(sc[0]))

    outside = {
        "space": "image",
        "marks": [{"n": 1, "x": 9000, "y": 10, "w": 10, "h": 10}],
    }
    c.expect_raises("outside mark rejected", lambda: scale_marks(outside, im))

    outp = work / "cli-multi.png"
    info3 = compose_to_path(src, marks, outp, scene="multi")
    c.check("compose_to_path writes", outp.is_file() and info3["scene"] == "multi")
    c.check("skill_dir is skill root", (skill_dir() / "SKILL.md").is_file(), str(skill_dir()))

    proc = run(
        [sys.executable, str(SCRIPTS / "compose.py"), "--list-scenes"],
    )
    c.check("compose --list-scenes", proc.returncode == 0 and "multi" in proc.stdout)


def test_locate(c: Checks, work: Path, src: Path) -> None:
    locate = SCRIPTS / "locate.py"
    if not locate.is_file():
        c.check("locate.py exists", False)
        return
    good = run(
        [
            sys.executable,
            str(locate),
            "--image",
            str(src),
            "--find",
            "添加文件",
            "--find",
            "元数据",
            "--out",
            str(work / "loc.json"),
            "--probe-dir",
            str(work / "probes"),
        ]
    )
    c.check("locate unique texts", good.returncode == 0, good.stderr[-400:] + good.stdout[-200:])
    if good.returncode == 0:
        meta = json.loads((work / "loc.json").read_text())
        c.check("locate space=image", meta.get("space") == "image")
        c.check("locate 2 marks", len(meta.get("marks") or []) == 2, str(meta.get("marks")))

    amb = run([sys.executable, str(locate), "--image", str(src), "--find", "保存"])
    c.check("locate ambiguous exits 2", amb.returncode == 2, f"rc={amb.returncode} {amb.stderr[-300:]}")

    nth = run(
        [
            sys.executable,
            str(locate),
            "--image",
            str(src),
            "--find",
            "保存#2",
            "--out",
            str(work / "loc2.json"),
        ]
    )
    c.check("locate 保存#2", nth.returncode == 0, nth.stderr[-300:])
    if nth.returncode == 0:
        m = json.loads((work / "loc2.json").read_text())["marks"][0]
        c.check("locate #2 is the right-hand 保存", m["x"] > 400, str(m))


def test_overlay(c: Checks) -> None:
    js = (SCRIPTS / "overlay.js").read_text()
    html = f"""<!doctype html><meta charset="utf-8">
    <button id="a"><span>添加文件</span></button>
    <button id="b1"><span>保存</span></button>
    <button id="b2"><span>保存</span></button>
    <div id="wrap"><em>文档</em></div>
    <script>{js}</script>"""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        c.check("playwright available", False, "skip overlay")
        return
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 800, "height": 600})
        page.set_content(html)
        nested = page.evaluate("() => teachingQuery('text:添加文件') && teachingQuery('text:添加文件').id")
        c.check("text: matches nested button", nested == "a", str(nested))
        second = page.evaluate("() => teachingQuery('text:保存#2') && teachingQuery('text:保存#2').id")
        c.check("text:保存#2", second == "b2", str(second))
        contains = page.evaluate("() => teachingQuery('text:~文') && teachingQuery('text:~文').id")
        c.check("text:~ contains innermost", contains in ("a", "wrap"), str(contains))
        measured = page.evaluate(
            """() => teachingMeasure([
                {n:1, sel:'text:添加文件'},
                {n:2, sel:'text:保存#2'}
            ])"""
        )
        c.check("measure multi ok", measured.get("ok") is True, str(measured))
        c.check("measure no-scroll still has rects", measured["marks"][0]["w"] > 2, str(measured["marks"][0]))
        missing = page.evaluate("() => teachingMeasure([{n:1, sel:'text:没有这个'}])")
        c.check("missing reason", missing["marks"][0].get("reason") == "missing", str(missing))
        browser.close()


def test_verify(c: Checks, work: Path, marks: dict, src: Path) -> None:
    verify = SCRIPTS / "verify.py"
    if not verify.is_file():
        c.check("verify.py exists", False)
        return
    good_png = work / "v-good.png"
    compose_to_path(src, marks, good_png, scene="multi")
    (work / "marks.json").write_text(json.dumps(marks), encoding="utf-8")
    good = run(
        [
            sys.executable,
            str(verify),
            "--image",
            str(src),
            "--meta",
            str(work / "marks.json"),
            "--composed",
            str(good_png),
        ]
    )
    c.check("verify good exits 0", good.returncode == 0, good.stderr + good.stdout[-400:])
    if good.stdout.strip():
        report = json.loads(good.stdout)
        c.check("verify report ok", report.get("ok") is True, str(report))

    fat = {
        "space": "image",
        "marks": [{"n": 1, "x": 0, "y": 0, "w": 1100, "h": 700}],
    }
    (work / "fat.json").write_text(json.dumps(fat), encoding="utf-8")
    fat_png = work / "v-fat.png"
    compose_to_path(src, fat, fat_png, scene="single")
    bad = run(
        [
            sys.executable,
            str(verify),
            "--image",
            str(src),
            "--meta",
            str(work / "fat.json"),
            "--composed",
            str(fat_png),
        ]
    )
    c.check("verify fat mark fails", bad.returncode == 1, bad.stdout[-300:])


def main() -> int:
    print(f"skill_dir={skill_dir()}")
    c = Checks()
    with tempfile.TemporaryDirectory(prefix="teaching-test-") as raw:
        work = Path(raw)
        src = work / "ui.png"
        marks = fake_ui(src)
        print("== drawlib / compose")
        test_drawlib(c, work, marks, src)
        print("== locate")
        test_locate(c, work, src)
        print("== overlay.js")
        test_overlay(c)
        print("== verify")
        test_verify(c, work, marks, src)
    print(f"\n{c.passed} passed, {len(c.failed)} failed")
    for item in c.failed:
        print(" -", item)
    return 1 if c.failed else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        traceback.print_exc()
        raise SystemExit(2)
