---
name: annotated-teaching-docs
description: >
  为后台 / 控制台 / IDE 写带截图的教学或使用文档：截整窗，按场景选题图
  （总览 / 多编号 / 一步一图 / 放大 / 对错 / 打码等），句子默认留在
  Markdown。用户说写教学文档、使用文档、带截图的说明书、标注截图、
  给这个页面出图、刷新过期截图、how-to with screenshots、annotate
  the UI 时必须用本 skill。不要用 app-docs / guidewright，也不要把
  控件裁成特写小图。
---

# 带标注的教学 / 使用文档

产出两种中文文档（已有仓库就沿用，不要合成一篇）：

| 类型 | 文件 | 写什么 |
|---|---|---|
| 教学 | `教学-*.md` | 为什么这样、看哪里能确认 |
| 使用 | `使用-*.md` | 一步一动作的操作路径 |

**SKILL_DIR** = 本文件 `SKILL.md` 所在目录（可能是 symlink）。用 `scripts/drawlib.py` 的 `skill_dir()`，或本文件相对路径。不要写死 `~/.claude/skills/...`。

视觉、取景、按场景选题图先读 `references/visual.md`。  
对照样张在 `examples/scenes/看效果.md`。  
场景名单：`python3 "$SKILL_DIR/scripts/compose.py" --list-scenes`。`scripts/scenes.py` 只生成 Dify 样张，日常出图用 `compose.py --scene`。

默认一篇教程页 = **介绍写在 Markdown + 整窗图 + 编号框**。黄铜框、默认不变暗、句子留在 Markdown。其它手法按「选题」一节选，不要一张图全堆上。

## 工作流

1. 问清：哪一页 / 哪一窗、写教学还是使用、读者是谁、图放到哪。登录态、真提交：先问用户。
2. 打开界面，等数据出来。视口约 1440×900。关掉无关标签、通知、其它窗口。
3. 列出这张图要标的点。**一图 1–4 个**；超过 4 个拆第二张整窗。硬上限 6，不要硬塞进一张。
4. **先量后截。** 网页和桌面用下面两套互斥配方，原点必须和截图同一套。
5. `compose.py` 合成。脚本不会裁周围界面，也不会替你对齐控件。
6. **每次合成后立刻 verify**，再 Read 每个 probe 和整张合成图。框必须贴在控件上。偏了就重新测量，不许手改 x/y。
7. 正文编号和图像编号对齐。默认图上不写句子；只有「别点旁边那个」才用气泡或引线。
8. **字不能压控件。** 标签、气泡放到空白（侧栏、页眉、图外一圈），用引线指过去。
9. **一指缝只来自 `--pad`。** 默认 12 图像像素（2x 大约 6 CSS 像素）。不要再手加 4–6 CSS 的第二圈。
10. 对外发出的图：人名、库名、未发布文件名打码。
11. `marks.json` 永远写在 png 旁边：`images/NN-section-slug.png` + 同名 `.json`。

## 两套互斥配方

`getBoundingClientRect` 相对 **CSS 视口**。带标题栏的窗口截图原点在窗口左上，会整组错开一个 chrome 高度。所以网页和桌面不要混用截法。

### 网页（`space=css`）

1. 注入 `$SKILL_DIR/scripts/overlay.js`，选择器全部 `teachingMeasure` 通过。
2. 截 **Playwright / 浏览器视口**（和 `getBoundingClientRect` 同一原点）。`space=css`。
3. **不要**对网页用 `screencapture -l`。那是窗口原点，每个框都会偏一个顶栏高度。

文本选择器：`text:添加文件` 精确、最内层、可见；`text:~添加` 包含；`text:保存#2` 第 n 个。一次量多个目标时不要逐个滚动。

### 桌面 / 已有 PNG（`space=image`）

1. `screencapture -l -o`（`-o` 去掉阴影）或用户已有的 PNG。
2. `locate.py --find "..."` → `space=image`。不要再乘 `dpr`。
3. `--find "保存#2"` 取第 2 个命中；同一字符串多个命中且没有 `#n` → 失败，不要猜。确要全收时才用 `--all`。
4. `--lang` 默认 `chi_sim+eng`。`--pad` 默认 12 图像像素。

## 刷新过期截图

1. 打开旧 Markdown，列出全部图。
2. 旁边若已有 `images/NN-*.json`，复用选择器 / `--find` 字符串（坐标不要手改）。
3. 重开同一 URL / 窗口，按原选择器或 `--find` 重新量。
4. compose + verify。
5. Read probes 和合成图。控件挪了就重新量，不要手改 x/y。

## 选题

| 这一步要干什么 | 手法 | `--scene` |
|---|---|---|
| 还不认识这一页 | 方位总览 | `overview` |
| 同一屏连续点几下 | 一图多编号 | `multi`（默认，1–4） |
| 怕乱序 / 下一步换页 | 一图一步 | `one`；长流程加 `banner` |
| 按钮缩了看不清 | 局部放大 | `loupe`（整窗保留） |
| 旁边有个很像的 | 气泡 / 对错 | `bubble` / `compare` |
| 控件挤、要写名字 | 引线短标签 | `leader` |
| 视线要飞到对角 | 箭头 / 动线 | `arrow` / `path` |
| 强调「点下去」 | 点击热区 | `click`（GitHub 不要指针） |
| 状态变了 | 操作前后 | `before_after` |
| 对外发出 | 打码 | `redact` |
| 只标一个目标 | 单框 | `single` |
| 介绍 + 图 + 图注 | 默认教程页排版 | `caption` |
| 聚光变暗 | 四周压暗 | `spotlight`（默认不用） |

聚光变暗：Scribe/Tango 在用，GitHub **禁止**。深色后台尤其容易把整页吃黑，默认不用。  
图上写中文：中文云文档常见；本 skill 默认 **句子在 Markdown**，正文用「如图 (1) / 红框内」对上。画法见 `visual.md`，不要在这里估像素。

## 量与合成

```javascript
// 注入 scripts/overlay.js 后
teachingMeasure([
  { n: 1, sel: 'text:添加文件' },
  { n: 2, sel: 'text:~保存' },
  { n: 3, sel: '[data-testid="send"]' }
])
```

```bash
python3 "$SKILL_DIR/scripts/compose.py" \
  --image IMG --meta marks.json --out OUT.png [--scene multi]
```

`--scene` 也可写在 marks.json 的 `"scene"`。名单：`multi`（默认）、`one`、`overview`、`leader`、`spotlight`、`arrow`、`bubble`、`loupe`、`click`、`compare`、`before_after`、`banner`、`redact`、`path`、`caption`、`single`。

```bash
python3 "$SKILL_DIR/scripts/verify.py" \
  --image IMG --meta marks.json --composed OUT.png --probe-dir DIR
```

```json
{
  "space": "css",
  "scene": "multi",
  "viewport": { "width": 1440, "height": 900, "dpr": 2 },
  "marks": [
    { "n": 1, "x": 16, "y": 80, "w": 200, "h": 36 },
    { "n": 2, "x": 360, "y": 820, "w": 480, "h": 48 }
  ]
}
```

网页 JSON 是 **CSS 像素**（`space=css`），compose 按 `dpr` 乘到图片像素。

```bash
python3 "$SKILL_DIR/scripts/locate.py" \
  --image /tmp/window.png \
  --find "保存#2" \
  --pad 12 \
  --out images/01-save.json \
  --probe-dir /tmp/probes
```

这份是 **图片像素**（`space=image`）。先 Read `probes/01.png`：裁切里要看见完整控件。`teachingPreview` 只供自己核对；交给 compose 的必须是干净整窗图。

## 为什么会偏

| 原因 | 看起来像什么 | 正确做法 |
|---|---|---|
| 对着大图目测 / 让视觉模型估 x,y | 框偏上或切穿按钮 | `teachingMeasure` 或 `locate.py` |
| CSS 像素又乘了一次 dpr，或图片像素当 CSS | 整组框跑到左上或飞出画面 | 网页 `space=css`；locate 保持 `space=image` |
| 网页量视口，却截带标题栏的窗口 | 所有框一起错开一个顶栏高度 | 网页只截浏览器视口，不用 `screencapture -l` |

## 截得准

- 标的是那一个控件，但**图里要留下侧栏、顶栏、主区**。不要为了「好看」把窗口裁没。桌面壁纸、其它 App 可以裁。不要 `fullPage` 长卷，不要只截元素。
- 超过 4 个点拆第二张**整窗**，不是特写。
- Playwright 对元素 handle 做 evaluate，不要用过期坐标。

## 正文

- 控件名用页面可见字，加粗。
- 使用文档：先一句话介绍这一页，再放整窗图，下列表 `(1)` `(2)` `(3)` 跟图对齐。教学文档先讲判断标准，再放图。
- 中文云文档句式可用：「如下图 (1)」「单击图中红框内」。信息不能只出现在图上。
- 需要总览 / 箭头 / 气泡 / 放大 / 对错 / 前后 / 步骤条 / 打码 / 动线时，看 `examples/scenes/看效果.md`，用 `compose.py --scene`。坐标仍必须量。
