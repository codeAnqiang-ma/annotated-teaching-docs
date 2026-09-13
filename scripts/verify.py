#!/usr/bin/env python3
"""Machine QA gate for annotated screenshots. Run after compose.

Exit 0 if every hard check passes; exit 1 otherwise. Always prints a JSON
report to stdout. Never invents x/y — space/dpr come from drawlib.scale_marks.
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
from typing import Any

from PIL import Image, UnidentifiedImageError

import drawlib
from drawlib import MAX_MARKS_MULTI, resolve_scene, scale_marks, skill_dir

MAX_MARKS_HARD = getattr(drawlib, "MAX_MARKS_HARD", 6)
FAT_AREA = 0.40

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
PHONE_RE = re.compile(
    r"(?<!\d)("
    r"(?:\+86[\s\-]?)?1[3-9]\d{9}"
    r"|(?:\+1[\s\-.]?)?(?:\(?\d{3}\)?[\s\-.]?\d{3}[\s\-.]?\d{4})"
    r"|(?:\+\d{1,3}[\s\-]?)?\d{2,4}[\s\-]\d{3,4}[\s\-]\d{4}"
    r")(?!\d)"
)


def issue(code: str, message: str, n: int | None = None) -> dict[str, Any]:
    item: dict[str, Any] = {"code": code, "message": message}
    if n is not None:
        item["n"] = int(n)
    return item


def open_rgb(path: Path) -> Image.Image:
    im = Image.open(path)
    im.load()
    return im.convert("RGB")


def report_shell(
    *,
    ok: bool,
    errors: list[dict[str, Any]],
    warnings: list[dict[str, Any]],
    space: str,
    dpr: float,
    scene: str,
    marks: int,
) -> dict[str, Any]:
    return {
        "ok": ok,
        "errors": errors,
        "warnings": warnings,
        "space": space,
        "dpr": dpr,
        "scene": scene,
        "marks": marks,
        "skill_dir": str(skill_dir()),
    }


def parse_tsv(text: str) -> list[dict[str, Any]]:
    header = None
    words: list[dict[str, Any]] = []
    for line in text.splitlines():
        parts = line.split("\t")
        if header is None:
            header = parts
            continue
        if len(parts) != len(header):
            continue
        row = dict(zip(header, parts))
        token = (row.get("text") or "").strip()
        if not token:
            continue
        try:
            conf = float(row.get("conf") or -1)
        except ValueError:
            continue
        words.append({"text": token, "conf": conf})
    return words


def ocr_words(png: Path) -> list[dict[str, Any]] | None:
    """OCR one crop. Try chi_sim+eng, then fall back. None if every invoke failed."""
    langs: list[str | None] = ["chi_sim+eng", "eng", "chi_sim", None]
    with tempfile.TemporaryDirectory(prefix="verify-ocr-") as raw:
        work = Path(raw)
        out_base = work / "ocr"
        for lang in langs:
            cmd = ["tesseract", str(png), str(out_base)]
            if lang:
                cmd.extend(["-l", lang])
            cmd.append("tsv")
            proc = subprocess.run(cmd, capture_output=True, text=True)
            tsv = Path(str(out_base) + ".tsv")
            if proc.returncode == 0 and tsv.is_file():
                return parse_tsv(tsv.read_text(errors="replace"))
    return None


def leftover_pii(text: str) -> str | None:
    blob = text.strip()
    if not blob:
        return None
    email = EMAIL_RE.search(blob)
    if email:
        return email.group(0)
    phone = PHONE_RE.search(blob)
    if phone:
        return phone.group(0)
    return None


def clamp_box(
    im: Image.Image, x: float, y: float, w: float, h: float
) -> tuple[int, int, int, int] | None:
    x0 = int(round(x))
    y0 = int(round(y))
    x1 = int(round(x + w))
    y1 = int(round(y + h))
    x0 = max(0, x0)
    y0 = max(0, y0)
    x1 = min(im.width, x1)
    y1 = min(im.height, y1)
    if x1 - x0 < 2 or y1 - y0 < 2:
        return None
    return x0, y0, x1, y1


def composed_origin(
    src: Image.Image, composed: Image.Image, scene: str, meta: dict
) -> tuple[int, int] | None:
    """Map source-pixel marks onto a plated compose output. None if layout is unknown."""
    dw = composed.width - src.width
    dh = composed.height - src.height
    if dw < 0 or dh < 0:
        return None
    k = src.width / 900.0
    if scene == "overview":
        left = int(meta.get("label_left") or max(160, 140 * max(1.0, k * 0.35)))
        top = int(meta.get("label_top") or max(56, 48 * max(1.0, k * 0.35)))
        return left, top
    g = int(drawlib.scales(src.width)["gutter"])
    if scene == "banner":
        bar_h = int((meta.get("banner") or {}).get("height") or 120)
        return g, g + bar_h
    if scene in ("compare", "before_after", "caption"):
        return None
    if dw >= 2 * g - 2 and dh >= 2 * g - 2:
        return g, g
    if dw % 2 == 0 and abs(dw // 2 - dh // 2) <= 2:
        return dw // 2, dh // 2
    return None


def redact_marks(scene: str, marks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if scene == "redact":
        return list(marks)
    return [m for m in marks if (m.get("kind") or "") == "redact"]


def check_redact(
    *,
    src: Image.Image,
    composed: Image.Image | None,
    scene: str,
    meta: dict,
    marks: list[dict[str, Any]],
    errors: list[dict[str, Any]],
    warnings: list[dict[str, Any]],
) -> None:
    boxes = redact_marks(scene, marks)
    if not boxes:
        return
    if not shutil.which("tesseract"):
        warnings.append(issue("ocr-skipped", "tesseract not found; redact OCR skipped"))
        return

    ocr_im = composed
    origin = composed_origin(src, composed, scene, meta) if composed is not None else None
    if ocr_im is None or origin is None:
        ocr_im = src.copy()
        mosaic = getattr(drawlib, "mosaic", None)
        if mosaic is None:
            warnings.append(issue("ocr-skipped", "cannot map redact boxes onto composed output"))
            return
        for m in boxes:
            mosaic(ocr_im, (m["x"], m["y"], m["w"], m["h"]))
        ox, oy = 0, 0
    else:
        ox, oy = origin

    ocr_failed = False
    with tempfile.TemporaryDirectory(prefix="verify-redact-") as raw:
        work = Path(raw)
        for m in boxes:
            box = clamp_box(ocr_im, m["x"] + ox, m["y"] + oy, m["w"], m["h"])
            if box is None:
                continue
            crop = ocr_im.crop(box)
            crop_path = work / f"mark-{m['n']:02d}.png"
            crop.save(crop_path, "PNG")
            words = ocr_words(crop_path)
            if words is None:
                ocr_failed = True
                continue
            joined = " ".join(w["text"] for w in words)
            pii = leftover_pii(joined) or next(
                (leftover_pii(w["text"]) for w in words if leftover_pii(w["text"])),
                None,
            )
            if pii:
                errors.append(
                    issue(
                        "redact-pii",
                        f"mark {m['n']} still shows email/phone after redact: {pii}",
                        n=m["n"],
                    )
                )
                continue
            leftover = next(
                (w for w in words if w["conf"] >= 60 and len(w["text"]) >= 2),
                None,
            )
            if leftover:
                warnings.append(
                    issue(
                        "redact-still-readable",
                        f"mark {m['n']} still readable after redact: {leftover['text']!r}",
                        n=m["n"],
                    )
                )
    if ocr_failed:
        warnings.append(issue("ocr-skipped", "tesseract failed on a redact crop; tried chi_sim+eng then fallback"))


def check_probes(probe_dir: Path, marks: list[dict[str, Any]], warnings: list[dict[str, Any]]) -> None:
    for m in marks:
        name = f"{int(m['n']):02d}.png"
        path = probe_dir / name
        if not path.is_file():
            warnings.append(
                issue("probe-missing", f"missing probe {name} for mark {m['n']}", n=m["n"])
            )


def is_zone_or_overview(mark: dict[str, Any], scene: str) -> bool:
    kind = (mark.get("kind") or "").strip().lower()
    return kind in ("zone", "overview") or scene == "overview"


def try_scale(
    meta: dict, src: Image.Image
) -> tuple[list[dict[str, Any]] | None, dict[str, Any] | None, str | None]:
    try:
        scaled, info = scale_marks(meta, src)
        return scaled, info, None
    except SystemExit as exc:
        return None, None, str(exc) or "scale_marks failed"


def verify(
    image: Path,
    meta: dict,
    composed_path: Path | None,
    probe_dir: Path | None,
) -> dict[str, Any]:
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []

    try:
        scene = resolve_scene(None, meta)
    except SystemExit as exc:
        scene = str((meta or {}).get("scene") or "multi")
        errors.append(issue("unknown-scene", str(exc) or "unknown scene"))

    raw_marks = meta.get("marks") if isinstance(meta, dict) else None
    mark_count = len(raw_marks) if isinstance(raw_marks, list) else 0
    declared_space = str((meta.get("space") if isinstance(meta, dict) else None) or "css").strip().lower()
    space = declared_space
    dpr = 1.0
    src: Image.Image | None = None
    scaled: list[dict[str, Any]] = []

    try:
        src = open_rgb(image)
    except FileNotFoundError:
        errors.append(issue("image-missing", f"source image missing: {image}"))
    except (OSError, UnidentifiedImageError) as exc:
        errors.append(issue("image-unreadable", f"source image unreadable: {image} ({exc})"))

    if not isinstance(raw_marks, list) or not raw_marks:
        errors.append(issue("empty-marks", "meta.marks is empty"))
        return report_shell(
            ok=False,
            errors=errors,
            warnings=warnings,
            space=space,
            dpr=dpr,
            scene=scene,
            marks=mark_count,
        )

    if mark_count > MAX_MARKS_HARD:
        errors.append(
            issue(
                "too-many-marks",
                f"{mark_count} marks exceeds hard max {MAX_MARKS_HARD}",
            )
        )

    if src is not None:
        scaled_or_none, info, scale_err = try_scale(meta, src)
        if info:
            space = str(info.get("space") or space)
            dpr = float(info.get("dpr") or dpr)
        if scale_err:
            n_match = re.search(r"mark\s+(\d+)", scale_err)
            n = int(n_match.group(1)) if n_match else None
            code = "mark-outside" if "outside" in scale_err else "empty-marks"
            errors.append(issue(code, scale_err, n=n))
        elif scaled_or_none is not None:
            scaled = scaled_or_none
            mark_count = len(scaled)
            if declared_space == "css" and space == "image":
                warnings.append(
                    issue(
                        "space-remapped",
                        "space=css but marks already look like image pixels; "
                        "drawlib remapped without multiplying dpr",
                    )
                )
            src_area = float(src.width * src.height)
            for m in scaled:
                if is_zone_or_overview(m, scene):
                    continue
                area = float(m["w"]) * float(m["h"])
                if src_area > 0 and area / src_area > FAT_AREA:
                    pct = area / src_area
                    errors.append(
                        issue(
                            "fat-frame",
                            f"mark {m['n']} covers {pct:.0%} of the source image (>{FAT_AREA:.0%})",
                            n=m["n"],
                        )
                    )
            if scene in ("multi", "one") and mark_count > MAX_MARKS_MULTI:
                warnings.append(
                    issue(
                        "split-window",
                        f"{mark_count} marks on a {scene} scene; split into a second full window",
                    )
                )

    composed: Image.Image | None = None
    if composed_path is None:
        warnings.append(issue("composed-omitted", "--composed omitted"))
    else:
        if not composed_path.is_file():
            errors.append(issue("composed-missing", f"composed path missing: {composed_path}"))
        else:
            try:
                composed = open_rgb(composed_path)
            except (OSError, UnidentifiedImageError) as exc:
                errors.append(
                    issue(
                        "composed-unreadable",
                        f"composed image unreadable: {composed_path} ({exc})",
                    )
                )
            else:
                # caption / compare / before_after letterbox on purpose
                if (
                    src is not None
                    and scene not in ("caption", "compare", "before_after")
                    and composed.width < src.width
                    and composed.height < src.height
                ):
                    errors.append(
                        issue(
                            "composed-smaller",
                            f"composed {composed.width}x{composed.height} is smaller than "
                            f"source {src.width}x{src.height} in both dimensions",
                        )
                    )

    if src is not None and scaled:
        check_redact(
            src=src,
            composed=composed,
            scene=scene,
            meta=meta,
            marks=scaled,
            errors=errors,
            warnings=warnings,
        )
        if probe_dir is not None:
            check_probes(probe_dir, scaled, warnings)

    return report_shell(
        ok=not errors,
        errors=errors,
        warnings=warnings,
        space=space,
        dpr=dpr,
        scene=scene,
        marks=mark_count,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="QA gate for annotated screenshots")
    parser.add_argument("--image", required=True, type=Path)
    parser.add_argument("--meta", required=True, type=Path)
    parser.add_argument("--composed", type=Path)
    parser.add_argument("--probe-dir", type=Path)
    parser.add_argument("--json-out", type=Path)
    args = parser.parse_args()

    errors: list[dict[str, Any]] = []
    meta: dict[str, Any] = {}
    try:
        loaded = json.loads(args.meta.read_text())
        if not isinstance(loaded, dict):
            raise ValueError("meta JSON must be an object")
        meta = loaded
    except FileNotFoundError:
        errors.append(issue("meta-missing", f"meta path missing: {args.meta}"))
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        errors.append(issue("meta-unreadable", f"meta unreadable: {args.meta} ({exc})"))

    if errors:
        report = report_shell(
            ok=False,
            errors=errors,
            warnings=[],
            space="css",
            dpr=1.0,
            scene="multi",
            marks=0,
        )
    else:
        try:
            report = verify(args.image, meta, args.composed, args.probe_dir)
        except Exception as exc:
            report = report_shell(
                ok=False,
                errors=[issue("verify-failed", str(exc))],
                warnings=[],
                space=str(meta.get("space") or "css"),
                dpr=1.0,
                scene=str(meta.get("scene") or "multi"),
                marks=len(meta.get("marks") or []) if isinstance(meta.get("marks"), list) else 0,
            )

    text = json.dumps(report, indent=2, ensure_ascii=False)
    sys.stdout.write(text + "\n")
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(text + "\n", encoding="utf-8")
    raise SystemExit(0 if report.get("ok") else 1)


if __name__ == "__main__":
    main()
