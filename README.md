# annotated-teaching-docs

给后台、控制台、IDE 写**带标注截图**的教学 / 使用文档。默认交整窗，编号贴在控件上，句子留在 Markdown。框是量出来的，不是对着 PNG 估的。

这是一份给 Agent 用的 [Agent Skill](https://github.com/anthropics/skills)：把 `SKILL.md` 放到 skills 目录后，写说明书、标注截图、刷新过期图时会走这套流程。

## 下载、安装、使用

完整步骤（含真实标注图）见：

- [使用：下载、安装、使用](docs/使用-下载安装使用.md)
- [教学：为什么先量后画](docs/教学-为什么先量后画.md)

十六种手法的街头样张：

- [使用：十六种标注手法](examples/street-github/使用-十六种标注手法.md)（真实 GitHub 仓库页）
- [教程图对照](examples/scenes/看效果.md)

## 最快试一枪

依赖：Python 3.9+、[Pillow](https://pypi.org/project/Pillow/)、[Tesseract](https://github.com/tesseract-ocr/tesseract)（`chi_sim+eng`）。网页量点还要 Playwright。

```bash
git clone https://github.com/codeAnqiang-ma/annotated-teaching-docs.git
cd annotated-teaching-docs
pip3 install -r requirements.txt
python3 scripts/test_skill.py
python3 scripts/compose.py --list-scenes
```

装进 Cursor / Claude Code / Codex：

```bash
git clone https://github.com/codeAnqiang-ma/annotated-teaching-docs.git \
  ~/.claude/skills/annotated-teaching-docs
```

`SKILL_DIR` 就是这份仓库的根目录（`SKILL.md` 所在处）。不要写死 `~/.claude/skills/...`。

## 日常出图

网页：注入 `scripts/overlay.js` → `teachingMeasure` 通过 → 截**浏览器视口** → `space=css`。

桌面 / 现成 PNG：`scripts/locate.py --find "屏幕上的字"` → `space=image`。

```bash
python3 scripts/compose.py --image window.png --meta marks.json --out 01-overview.png --scene multi
python3 scripts/verify.py --image window.png --meta marks.json --composed 01-overview.png
```

`--scene`：`multi`（默认）、`one`、`overview`、`leader`、`spotlight`、`arrow`、`bubble`、`loupe`、`click`、`compare`、`before_after`、`banner`、`redact`、`path`、`caption`、`single`。

## 文档两种

| 类型 | 文件 | 写什么 |
|---|---|---|
| 教学 | `教学-*.md` | 为什么这样、看哪里能确认 |
| 使用 | `使用-*.md` | 一步一动作的操作路径 |

已有仓库就沿用，不要合成一篇。默认一页 = 介绍写在 Markdown + 整窗图 + 编号框。

## 许可

MIT。`examples/scenes/refs/` 里是各家公开文档的对照截图，只作取景研究，不表示那些产品属于本仓库。
