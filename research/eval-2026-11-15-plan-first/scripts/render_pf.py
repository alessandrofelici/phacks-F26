"""Draw the plan-first comparison charts as PNG (light and dark) from metrics_pf.json and runs_pf.json.

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
M = json.loads((IN / "metrics_pf.json").read_text())
ROWS = json.loads((IN / "runs_pf.json").read_text())

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
GROUP_ORDER = ["compute wall", "reproduced before", "cut off by credit"]
GROUP_NAME = {"compute wall": "Too slow for a CPU in 30 minutes on 14 Nov",
              "reproduced before": "Reproduced on 14 Nov (regression check)",
              "cut off by credit": "Cut off when the credit ran out on 14 Nov"}
OUTCOME_ORDER = ["reproduced", "partly", "verifiable", "not_verifiable", "timed out", "gave up",
                 "finished, answers wrong", "not run (credit)", "crashed"]
OUTCOME_LABEL = {"reproduced": "Reproduced", "partly": "Partly reproduced", "verifiable": "Verifiable within budget",
                 "not_verifiable": "Not verifiable within budget", "timed out": "Timed out at 30 min",
                 "gave up": "Gave up", "finished, answers wrong": "Finished, answers wrong",
                 "not run (credit)": "Not run: credit ran out", "crashed": "Crashed"}


def outcome_style(t, o):
    """(fill, edge) for an outcome chip; 'not verifiable' is hollow on purpose: no verdict on the paper."""
    s = t["s"]
    return {"reproduced": (s[0], None), "partly": (s[1], None), "verifiable": (s[6], None),
            "not_verifiable": (t["surface"], t["ink2"]), "timed out": (s[2], None), "gave up": (s[3], None),
            "finished, answers wrong": (s[4], None), "not run (credit)": (t["neutral"], None),
            "crashed": (t["neutral"], None)}.get(o, (t["neutral"], None))


def papers_in_order():
    pp = M["per_paper"]
    out = []
    for g in GROUP_ORDER:
        ps = sorted((p for p, v in pp.items() if v["group"] == g), key=lambda p: p)
        if ps:
            out.append((g, ps))
    return out


def title_of(p):
    t = next((r.get("title") for r in ROWS if r["paper"] == p and r.get("title")), "") or ""
    return t


def chart_outcomes_pf(t, mode):
    groups = papers_in_order()
    n_rows = sum(len(ps) for _, ps in groups)
    W = 900
    row_h, group_gap = 34, 30
    used = sorted({o for v in M["per_paper"].values() for o in v["before"] + v["after"]}, key=OUTCOME_ORDER.index)
    H = 230 + n_rows * row_h + len(groups) * group_gap + 40
    cv = Canvas(W, H, t)
    rep_after = M["papers_reproduced_any_run"]
    limit = (f"none of the {M['runs_after']} runs hit the 30-minute limit" if M["timeouts_after"] == 0
             else f"{M['timeouts_after']} of {M['runs_after']} runs hit the 30-minute limit")
    y = cv.header(f"With a plan before every experiment, {limit}",
                  f"Each square is one run of a paper: 14 November (before) on the left, the plan-first runs of 15 November "
                  f"on the right. Haiku 5.5, medium level, 30 minutes per run. Across both days {rep_after} of "
                  f"{M['papers_total']} papers have reproduced in at least one run ({M['papers_reproduced_before']} before).")
    lx, bx, ax_ = 32, 480, 630
    px = ax_ + 2 * 28 + 10  # the plan column, after two run squares
    # Legend drawn here (not Canvas.legend) so the hollow "not verifiable" square matches the grid.
    cx, cy = 32, y + 22
    for o in used:
        fill, edge = outcome_style(t, o)
        lab = OUTCOME_LABEL.get(o, o)
        w = 12 + 6 + cv.measure(lab, 12.5)
        if cx + w > W - 32 and cx > 32:
            cx, cy = 32, cy + 22
        cv.rrect(cx, cy - 10, 11, 11, fill, r=2, edge=edge, lw=1.3 if edge else 0)
        cv.text(cx + 18, cy, lab, size=12.5, color=t["ink2"])
        cx += w + 22
    y = cy + 10 + 18
    cv.text(bx, y, "14 Nov", size=12.5, weight="bold", color=t["ink2"])
    cv.text(ax_, y, "Plan-first", size=12.5, weight="bold", color=t["ink2"])
    cv.text(px + 20, y, "Its plans", size=12.5, weight="bold", color=t["ink2"])
    y += 14
    for g, ps in groups:
        y += group_gap - 8
        cv.text(lx, y, GROUP_NAME[g], size=12.5, weight="bold", color=t["ink1"])
        cv.line(lx, y + 7, W - 32, y + 7, color=t["grid"], w=1)
        y += 10
        for p in ps:
            y += row_h
            v = M["per_paper"][p]
            name = title_of(p)
            short = cv.wrap(name, 12, bx - lx - 90)[0] if name else ""
            if name and short != name:
                short = short.rstrip(",.:;") + "…"
            cv.text(lx, y - 8, p, size=12, weight="bold", color=t["ink2"])
            cv.text(lx + 64, y - 8, short, size=12, color=t["ink1"])
            for col_x, outs in ((bx, v["before"]), (ax_, v["after"])):
                cx = col_x
                if not outs:
                    cv.text(cx, y - 8, "–", size=12, color=t["muted"])
                for o in outs:
                    fill, edge = outcome_style(t, o)
                    cv.rrect(cx, y - 24, 22, 22, fill, r=4, edge=edge, lw=1.6 if edge else 0)
                    cx += 28
            plans = [pp for pp in v["plans"] if pp]
            if plans:
                tag = {"full": "full", "scaled": "scaled", "not_verifiable": "not verifiable"}
                cv.text(px + 20, y - 8, ", ".join(tag.get(pp, pp) for pp in plans), size=11.5, color=t["muted"])
    cv.footer("Scored with harness/score.py: a scaled run's answer is never counted as reproduced. Runs, not papers.")
    cv.save(f"08-plan-first-outcomes-{mode}.png")


def chart_time_tokens_pf(t, mode):
    groups = papers_in_order()
    order = [p for _, ps in groups for p in ps]
    W, row_h = 900, 30
    H = 190 + len(order) * row_h + 90
    cv = Canvas(W, H, t)
    reg = M["group reproduced before"]
    y = cv.header("Time and tokens per run, before and with the planning step",
                  f"Median per paper over its runs on 14 November (grey) and its plan-first runs (blue). On papers that "
                  f"reproduced before, planning adds about {reg['minutes_median_after'] - reg['minutes_median_before']:.0f} "
                  f"minutes and {(reg['tokens_median_after'] - reg['tokens_median_before']) / 1e3:.0f}k tokens a run; on papers "
                  f"too slow for the limit it changes the outcome more than the time.")
    y = cv.legend(32, y + 22, [("14 Nov", t["neutral"]), ("Plan-first", t["s"][0])], shape="dot") + 26
    lx = 32
    panels = [("Minutes per run", "minutes", 0, 35, [0, 10, 20, 30], 250, 545),
              ("Tokens per run", "tokens", 0, 2.4e6, [0, 1e6, 2e6], 600, 860)]
    top = y + 10
    for title, key, lo, hi, ticks, x0, x1 in panels:
        X = lambda v, x0=x0, x1=x1, lo=lo, hi=hi: x0 + (min(max(v, lo), hi) - lo) / (hi - lo) * (x1 - x0)  # noqa: E731
        cv.text(x0, top - 8, title, size=12.5, weight="bold", color=t["ink2"])
        bottom = top + len(order) * row_h + 6
        for tk in ticks:
            cv.line(X(tk), top + 2, X(tk), bottom, color=t["grid"], w=1)
            lab = ("0" if tk == 0 else f"{tk / 1e6:g}M") if key == "tokens" else f"{tk:g}"
            cv.text(X(tk), bottom + 16, lab, size=11, color=t["muted"], ha="center")
        if key == "minutes":
            cv.line(X(30), top + 2, X(30), bottom, color=t["axis"], w=1.5, ls="--")
            cv.text(X(30), bottom + 30, "30-min limit", size=11, color=t["muted"], ha="center")
        for i, p in enumerate(order):
            v = M["per_paper"][p]
            yy = top + (i + 0.5) * row_h + 6
            b, a = v[f"{key}_before"], v[f"{key}_after"]
            if b is not None and a is not None:
                cv.line(X(b), yy, X(a), yy, color=t["axis"], w=2)
            if b is not None:
                cv.dot(X(b), yy, 5, t["neutral"])
            if a is not None:
                cv.dot(X(a), yy, 5, t["s"][0])
    for i, p in enumerate(order):
        yy = top + (i + 0.5) * row_h + 6
        cv.text(lx, yy + 4, p, size=12, weight="bold", color=t["ink2"])
        g = M["per_paper"][p]["group"]
        cv.text(lx + 64, yy + 4, {"compute wall": "too slow", "reproduced before": "reproduced",
                                  "cut off by credit": "cut off"}[g], size=11, color=t["muted"])
    cv.footer("For papers cut off on 14 Nov, the grey dot is their cycle 1 run on the older sandbox image. Tokens include "
              "cached prompt tokens.")
    cv.save(f"09-plan-first-time-tokens-{mode}.png")


for mode, t in THEMES.items():
    chart_outcomes_pf(t, mode)
    chart_time_tokens_pf(t, mode)
print("ok", sorted(p.name for p in OUT.iterdir()))
