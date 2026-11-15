"""Draw the evaluation charts and diagrams as PNG (light and dark) from metrics.json.

Usage: python render.py <in_dir> <out_dir>
Coordinates are CSS-like px (origin top-left); images are written at 2x.
"""
import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.font_manager import FontProperties  # noqa: E402
from matplotlib.patches import Circle, PathPatch  # noqa: E402
from matplotlib.path import Path as MPath  # noqa: E402
from matplotlib.textpath import TextPath  # noqa: E402

IN, OUT = Path(sys.argv[1]), Path(sys.argv[2])
OUT.mkdir(parents=True, exist_ok=True)
M = json.loads((IN / "metrics.json").read_text())
RUNS = json.loads((IN / "runs_ran.json").read_text())

PT = 0.72  # 1 px = 0.01 in = 0.72 pt
FAMILY = "DejaVu Sans"

THEMES = {
    "light": {
        "surface": "#fcfcfb", "box": "#f3f2ee", "ink1": "#0b0b0b", "ink2": "#52514e", "muted": "#898781",
        "grid": "#e1e0d9", "axis": "#c3c2b7", "boxline": "#dcdbd4",
        "s": ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"],
        "dark_label_on": {"#eda100", "#fab219"},
        "neutral": "#898781", "wash": "#eaf2fc",
    },
    "dark": {
        "surface": "#1a1a19", "box": "#242423", "ink1": "#f0efec", "ink2": "#c3c2b7", "muted": "#898781",
        "grid": "#2c2c2a", "axis": "#383835", "boxline": "#3a3a37",
        "s": ["#3987e5", "#d95926", "#199e70", "#c98500", "#d55181", "#0ca30c", "#9085e9", "#e66767"],
        "dark_label_on": {"#fab219"},
        "neutral": "#6e6d68", "wash": "#1c2a3c",
    },
}
STATUS = {"good": "#0ca30c", "warning": "#fab219", "serious": "#ec835a", "critical": "#d03b3b"}


def label_on(t, fill):
    return "#0b0b0b" if fill in t["dark_label_on"] else "#ffffff"


class Canvas:
    def __init__(self, W, H, t):
        self.W, self.H, self.t = W, H, t
        self.fig = plt.figure(figsize=(W / 100, H / 100), dpi=200)
        self.ax = self.fig.add_axes([0, 0, 1, 1])
        self.ax.set_xlim(0, W)
        self.ax.set_ylim(H, 0)
        self.ax.axis("off")
        self.fig.patch.set_facecolor(t["surface"])

    @staticmethod
    def measure(s, size=13, weight="normal"):
        fp = FontProperties(family=FAMILY, weight=weight)
        return TextPath((0, 0), s, size=size * PT, prop=fp).get_extents().width / PT

    def wrap(self, s, size, maxw, weight="normal"):
        lines, cur = [], ""
        for word in s.split():
            trial = (cur + " " + word).strip()
            if self.measure(trial, size, weight) <= maxw or not cur:
                cur = trial
            else:
                lines.append(cur)
                cur = word
        if cur:
            lines.append(cur)
        return lines

    def rrect(self, x, y, w, h, fill, r=4, corners=("tl", "tr", "br", "bl"), z=2, edge=None, lw=0, ls="-", alpha=1.0):
        if w <= 0 or h <= 0:
            return
        r = min(r, w / 2, h / 2)
        c = {k: (r if k in corners else 0) for k in ("tl", "tr", "br", "bl")}
        V, C = [(x + c["tl"], y)], [MPath.MOVETO]
        V.append((x + w - c["tr"], y)); C.append(MPath.LINETO)
        if c["tr"]:
            V += [(x + w, y), (x + w, y + c["tr"])]; C += [MPath.CURVE3] * 2
        V.append((x + w, y + h - c["br"])); C.append(MPath.LINETO)
        if c["br"]:
            V += [(x + w, y + h), (x + w - c["br"], y + h)]; C += [MPath.CURVE3] * 2
        V.append((x + c["bl"], y + h)); C.append(MPath.LINETO)
        if c["bl"]:
            V += [(x, y + h), (x, y + h - c["bl"])]; C += [MPath.CURVE3] * 2
        V.append((x, y + c["tl"])); C.append(MPath.LINETO)
        if c["tl"]:
            V += [(x, y), (x + c["tl"], y)]; C += [MPath.CURVE3] * 2
        V.append((x + c["tl"], y)); C.append(MPath.CLOSEPOLY)
        self.ax.add_patch(PathPatch(MPath(V, C), facecolor=fill, edgecolor=edge or "none", linewidth=lw * PT,
                                    linestyle=ls, zorder=z, alpha=alpha))

    def text(self, x, y, s, size=13, color=None, weight="normal", ha="left", va="baseline", z=5, style="normal"):
        self.ax.text(x, y, s, fontsize=size * PT, color=color or self.t["ink1"], fontweight=weight, ha=ha, va=va,
                     family=FAMILY, zorder=z, fontstyle=style)

    def lines(self, x, y, lines, size=13, lh=None, **kw):
        lh = lh or size * 1.4
        for i, s in enumerate(lines):
            self.text(x, y + i * lh, s, size=size, **kw)
        return y + len(lines) * lh

    def line(self, x1, y1, x2, y2, color=None, w=1, z=1, ls="-", cap="butt"):
        self.ax.plot([x1, x2], [y1, y2], color=color or self.t["grid"], linewidth=w * PT, zorder=z, linestyle=ls,
                     solid_capstyle=cap)

    def dot(self, x, y, r, fill, ring=2, z=4):
        self.ax.add_patch(Circle((x, y), r + ring, facecolor=self.t["surface"], edgecolor="none", zorder=z))
        self.ax.add_patch(Circle((x, y), r, facecolor=fill, edgecolor="none", zorder=z + 0.1))

    def arrow(self, x1, y1, x2, y2, color=None, w=1.5, z=1, head=7, dashed=False):
        color = color or self.t["muted"]
        self.ax.annotate("", xy=(x2, y2), xytext=(x1, y1), zorder=z,
                         arrowprops=dict(arrowstyle=f"-|>,head_length={head * PT / 10},head_width={head * PT / 20}",
                                         color=color, lw=w * PT, linestyle="--" if dashed else "-",
                                         shrinkA=0, shrinkB=0))

    def header(self, title, subtitle=None, x=32, y=40, maxw=None):
        maxw = maxw or self.W - 64
        tl = self.wrap(title, 20, maxw, "bold")
        y = self.lines(x, y, tl, size=20, lh=27, weight="bold")
        if subtitle:
            sl = self.wrap(subtitle, 13.5, maxw)
            y = self.lines(x, y + 2, sl, size=13.5, lh=19, color=self.t["ink2"])
        return y

    def legend(self, x, y, items, size=12.5, gap=22, maxw=None, shape="square"):
        """items: [(label, color)]; wraps to new lines. Returns y after legend."""
        maxw = maxw or self.W - 64
        cx, cy = x, y
        for lab, col in items:
            w = 12 + 6 + self.measure(lab, size)
            if cx + w > x + maxw and cx > x:
                cx, cy = x, cy + 22
            if shape == "dot":
                self.dot(cx + 5, cy - 4, 5, col, ring=0)
            else:
                self.rrect(cx, cy - 10, 11, 11, col, r=2)
            self.text(cx + 18, cy, lab, size=size, color=self.t["ink2"])
            cx += w + gap
        return cy + 10

    def footer(self, s):
        self.text(32, self.H - 18, s, size=11, color=self.t["muted"])

    def save(self, name):
        self.fig.savefig(OUT / name, dpi=200, facecolor=self.t["surface"])
        plt.close(self.fig)


# ---------------------------------------------------------------------------------------------
def chart_outcomes(t, mode):
    W, H = 900, 450
    cv = Canvas(W, H, t)
    y = cv.header("14 of 20 CORE-Bench papers reproduced in at least one run",
                  "Outcome of each paper per batch: Haiku 5.5, medium level, 30-minute limit per paper, Podman sandbox. "
                  "Every answer is scored against CORE-Bench's key.")
    cats = [("Reproduced (all answers right)", t["s"][0]), ("Partly reproduced", t["s"][1]), ("Timed out at 30 min", t["s"][2]),
            ("Gave up (infeasible or broken)", t["s"][3]), ("Finished with wrong answers", t["s"][4]),
            ("Not scored: harness crash or credit ran out", t["neutral"])]
    y = cv.legend(32, y + 26, cats)
    rows = [
        ("Cycle 1", "sandbox image :1", [9, 1, 7, 1, 1, 1]),
        ("Cycle 2", "image :2 and fixes", [8, 0, 1, 2, 0, 9]),
        ("Best run per paper", "any real run, Nov 14", [14, 1, 3, 2, 0, 0]),
    ]
    x0, x1 = 250, W - 40
    scale = (x1 - x0) / 20
    ry = y + 34
    for name, sub, vals in rows:
        cv.text(32, ry + 4, name, size=14, weight="bold", va="center")
        cv.text(32, ry + 22, sub, size=11.5, color=t["ink2"], va="center")
        x = x0
        nonzero = [i for i, v in enumerate(vals) if v]
        for i, v in enumerate(vals):
            if not v:
                continue
            w = v * scale - (2 if i != nonzero[-1] else 0)
            col = cats[i][1]
            cv.rrect(x, ry - 10, w, 28, col, r=4)
            lab = str(v)
            if cv.measure(lab, 13, "bold") + 12 < w:
                cv.text(x + 7, ry + 4, lab, size=13, weight="bold", color=label_on(t, col), va="center")
            x += v * scale
        ry += 76
    # axis ticks for "papers"
    for k in (0, 5, 10, 15, 20):
        cv.text(x0 + k * scale, ry - 34, f"{k}", size=11, color=t["muted"], ha="center")
    cv.text(x0 - 12, ry - 34, "papers", size=11, color=t["muted"], ha="right")
    cv.footer("Source: runs/.batches and run directories in CT 120, 2026-11-14. Toy task excluded (reproduced in all 8 real runs).")
    cv.save(f"01-outcomes-by-cycle-{mode}.png")


def chart_same_papers(t, mode):
    W, H = 900, 380
    cv = Canvas(W, H, t)
    y = cv.header("On the same 11 papers, cycle 2 reproduced twice as many as cycle 1",
                  "Papers that ran to the end in both cycles. The cycle 2 changes: a sandbox image with current R and "
                  "preinstalled packages, a figure-reading tool, background-run waits and prompt fixes.")
    c1, c2 = t["muted"], t["s"][0]
    y = cv.legend(32, y + 24, [("Cycle 1", c1), ("Cycle 2", c2)], shape="dot")
    rows = [("R papers", 2, 5, 6), ("Python papers", 2, 3, 5), ("All 11 papers", 4, 8, 11)]
    x0, x1 = 200, W - 70
    top = y + 30
    for k in (0, 25, 50, 75, 100):
        xx = x0 + (x1 - x0) * k / 100
        cv.line(xx, top - 12, xx, top + 3 * 58 - 22, t["grid"], 1)
        cv.text(xx, top + 3 * 58 - 6, f"{k}%", size=11, color=t["muted"], ha="center")
    for i, (name, a, b, n) in enumerate(rows):
        ry = top + i * 58 + 8
        cv.text(32, ry, name, size=14, weight="bold" if i == 2 else "normal", va="center")
        xa = x0 + (x1 - x0) * a / n
        xb = x0 + (x1 - x0) * b / n
        cv.line(xa, ry, xb, ry, t["axis"], 2, z=3, cap="round")
        cv.dot(xa, ry, 6, c1)
        cv.dot(xb, ry, 6, c2)
        cv.text(xa - 14, ry, f"{a}/{n}", size=12.5, color=t["ink2"], ha="right", va="center")
        cv.text(xb + 14, ry, f"{b}/{n}", size=12.5, color=t["ink1"], weight="bold", ha="left", va="center")
    cv.footer("Cycle 1 crash on the ART paper was a harness Podman timeout, counted as not reproduced here. Small samples: read as direction, not precision.")
    cv.save(f"02-same-papers-cycle1-vs-cycle2-{mode}.png")


def chart_causes(t, mode):
    W, H = 900, 430
    cv = Canvas(W, H, t)
    y = cv.header("Every failure traced to the environment or the 30-minute CPU budget",
                  "Root cause of the 15 runs that ran to the end without reproducing the paper, plus the 9 runs that "
                  "never ran. No run failed because the agent reasoned its way to a wrong number.")
    groups = [("Cycle 1", t["s"][0]), ("Cycle 2", t["s"][1]), ("Trial runs", t["s"][2])]
    y = cv.legend(32, y + 24, groups + [("Not run", t["neutral"])])
    rows = [
        ("R packages missing or compiling", [7, 1, 0], "3 of 4 that re-ran on image :2 then passed"),
        ("Training longer than 30 min on CPU", [2, 1, 1], "Needs a longer limit; agent now says so"),
        ("Code requires a GPU (CUDA only)", [1, 1, 0], "Needs a GPU"),
        ("Harness crash (Podman lock)", [1, 0, 0], "Fixed: cleanup can't crash a run"),
        ("Not run: OpenRouter credit ran out", [None, 9, None], "All of cycle 2's last 9 papers"),
    ]
    x0 = 300
    scale = 26
    ry = y + 30
    for name, vals, note in rows:
        cv.text(32, ry + 1, name, size=13, va="center")
        x = x0
        segs = [(v, groups[i][1]) for i, v in enumerate(vals) if v]
        if vals[0] is None:
            segs = [(vals[1], t["neutral"])]
        for j, (v, col) in enumerate(segs):
            last = j == len(segs) - 1
            w = v * scale - (0 if last else 2)
            cv.rrect(x, ry - 11, w, 22, col, r=4, corners=("tr", "br") if last else ())
            x += v * scale
        total = sum(v for v, _ in segs)
        cv.text(x + 8, ry + 1, str(total), size=13, weight="bold", va="center")
        cv.text(x + 30, ry + 1, note, size=11.5, color=t["ink2"], va="center")
        ry += 50
    cv.line(x0, y + 12, x0, ry - 30, t["axis"], 1)
    cv.footer("Runs, not papers: some papers failed in more than one run. Trial runs = the strict-delegation trial.")
    cv.save(f"03-failure-causes-{mode}.png")


def chart_time_tokens(t, mode):
    W, H = 900, 545
    cv = Canvas(W, H, t)
    y = cv.header("Runs that failed hit the 30-minute wall and used most of the budget",
                  "Each dot is one run of a CORE-Bench paper that ran to the end (35 runs with token counts).")
    rep, nrep = t["s"][0], t["s"][1]
    y = cv.legend(32, y + 24, [("Reproduced", rep), ("Not reproduced", nrep)], shape="dot")
    L, R, T, B = 90, W - 250, y + 26, H - 84
    xmax, ymax = 32, 2.5e6
    X = lambda m: L + (R - L) * m / xmax
    Y = lambda v: B - (B - T) * v / ymax
    for k in (0, 0.5e6, 1e6, 1.5e6, 2e6, 2.5e6):
        cv.line(L, Y(k), R, Y(k), t["grid"], 1)
        cv.text(L - 8, Y(k), "0" if k == 0 else f"{k / 1e6:g}M", size=11, color=t["muted"], ha="right", va="center")
    for k in (0, 5, 10, 15, 20, 25, 30):
        cv.text(X(k), B + 18, f"{k}", size=11, color=t["muted"], ha="center")
    cv.text((L + R) / 2, B + 38, "wall time (minutes)", size=11.5, color=t["ink2"], ha="center")
    cv.text(L - 8, T - 14, "tokens", size=11.5, color=t["ink2"], ha="right")
    cv.line(X(30), T, X(30), B, t["axis"], 1.5, z=2)
    cv.text(X(30) - 8, Y(1.62e6), "30-minute limit", size=11, color=t["ink2"], ha="right", va="center")
    for r in RUNS:
        if not r.get("tokens"):
            continue
        ok = r["outcome"] == "reproduced"
        cv.dot(X(min(r["wall_seconds"] / 60, 31.5)), Y(r["tokens"]), 5, rep if ok else nrep)
    big = max(RUNS, key=lambda r: r.get("tokens") or 0)
    bx, by = X(big["wall_seconds"] / 60), Y(big["tokens"])
    cv.line(bx - 8, by, bx - 60, by, t["axis"], 1)
    cv.text(bx - 64, by - 6, "2.3M tokens: 23 approvals for", size=11, color=t["ink2"], ha="right")
    cv.text(bx - 64, by + 9, "'sleep' waits (fixed in cycle 2)", size=11, color=t["ink2"], ha="right")
    # side panel
    px = R + 28
    cv.text(px, T + 6, "Not-reproduced runs", size=13, weight="bold")
    stats = [(f"{M['tokens_spent_on_failed_runs_pct']:.0f}%", "of all tokens"),
             (f"{M['time_spent_on_failed_runs_pct']:.0f}%", "of all run time"),
             ("1 of 26", "answers correct"),
             (f"{M['failed_hit_time_limit']} of 15", "ended at the limit")]
    sy = T + 40
    for big_s, small in stats:
        cv.text(px, sy, big_s, size=22, weight="bold")
        cv.text(px, sy + 20, small, size=12, color=t["ink2"])
        sy += 62
    cv.text(px, sy + 2, f"Median reproduced run: {M['wall_median_reproduced_s'] / 60:.1f} min,", size=11.5, color=t["ink2"])
    cv.text(px, sy + 19, f"{M['tokens_median_reproduced'] / 1e3:.0f}k tokens, about {M['usd_per_reproduced_paper_median'] * 100:.1f} cents", size=11.5, color=t["ink2"])
    cv.footer("Tokens include cached prompt tokens. Cost is estimated from the OpenRouter key's spend ($3.18) over all real runs (23.0M tokens).")
    cv.save(f"04-time-vs-tokens-{mode}.png")


def chart_answers(t, mode):
    W, H = 900, 410
    cv = Canvas(W, H, t)
    y = cv.header("When the agent recorded an answer, it was right 52 times out of 54",
                  "77 questions across the 36 runs that ran to the end. The 2 misses were the text 'no answer' "
                  "recorded as a value, both quoting an install error line.")
    # left: tall segmented bar of 77 questions (status colours, icon + label)
    lx, ly = 32, y + 40
    cv.text(lx, ly, "All 77 questions", size=14, weight="bold")
    parts = [("Correct", 52, STATUS["good"], "✓"), ("Left blank (no answer claimed)", 23, STATUS["warning"], "–"),
             ("Wrong", 2, STATUS["critical"], "✗")]
    bw = 400
    x = lx
    for i, (lab, v, col, icon) in enumerate(parts):
        w = bw * v / 77 - (2 if i < len(parts) - 1 else 0)
        cv.rrect(x, ly + 18, w, 28, col, r=4)
        s = f"{icon} {v}"
        if cv.measure(s, 13, "bold") + 12 < w:
            cv.text(x + 7, ly + 32, s, size=13, weight="bold", color=label_on(t, col), va="center")
        x += bw * v / 77
    yy = ly + 74
    for lab, v, col, icon in parts:
        cv.rrect(lx, yy - 10, 11, 11, col, r=2)
        cv.text(lx + 18, yy, f"{icon} {lab}: {v}", size=12.5, color=t["ink2"])
        yy += 22
    yy += 10
    for s in ["Coverage: 54 of 77 answered (70%)", "Accuracy: 52 of 77 (68%)", "Precision: 52 of 54 (96%; 95% CI 87-99%)",
              "Real numbers recorded wrong: 0"]:
        cv.text(lx, yy, s, size=12.5)
        yy += 21
    # right: correctness by stated confidence
    rx = 500
    cv.text(rx, ly, "Correct, by the confidence the agent gave", size=14, weight="bold")
    conf = M["confidence"]
    rows = [("high", conf["high"]), ("medium", conf["medium"]), ("low", conf["low"])]
    bx0, bx1 = rx + 80, W - 70
    cy = ly + 40
    for name, c in rows:
        frac = c["correct"] / c["answered"]
        cv.text(rx, cy + 1, name, size=13, va="center")
        cv.rrect(bx0, cy - 11, (bx1 - bx0) * frac, 22, t["s"][0], r=4, corners=("tr", "br"))
        cv.text(bx0 + (bx1 - bx0) * frac + 8, cy + 1, f"{c['correct']}/{c['answered']}", size=12.5, weight="bold", va="center")
        cy += 44
    cv.line(bx0, ly + 22, bx0, cy - 18, t["axis"], 1)
    cv.lines(rx, cy + 12, cv.wrap("Both wrong values were marked 'low'. High confidence was never wrong (35 of 35).", 12, W - rx - 40),
             size=12, color=t["ink2"], lh=18)
    cv.footer("Scored with harness/score.py (CORE-Bench rules: 95% prediction interval, +0.5% slack). Expected values are not shown here.")
    cv.save(f"05-answer-quality-{mode}.png")


def diagram_flow(t, mode):
    W, H = 1000, 730
    cv = Canvas(W, H, t)
    y = cv.header("How a run flows through the deep agent, and where it broke",
                  "Numbers from the 36 CORE-Bench runs that ran to the end. Green checks: what worked. Red marks: "
                  "failure points, with how often they hit.", maxw=W - 64)

    def box(x, y, w, h, title, lines_, strong=False, dashed=False):
        cv.rrect(x, y, w, h, t["box"], r=8, edge=t["boxline"] if not strong else t["axis"], lw=1.2 if strong else 1,
                 ls="--" if dashed else "-", z=1)
        cv.text(x + 14, y + 24, title, size=13.5, weight="bold")
        yy = y + 46
        for ln in lines_:
            for part in cv.wrap(ln, 11.5, w - 28):
                cv.text(x + 14, yy, part, size=11.5, color=t["ink2"])
                yy += 16
            yy += 3

    def mark(x, y, kind, label):
        col = STATUS["good"] if kind == "good" else STATUS["critical"]
        cv.ax.add_patch(Circle((x, y), 11, facecolor=col, edgecolor=t["surface"], linewidth=2 * PT, zorder=6))
        cv.text(x, y + 0.5, "✓" if kind == "good" else "!", size=12, weight="bold", color="#ffffff", ha="center", va="center", z=7)
        cv.text(x + 16, y + 0.5, label, size=11.5, weight="bold", color=t["ink1"], va="center", z=7)

    top = y + 26
    # row 1
    box(32, top, 250, 110, "CORE-Bench task", ["Paper's code capsule + questions (20 papers, medium level)", "Answer key stays in harness/answers"])
    box(330, top, 290, 110, "Workspace + Podman sandbox", ["Private copy of repo/; API keys never enter it", "Image :2: old Pythons via uv/conda, CRAN R, compilers"])
    box(668, top, 300, 110, "Memory and skills", ["/memories/fixes.md loaded every run, written in 17/36", "Skills (old pins, conda, R, notebooks, Code Ocean) read in 25/36 runs"])
    cv.arrow(282, top + 55, 328, top + 55)
    # row 2: main agent
    m_top = top + 150
    box(32, m_top, 600, 190, "Main deep agent (Haiku 5.5 via OpenRouter)", [
        "execute: 487 shell calls, 12% non-zero exit  ·  read_file/grep/glob: 143",
        "run_experiment: 38 (each one approved)  ·  start/check_background_run: 15/58",
        "look_at_figure: 10 uses; 12 answers cite a figure as evidence",
        "write_todos plan kept in only 12 of 36 runs",
        "Obstacles recorded: 33, 20 resolved (61%)",
    ], strong=True)
    box(668, m_top, 300, 190, "Subagents", ["paper-reader · env-builder · runner · result-judge",
                                             "Called in 0 of 34 normal runs: Haiku did every step itself",
                                             "With REPRO_DELEGATION=strict: delegated in 2 of 2 trial runs (1 reproduced)"], dashed=True)
    cv.arrow(632, m_top + 95, 666, m_top + 95, dashed=True)
    cv.arrow(475, top + 110, 475, m_top - 2)
    cv.arrow(700, top + 110, 612, m_top - 2)
    # row 3
    b_top = m_top + 230
    box(32, b_top, 280, 120, "Approvals (interrupt_on)", ["188 requests, auto-approved in batches", "Cycle 1 max 23 per run (sleep waits) -> cycle 2 max 8"])
    box(350, b_top, 300, 120, "record_answer evidence check", ["Quote must appear in this run's saved output", "51 of 54 quotes contain the value; 2 quoted an install error"])
    box(688, b_top, 280, 120, "report.json -> harness scorer", ["CORE-Bench scoring rules", "21 of 36 runs reproduced; 14 of 20 papers in at least one run"])
    cv.arrow(172, m_top + 190, 172, b_top - 2)
    cv.arrow(312, b_top + 60, 348, b_top + 60)
    cv.arrow(650, b_top + 60, 686, b_top + 60)
    # markers
    mark(350, top - 10, "bad", "F1 R packages on image :1: 8 runs")
    mark(44, m_top - 10, "bad", "F2 30-min CPU wall: 6 runs (CPU training, GPU-only)")
    mark(362, b_top + 140, "good", "S1 answers 52/54 right; blanks, not guesses")
    mark(800, m_top - 10, "bad", "F3 subagents unused")
    mark(362, b_top - 10, "bad", "F4 quote need not contain the value")
    mark(700, b_top - 10, "bad", "F5 credit ran out: 9 runs")
    mark(680, top - 10, "good", "S2 memory: -15% tokens on rerun")
    mark(420, m_top + 200, "good", "S3 image :2 + waits: 2 papers 28 -> 2.5 min")
    cv.footer("Counts from events.jsonl and report.json of each run. The strict-delegation trial is the only setting in which subagents were used.")
    cv.save(f"06-agent-flow-failure-points-{mode}.png")


FIXES = [
    (1, "Value must appear in the quote; add a 'no answer' tool", 1.0, 8.5),
    (2, "Stop early when projected runtime exceeds the limit", 2.5, 8.0),
    (3, "Re-run the 9 papers cut off when credit ran out", 2.0, 9.0),
    (4, "Score 'infeasible on CPU in 30 min' as its own outcome", 1.2, 6.2),
    (5, "Accept evidence only from experiment output", 2.2, 5.2),
    (6, "Run 3 papers 3x each to measure flakiness", 3.2, 4.6),
    (7, "One strict-delegation cycle (subagents on)", 4.2, 5.4),
    (8, "Hard-level cycle", 4.6, 6.6),
    (9, "Opus on the 6 unreproduced papers", 8.2, 2.2),
]


def diagram_fixes(t, mode):
    W, H = 1000, 620
    cv = Canvas(W, H, t)
    y = cv.header("Fix first: high benefit, low cost", "Estimated benefit and cost of each fix (time to build plus API spend at Haiku "
                  "rates of about $0.05 per reproduced paper). Judgment calls from the run data, not measurements.", maxw=W - 64)
    L, R, T, B = 80, 560, y + 30, H - 90
    X = lambda c: L + (R - L) * c / 10
    Y = lambda b: B - (B - T) * b / 10
    cv.rrect(X(0), Y(10), X(3.5) - X(0), Y(6) - Y(10), t["wash"], r=6, z=0)
    cv.text(X(0) + 10, Y(10) + 20, "Do first", size=12.5, weight="bold", color=t["ink2"])
    cv.line(L, B, R, B, t["axis"], 1)
    cv.line(L, T, L, B, t["axis"], 1)
    for k, lab in [(0.5, "~30 min"), (2.5, "~2 h or ~$2"), (5, "half a day or ~$5"), (8.5, "$10+")]:
        cv.text(X(k), B + 18, lab, size=11, color=t["muted"], ha="center")
    cv.text((L + R) / 2, B + 38, "cost", size=11.5, color=t["ink2"], ha="center")
    cv.text(L - 10, T + 4, "high", size=11, color=t["muted"], ha="right", va="center")
    cv.text(L - 10, B - 4, "low", size=11, color=t["muted"], ha="right", va="center")
    cv.text(L - 10, (T + B) / 2, "benefit", size=11.5, color=t["ink2"], ha="right", va="center")
    for n, name, c, b in FIXES:
        cv.dot(X(c), Y(b), 11, t["s"][0])
        cv.text(X(c), Y(b) + 0.5, str(n), size=11.5, weight="bold", color="#ffffff", ha="center", va="center", z=6)
    # list
    lx = 600
    ly = T + 4
    for n, name, c, b in FIXES:
        cv.dot(lx + 10, ly - 4, 10, t["s"][0])
        cv.text(lx + 10, ly - 3.5, str(n), size=11, weight="bold", color="#ffffff", ha="center", va="center", z=6)
        ls = cv.wrap(name, 12.5, W - lx - 60)
        cv.lines(lx + 30, ly, ls, size=12.5, lh=17)
        ly += 17 * len(ls) + 15
    cv.footer("1, 2 and 4 are code changes in agent/ and harness/; 3, 6, 7, 8 and 9 need OpenRouter credit.")
    cv.save(f"07-fix-priority-{mode}.png")


for mode, t in THEMES.items():
    chart_outcomes(t, mode)
    chart_same_papers(t, mode)
    chart_causes(t, mode)
    chart_time_tokens(t, mode)
    chart_answers(t, mode)
    diagram_flow(t, mode)
    diagram_fixes(t, mode)
print("ok", sorted(p.name for p in OUT.iterdir()))
