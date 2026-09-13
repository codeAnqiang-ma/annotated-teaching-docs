// Injected into the live page. Measure first; do not screenshot until every
// selector returns ok:true and a non-zero rect. Preview L-marks are optional.
//
// Selectors:
//   CSS                 document.querySelector
//   text:添加文件        exact visible innerText (nth=1)
//   text:~添加           visible innerText contains
//   text:保存#2          1-based nth exact
//   text:~保存#2         1-based nth contains
// Trailing # + digits is the index; any other # stays in the phrase.

function teachingClear() {
  document.getElementById("__teaching_overlay__")?.remove();
  return "cleared";
}

function teachingNormText(s) {
  return String(s || "").replace(/\s+/g, " ").trim();
}

function teachingParseIndex(raw) {
  const m = String(raw).match(/#(\d+)$/);
  if (!m) return { text: raw, nth: 1 };
  return { text: raw.slice(0, m.index), nth: parseInt(m[1], 10) };
}

function teachingParseSel(sel) {
  const s = String(sel);
  if (!s.startsWith("text:")) {
    return { type: "css", css: s };
  }
  let body = s.slice(5).trim();
  let contains = false;
  if (body.startsWith("~")) {
    contains = true;
    body = body.slice(1);
  }
  const parsed = teachingParseIndex(body);
  return {
    type: "text",
    needle: teachingNormText(parsed.text),
    contains,
    nth: parsed.nth,
  };
}

function teachingElText(el) {
  return teachingNormText(el.innerText);
}

function teachingTextMatches(el, needle, contains) {
  if (!needle) return false;
  const t = teachingElText(el);
  if (!t) return false;
  return contains ? t.includes(needle) : t === needle;
}

function teachingLiftSameText(el) {
  const t = teachingElText(el);
  let cur = el;
  while (cur.parentElement && teachingElText(cur.parentElement) === t) {
    cur = cur.parentElement;
  }
  return cur;
}

function teachingTextCandidates(needle, contains) {
  if (!needle || !document.body) return [];
  const all = [document.body, ...document.body.querySelectorAll("*")];
  const matches = all.filter((el) => teachingTextMatches(el, needle, contains));
  const innermost = matches.filter(
    (el) => !matches.some((other) => other !== el && el.contains(other))
  );
  const lifted = [];
  const seen = new Set();
  for (const el of innermost) {
    const top = teachingLiftSameText(el);
    if (seen.has(top)) continue;
    seen.add(top);
    lifted.push(top);
  }
  return lifted;
}

function teachingResolve(sel) {
  const parsed = teachingParseSel(sel);
  if (parsed.type === "css") {
    const el = document.querySelector(parsed.css);
    return { el, hits: el ? 1 : 0, nth: 1, text: false };
  }
  const cands = teachingTextCandidates(parsed.needle, parsed.contains);
  const el = parsed.nth >= 1 && parsed.nth <= cands.length ? cands[parsed.nth - 1] : null;
  return { el, hits: cands.length, nth: parsed.nth, text: true };
}

function teachingQuery(sel) {
  return teachingResolve(sel).el;
}

function teachingShouldScroll(specs, options) {
  const opt = options || {};
  if (opt.scroll === false) return false;
  if (opt.scroll === true) return true;
  return specs.length === 1;
}

function teachingMeasure(specs, options) {
  const items = [];
  if (teachingShouldScroll(specs, options) && specs.length) {
    const first = teachingResolve(specs[0].sel);
    if (first.el) first.el.scrollIntoView({ block: "center", inline: "nearest" });
  }
  for (const spec of specs) {
    const resolved = teachingResolve(spec.sel);
    const el = resolved.el;
    if (!el) {
      if (resolved.text && resolved.hits > 0) {
        items.push({
          n: spec.n,
          sel: spec.sel,
          ok: false,
          reason: "nth-out-of-range",
          hits: resolved.hits,
        });
      } else {
        items.push({ n: spec.n, sel: spec.sel, ok: false, reason: "missing" });
      }
      continue;
    }
    const r = el.getBoundingClientRect();
    if (r.width < 2 || r.height < 2) {
      items.push({ n: spec.n, sel: spec.sel, ok: false, reason: "zero-rect" });
      continue;
    }
    items.push({
      n: spec.n,
      sel: spec.sel,
      ok: true,
      kind: spec.kind || "region",
      x: r.left,
      y: r.top,
      w: r.width,
      h: r.height,
    });
  }
  const failed = items.filter((i) => !i.ok);
  return {
    ok: failed.length === 0,
    viewport: {
      width: window.innerWidth,
      height: window.innerHeight,
      dpr: window.devicePixelRatio || 1,
    },
    marks: items,
    failed,
  };
}

function teachingPreview(specs) {
  teachingClear();
  const measured = teachingMeasure(specs, { scroll: false });
  if (!measured.ok) return measured;
  const root = document.createElement("div");
  root.id = "__teaching_overlay__";
  Object.assign(root.style, {
    position: "fixed",
    inset: "0",
    zIndex: "2147483647",
    pointerEvents: "none",
  });
  for (const m of measured.marks) {
    const box = document.createElement("div");
    const pad = 5;
    Object.assign(box.style, {
      position: "fixed",
      left: m.x - pad + "px",
      top: m.y - pad + "px",
      width: m.w + pad * 2 + "px",
      height: m.h + pad * 2 + "px",
      border: "1.5px solid #D4A24A",
      borderRadius: "0",
      boxSizing: "border-box",
    });
    root.appendChild(box);
  }
  document.body.appendChild(root);
  return measured;
}
