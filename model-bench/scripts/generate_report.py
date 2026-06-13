#!/usr/bin/env python3
"""Generate benchmark PDF report with charts."""

import io
import os
from collections import defaultdict

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm, mm
from reportlab.platypus import (
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
    Image,
)

# ── Raw data ──────────────────────────────────────────────────────────────────
RAW = [
    ("claude-opus-4-8",           "code_generation",     "passed", 100, 7503,   516,  749, 1265, 99.8,  0.021305),
    ("claude-opus-4-8",           "instruction_strict",  "passed", 100, 10310,  568,  904, 1472, 87.7,  0.025440),
    ("claude-opus-4-8",           "long_context_qa",     "passed",  80, 11328, 1122,  374, 1496, 33.0,  0.014960),
    ("claude-opus-4-8",           "reasoning_multistep", "passed", 100,  5930,  593,  394,  987, 66.4,  0.012815),
    ("deepseek-v3-250324",        "code_generation",     "passed",  95, 18194,  367,  571,  938, 31.4,  0.000727),
    ("deepseek-v3-250324",        "instruction_strict",  "passed", 100, 16728,  386,  474,  860, 28.3,  0.000626),
    ("deepseek-v3-250324",        "long_context_qa",     "passed",  80,  3293,  849,  100,  949, 30.4,  0.000339),
    ("deepseek-v3-250324",        "reasoning_multistep", "passed", 100,  9143,  376,  245,  621, 26.8,  0.000371),
    ("doubao-seed-1-6-flash",     "code_generation",     "passed", 100, 98818,  461, 9172, 9633, 92.8,  0.001399),
    ("doubao-seed-1-6-flash",     "instruction_strict",  "passed", 100, 37293,  496, 4612, 5108,123.7,  0.000717),
    ("doubao-seed-1-6-flash",     "long_context_qa",     "passed", 100, 25231, 1045, 2297, 3342, 91.0,  0.000397),
    ("doubao-seed-1-6-flash",     "reasoning_multistep", "passed", 100, 15641,  506, 1839, 2345,117.6,  0.000301),
    ("gemini-2.5-flash",          "code_generation",     "passed", 100, 23111,  381, 5035, 5416,217.9,  0.001539),
    ("gemini-2.5-flash",          "instruction_strict",  "passed",  90,  7360,  409, 1466, 1875,199.2,  0.000470),
    ("gemini-2.5-flash",          "long_context_qa",     "passed", 100,  8283,  955, 1926, 2881,232.5,  0.000649),
    ("gemini-2.5-flash",          "reasoning_multistep", "passed", 100,  9695,  428, 2012, 2440,207.5,  0.000636),
    ("gemini-2.5-flash-thinking", "code_generation",     "passed", 100, 26485,  381, 5013, 5394,189.3,  0.003065),
    ("gemini-2.5-flash-thinking", "instruction_strict",  "passed",  90, 13844,  409, 2039, 2448,147.3,  0.001285),
    ("gemini-2.5-flash-thinking", "long_context_qa",     "passed", 100, 13953,  955, 2629, 3584,188.4,  0.001721),
    ("gemini-2.5-flash-thinking", "reasoning_multistep", "passed", 100, 12570,  428, 1982, 2410,157.7,  0.001253),
    ("gemini-2.5-pro-thinking",   "code_generation",     "passed", 100, 44507,  381, 5529, 5910,124.2,  0.055766),
    ("gemini-2.5-pro-thinking",   "instruction_strict",  "passed", 100, 19453,  409, 1923, 2332, 98.9,  0.019741),
    ("gemini-2.5-pro-thinking",   "long_context_qa",     "passed", 100, 19764,  955, 1725, 2680, 87.3,  0.018444),
    ("gemini-2.5-pro-thinking",   "reasoning_multistep", "passed", 100, 15620,  428, 1553, 1981, 99.4,  0.016065),
    ("gpt-4.1",                   "code_generation",     "passed", 100, 22280, 1799, 1923, 2442, 86.3,  0.018982),
    ("gpt-4.1",                   "instruction_strict",  "passed", 100,  4473,  403,  501,  904,112.0,  0.004814),
    ("gpt-4.1",                   "long_context_qa",     "passed", 100, 13119, 2282,  812, 1814, 61.9,  0.011060),
    ("gpt-4.1",                   "reasoning_multistep", "passed", 100,  6213, 1817,  487, 1024, 78.4,  0.007530),
    ("gpt-4.1-mini",              "code_generation",     "passed", 100,  5454,  390,  590,  980,108.2,  0.001100),
    ("gpt-4.1-mini",              "instruction_strict",  "passed",  90,  4389,  403,  506,  909,115.3,  0.000971),
    ("gpt-4.1-mini",              "long_context_qa",     "failed",  35,  2581,  873,   79,  952, 30.6,  0.000476),
    ("gpt-4.1-mini",              "reasoning_multistep", "passed",  80,  2877,  408,  206,  614, 71.6,  0.000493),
    ("gpt-4o",                    "code_generation",     "passed", 100,  4433,  390,  556,  946,125.4,  0.006535),
    ("gpt-4o",                    "instruction_strict",  "passed", 100,  4142,  403,  520,  923,125.5,  0.006208),
    ("gpt-4o",                    "long_context_qa",     "failed",  55,  2017,  873,   84,  957, 41.6,  0.003023),
    ("gpt-4o",                    "reasoning_multistep", "passed",  80,  2862,  408,  212,  620, 74.1,  0.003140),
    ("kimi-k2.5",                 "code_generation",     "passed", 100, 16920,  361,  534,  895, 31.6,  0.006243),
    ("kimi-k2.5",                 "instruction_strict",  "passed", 100, 17910,  389,  569,  958, 31.8,  0.006663),
    ("kimi-k2.5",                 "long_context_qa",     "passed",  80,  3453,  833,   68,  901, 19.7,  0.002763),
    ("kimi-k2.5",                 "reasoning_multistep", "passed", 100,  5345,  385,  244,  629, 45.7,  0.003403),
]

CASES = ["reasoning_multistep", "code_generation", "instruction_strict", "long_context_qa"]
CASE_LABELS = ["Reasoning\nMultistep", "Code\nGeneration", "Instruction\nStrict", "Long Context\nQ&A"]

# ── Aggregation ───────────────────────────────────────────────────────────────
def agg():
    m = defaultdict(lambda: {
        "scores": [], "lat_ms": [], "costs": [], "tps": [],
        "in_tok": [], "out_tok": [], "per_case": {}
    })
    for model, case, status, score, lat, in_tok, out_tok, tot_tok, tps, cost in RAW:
        m[model]["scores"].append(score)
        m[model]["lat_ms"].append(lat)
        m[model]["costs"].append(cost)
        m[model]["tps"].append(tps)
        m[model]["in_tok"].append(in_tok)
        m[model]["out_tok"].append(out_tok)
        m[model]["per_case"][case] = {
            "score": score, "lat_ms": lat, "status": status,
            "tps": tps, "cost": cost, "out_tok": out_tok, "in_tok": in_tok
        }
    return dict(m)

DATA = agg()

# Sort by avg score desc, then cost asc
MODELS_RANKED = sorted(DATA.keys(), key=lambda m: (
    -sum(DATA[m]["scores"]) / len(DATA[m]["scores"]),
    sum(DATA[m]["costs"])
))

SHORT = {
    "claude-opus-4-8":           "Claude Opus 4.8",
    "deepseek-v3-250324":        "DeepSeek V3",
    "doubao-seed-1-6-flash":     "Doubao Flash",
    "gemini-2.5-flash":          "Gemini 2.5 Flash",
    "gemini-2.5-flash-thinking": "Gemini 2.5 Flash T.",
    "gemini-2.5-pro-thinking":   "Gemini 2.5 Pro T.",
    "gpt-4.1":                   "GPT-4.1",
    "gpt-4.1-mini":              "GPT-4.1 Mini",
    "gpt-4o":                    "GPT-4o",
    "kimi-k2.5":                 "Kimi K2.5",
}

# ── Color palette ─────────────────────────────────────────────────────────────
SCORE_COLOR = "#2563EB"   # blue
LAT_COLOR   = "#16A34A"   # green
COST_COLOR  = "#DC2626"   # red
TPS_COLOR   = "#9333EA"   # purple
PASS_COLOR  = "#22C55E"
FAIL_COLOR  = "#EF4444"
NEUTRAL     = "#64748B"
BG_HEADER   = colors.HexColor("#1E3A5F")
BG_ALT      = colors.HexColor("#F0F4F8")
ACCENT      = colors.HexColor("#2563EB")

# ── Chart helpers ─────────────────────────────────────────────────────────────
def fig_to_image(fig, width_cm=17):
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight",
                facecolor="white", edgecolor="none")
    plt.close(fig)
    buf.seek(0)
    from PIL import Image as PILImage
    pil = PILImage.open(buf)
    w_px, h_px = pil.size
    aspect = h_px / w_px
    w = width_cm * cm
    h = w * aspect
    buf.seek(0)
    return Image(buf, width=w, height=h)


def chart_avg_score_vs_cost():
    fig, axes = plt.subplots(1, 2, figsize=(14, 4.5))

    # ── Left: avg score bar chart ──
    ax = axes[0]
    labels = [SHORT[m] for m in MODELS_RANKED]
    scores = [sum(DATA[m]["scores"]) / 4 for m in MODELS_RANKED]
    bar_colors = [PASS_COLOR if s >= 95 else (LAT_COLOR if s >= 85 else FAIL_COLOR) for s in scores]
    bars = ax.barh(labels[::-1], scores[::-1], color=bar_colors[::-1], height=0.6, edgecolor="white")
    for bar, sc in zip(bars, scores[::-1]):
        ax.text(bar.get_width() + 0.5, bar.get_y() + bar.get_height() / 2,
                f"{sc:.1f}", va="center", ha="left", fontsize=8.5, fontweight="bold")
    ax.set_xlim(0, 115)
    ax.set_xlabel("Average Score / 100", fontsize=9)
    ax.set_title("Quality Score (avg across 4 tasks)", fontsize=10, fontweight="bold", pad=10)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.tick_params(axis="y", labelsize=8.5)

    # ── Right: total latency bar chart ──
    ax2 = axes[1]
    lats = [sum(DATA[m]["lat_ms"]) / 1000 for m in MODELS_RANKED]
    bar_colors2 = [LAT_COLOR if l < 60 else (COST_COLOR if l > 120 else "#F59E0B") for l in lats]
    bars2 = ax2.barh(labels[::-1], lats[::-1], color=bar_colors2[::-1], height=0.6, edgecolor="white")
    for bar, lt in zip(bars2, lats[::-1]):
        ax2.text(bar.get_width() + 1, bar.get_y() + bar.get_height() / 2,
                 f"{lt:.0f}s", va="center", ha="left", fontsize=8.5, fontweight="bold")
    ax2.set_xlim(0, 230)
    ax2.set_xlabel("Total Latency — 4 tasks (seconds)", fontsize=9)
    ax2.set_title("Total Latency (sum of 4 task calls)", fontsize=10, fontweight="bold", pad=10)
    ax2.spines["top"].set_visible(False)
    ax2.spines["right"].set_visible(False)
    ax2.tick_params(axis="y", labelsize=8.5)
    ax2.yaxis.set_ticklabels([])

    fig.tight_layout(pad=2.0)
    return fig_to_image(fig)


def chart_cost_tps():
    fig, axes = plt.subplots(1, 2, figsize=(14, 4.5))

    labels = [SHORT[m] for m in MODELS_RANKED]
    costs  = [sum(DATA[m]["costs"]) * 1000 for m in MODELS_RANKED]  # in milli-$
    tps    = [sum(DATA[m]["tps"]) / len(DATA[m]["tps"]) for m in MODELS_RANKED]

    # Cost
    ax = axes[0]
    bar_cols = [PASS_COLOR if c < 5 else (COST_COLOR if c > 50 else "#F59E0B") for c in costs]
    bars = ax.barh(labels[::-1], costs[::-1], color=bar_cols[::-1], height=0.6, edgecolor="white")
    for bar, c in zip(bars, costs[::-1]):
        ax.text(bar.get_width() + 0.5, bar.get_y() + bar.get_height() / 2,
                f"${c:.1f}m", va="center", ha="left", fontsize=8.5, fontweight="bold")
    ax.set_xlim(0, 160)
    ax.set_xlabel("Total Cost (milli-USD, i.e. ×0.001$)", fontsize=9)
    ax.set_title("Cost per 4-task Run (milli-$)", fontsize=10, fontweight="bold", pad=10)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.tick_params(axis="y", labelsize=8.5)

    # TPS
    ax2 = axes[1]
    tps_cols = [PASS_COLOR if t > 150 else (LAT_COLOR if t > 80 else NEUTRAL) for t in tps]
    bars2 = ax2.barh(labels[::-1], tps[::-1], color=tps_cols[::-1], height=0.6, edgecolor="white")
    for bar, t in zip(bars2, tps[::-1]):
        ax2.text(bar.get_width() + 1, bar.get_y() + bar.get_height() / 2,
                 f"{t:.0f}", va="center", ha="left", fontsize=8.5, fontweight="bold")
    ax2.set_xlim(0, 270)
    ax2.set_xlabel("Tokens per Second (output)", fontsize=9)
    ax2.set_title("Avg Generation Speed (tok/s)", fontsize=10, fontweight="bold", pad=10)
    ax2.spines["top"].set_visible(False)
    ax2.spines["right"].set_visible(False)
    ax2.yaxis.set_ticklabels([])

    fig.tight_layout(pad=2.0)
    return fig_to_image(fig)


def chart_latency_per_case():
    fig, ax = plt.subplots(figsize=(14, 5))
    x = np.arange(len(MODELS_RANKED))
    width = 0.2
    palette = ["#2563EB", "#16A34A", "#F59E0B", "#DC2626"]

    for i, (case, label, color) in enumerate(zip(CASES, CASE_LABELS, palette)):
        lats = [DATA[m]["per_case"].get(case, {}).get("lat_ms", 0) / 1000 for m in MODELS_RANKED]
        ax.bar(x + i * width, lats, width, label=label.replace("\n", " "), color=color, alpha=0.85)

    ax.set_xticks(x + 1.5 * width)
    ax.set_xticklabels([SHORT[m] for m in MODELS_RANKED], rotation=25, ha="right", fontsize=8.5)
    ax.set_ylabel("Latency (seconds)", fontsize=9)
    ax.set_title("Per-Task Latency Breakdown", fontsize=11, fontweight="bold", pad=10)
    ax.legend(fontsize=8.5, ncol=4, loc="upper left")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    fig.tight_layout(pad=2.0)
    return fig_to_image(fig)


def chart_score_heatmap():
    """Score heatmap: models × cases."""
    fig, ax = plt.subplots(figsize=(10, 5))
    matrix = []
    for m in MODELS_RANKED:
        row = [DATA[m]["per_case"].get(c, {}).get("score", 0) for c in CASES]
        matrix.append(row)
    matrix = np.array(matrix, dtype=float)

    import matplotlib.colors as mcolors
    cmap = mcolors.LinearSegmentedColormap.from_list(
        "score", ["#EF4444", "#F59E0B", "#22C55E"], N=256
    )
    im = ax.imshow(matrix, cmap=cmap, vmin=0, vmax=100, aspect="auto")
    ax.set_xticks(range(len(CASES)))
    ax.set_xticklabels(CASE_LABELS, fontsize=9)
    ax.set_yticks(range(len(MODELS_RANKED)))
    ax.set_yticklabels([SHORT[m] for m in MODELS_RANKED], fontsize=9)
    for i, m in enumerate(MODELS_RANKED):
        for j, c in enumerate(CASES):
            sc = matrix[i, j]
            col = "white" if sc < 60 else "black"
            status = DATA[m]["per_case"].get(c, {}).get("status", "")
            marker = "" if status == "passed" else "✗"
            ax.text(j, i, f"{int(sc)}{marker}", ha="center", va="center",
                    fontsize=9, fontweight="bold", color=col)
    plt.colorbar(im, ax=ax, shrink=0.8, label="Score (0–100)")
    ax.set_title("Quality Heatmap — Score per Model × Task", fontsize=11, fontweight="bold", pad=10)
    fig.tight_layout(pad=2.0)
    return fig_to_image(fig, width_cm=14)


def chart_scatter_quality_vs_cost():
    """Scatter: quality vs cost (log scale)."""
    fig, ax = plt.subplots(figsize=(9, 5))
    for m in MODELS_RANKED:
        avg_score = sum(DATA[m]["scores"]) / 4
        total_cost_usd = sum(DATA[m]["costs"])
        ax.scatter(total_cost_usd, avg_score, s=110, zorder=5,
                   color=SCORE_COLOR if avg_score >= 95 else COST_COLOR, alpha=0.85)
        ax.annotate(SHORT[m], (total_cost_usd, avg_score),
                    textcoords="offset points", xytext=(6, 3), fontsize=7.5)
    ax.set_xscale("log")
    ax.set_xlabel("Total Cost per 4-task Run (USD, log scale)", fontsize=9)
    ax.set_ylabel("Average Score / 100", fontsize=9)
    ax.set_title("Quality vs Cost Trade-off", fontsize=11, fontweight="bold", pad=10)
    ax.set_ylim(60, 105)
    ax.axhline(95, color="green", linestyle="--", alpha=0.4, linewidth=1)
    ax.text(0.001, 95.5, "95 score threshold", color="green", fontsize=7.5, alpha=0.7)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout(pad=2.0)
    return fig_to_image(fig, width_cm=13)


# ── PDF styles ────────────────────────────────────────────────────────────────
styles = getSampleStyleSheet()

def S(name="Normal", **kw):
    return ParagraphStyle(name, parent=styles[name], **kw)

title_style    = S("Normal", fontSize=22, fontName="Helvetica-Bold", textColor=colors.HexColor("#1E3A5F"), spaceAfter=4, alignment=TA_LEFT)
subtitle_style = S("Normal", fontSize=11, fontName="Helvetica", textColor=colors.HexColor("#64748B"), spaceAfter=14)
h2_style       = S("Normal", fontSize=13, fontName="Helvetica-Bold", textColor=colors.HexColor("#1E3A5F"), spaceBefore=16, spaceAfter=6)
h3_style       = S("Normal", fontSize=10, fontName="Helvetica-Bold", textColor=colors.HexColor("#334155"), spaceBefore=8, spaceAfter=4)
body_style     = S("Normal", fontSize=8.5, fontName="Helvetica", textColor=colors.HexColor("#334155"), leading=13)
small_style    = S("Normal", fontSize=7.5, fontName="Helvetica", textColor=colors.HexColor("#64748B"), leading=11)
note_style     = S("Normal", fontSize=8, fontName="Helvetica-Oblique", textColor=colors.HexColor("#64748B"), leading=12, leftIndent=8)
bullet_style   = S("Normal", fontSize=8.5, fontName="Helvetica", textColor=colors.HexColor("#334155"), leading=13, leftIndent=12)


def P(text, style=None): return Paragraph(text, style or body_style)
def H2(text):            return Paragraph(text, h2_style)
def H3(text):            return Paragraph(text, h3_style)
def SP(h=6):             return Spacer(1, h)


# ── Table builders ─────────────────────────────────────────────────────────────
def summary_table():
    hdr_style = ParagraphStyle("th", fontSize=8, fontName="Helvetica-Bold",
                               textColor=colors.white, alignment=TA_CENTER)
    cell_style = ParagraphStyle("td", fontSize=7.5, fontName="Helvetica",
                                textColor=colors.HexColor("#1E293B"), alignment=TA_CENTER)
    cell_l = ParagraphStyle("tdl", fontSize=7.5, fontName="Helvetica",
                             textColor=colors.HexColor("#1E293B"), alignment=TA_LEFT)

    headers = ["#", "Model", "Avg\nScore", "Reason.", "Code", "Instr.", "LongCtx",
               "Total\nLat (s)", "Avg\nLat (s)", "Avg\nTPS", "4-task\nCost ($)"]
    rows = [[Paragraph(h, hdr_style) for h in headers]]

    for rank, m in enumerate(MODELS_RANKED, 1):
        d = DATA[m]
        avg = sum(d["scores"]) / 4
        total_lat = sum(d["lat_ms"]) / 1000
        avg_lat   = total_lat / 4
        avg_tps   = sum(d["tps"]) / 4
        total_cost = sum(d["costs"])

        def sc_cell(case):
            s = d["per_case"].get(case, {}).get("score", 0)
            st = d["per_case"].get(case, {}).get("status", "")
            col = "#15803D" if s >= 95 else ("#D97706" if s >= 75 else "#DC2626")
            marker = "" if st == "passed" else " ✗"
            return Paragraph(f'<font color="{col}"><b>{s}{marker}</b></font>', cell_style)

        medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(rank, str(rank))
        row = [
            Paragraph(f"<b>{medal}</b>", cell_style),
            Paragraph(f"<b>{SHORT[m]}</b>", cell_l),
            Paragraph(f'<font color="#1D4ED8"><b>{avg:.1f}</b></font>', cell_style),
            sc_cell("reasoning_multistep"),
            sc_cell("code_generation"),
            sc_cell("instruction_strict"),
            sc_cell("long_context_qa"),
            Paragraph(f"{total_lat:.0f}s", cell_style),
            Paragraph(f"{avg_lat:.1f}s", cell_style),
            Paragraph(f"{avg_tps:.0f}", cell_style),
            Paragraph(f"${total_cost:.4f}", cell_style),
        ]
        rows.append(row)

    col_widths = [1.0*cm, 3.5*cm, 1.4*cm, 1.4*cm, 1.3*cm, 1.3*cm, 1.4*cm,
                  1.5*cm, 1.5*cm, 1.3*cm, 1.8*cm]
    t = Table(rows, colWidths=col_widths, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND",   (0, 0), (-1, 0), BG_HEADER),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, BG_ALT]),
        ("GRID",         (0, 0), (-1, -1), 0.4, colors.HexColor("#CBD5E1")),
        ("VALIGN",       (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING",   (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 4),
        ("LEFTPADDING",  (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("ROWBACKGROUNDS", (0, 0), (-1, 0), [BG_HEADER]),
    ]))
    return t


def per_model_detail_table(model):
    hdr_style  = ParagraphStyle("th2", fontSize=8, fontName="Helvetica-Bold",
                                textColor=colors.white, alignment=TA_CENTER)
    cell_c = ParagraphStyle("td2c", fontSize=8, fontName="Helvetica",
                             textColor=colors.HexColor("#1E293B"), alignment=TA_CENTER)
    cell_l = ParagraphStyle("td2l", fontSize=8, fontName="Helvetica",
                             textColor=colors.HexColor("#1E293B"), alignment=TA_LEFT)

    headers = ["Task", "Status", "Score", "Latency", "In Tok", "Out Tok", "TPS", "Cost"]
    rows = [[Paragraph(h, hdr_style) for h in headers]]

    for case in CASES:
        c = DATA[model]["per_case"].get(case, {})
        score = c.get("score", 0)
        status = c.get("status", "-")
        lat    = c.get("lat_ms", 0)
        in_tok = c.get("in_tok", 0)
        out_tok = c.get("out_tok", 0)
        tps    = c.get("tps", 0)
        cost   = c.get("cost", 0)

        scol = "#15803D" if score >= 95 else ("#D97706" if score >= 75 else "#DC2626")
        stcol = "#15803D" if status == "passed" else "#DC2626"
        case_label = case.replace("_", " ").title()

        row = [
            Paragraph(case_label, cell_l),
            Paragraph(f'<font color="{stcol}"><b>{status.upper()}</b></font>', cell_c),
            Paragraph(f'<font color="{scol}"><b>{score}</b></font>', cell_c),
            Paragraph(f"{lat/1000:.1f}s", cell_c),
            Paragraph(f"{in_tok:,}", cell_c),
            Paragraph(f"{out_tok:,}", cell_c),
            Paragraph(f"{tps:.0f}/s", cell_c),
            Paragraph(f"${cost:.5f}", cell_c),
        ]
        rows.append(row)

    col_widths = [3.2*cm, 1.8*cm, 1.4*cm, 1.8*cm, 1.6*cm, 1.6*cm, 1.6*cm, 2.0*cm]
    t = Table(rows, colWidths=col_widths, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND",   (0, 0), (-1, 0), colors.HexColor("#334155")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, BG_ALT]),
        ("GRID",         (0, 0), (-1, -1), 0.4, colors.HexColor("#CBD5E1")),
        ("VALIGN",       (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING",   (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 4),
        ("LEFTPADDING",  (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
    ]))
    return t


# ── Insights ──────────────────────────────────────────────────────────────────
INSIGHTS = {
    "latency": [
        "<b>gpt-4o и gpt-4.1-mini — самые быстрые</b>: avg 3–4s на задачу, итого ~13–15s на весь suite.",
        "<b>doubao-seed-1-6-flash — самый медленный</b>: code_generation = 98.8s (модель генерирует ~9000 токенов объяснений). Итого 177s, но 100/100 баллов.",
        "<b>gemini-2.5-flash — лучший баланс скорость/качество</b>: avg 12s при TPS 207–232, score 97.5.",
        "<b>claude-opus-4-8</b>: неожиданно быстрый для flagship (avg 8.8s), TPS 33–100 в зависимости от задачи.",
        "<b>TPS лидеры</b>: Gemini 2.5 Flash (215 avg), Gemini 2.5 Flash Thinking (171), Doubao Flash (106). DeepSeek — самый медленный (28 TPS).",
        "<b>long_context_qa латенси</b>: gpt-4o и gpt-4.1-mini выдают ответ за 2s, но неправильный (score 35–55). Gemini/Claude тратят 8–19s и отвечают корректно.",
    ],
    "cost": [
        "<b>DeepSeek V3 — абсолютный чемпион цены</b>: $0.0021 за 4 задачи при avg score 93.8. В 20× дешевле GPT-4.1.",
        "<b>Gemini 2.5 Flash</b>: $0.0033 за 4 задачи, score 97.5 — лучшее соотношение среди tier-2 моделей.",
        "<b>GPT-4o</b>: $0.019 за 4 задачи — дорогой, но с провалами на long context (55/100).",
        "<b>Gemini 2.5 Pro Thinking</b>: $0.110 — самый дорогой. Оправдан только для критически важных задач рассуждения.",
        "<b>Claude Opus 4.8</b>: $0.075 за run — 36× дороже DeepSeek при схожем avg score (95 vs 93.8).",
        "<b>DataEyes подписка</b>: per-call модель с фиксированной ценой. GPT-4o через DataEyes = $0.003/call vs прямой OpenAI ~$0.011/call.",
    ],
    "quality": [
        "<b>long_context_qa — главный разделитель</b>: GPT-4o (55) и GPT-4.1-mini (35) срезались на поиске чисел в длинном документе. Все Gemini, Doubao, Claude — 100.",
        "<b>instruction_strict</b>: Gemini Flash (обе версии) и GPT-4.1-mini — 90 вместо 100. Пропускают мелкие constraint-ы в IFEval-стиле.",
        "<b>reasoning_multistep</b>: GPT-4o и GPT-4.1-mini — 80. Ошиблись в расчёте выручки SaaS tier-ов. Все остальные — 100.",
        "<b>code_generation</b>: все модели 95–100. DeepSeek — 95 (незначительная ошибка в именовании функции).",
        "<b>Лучшие по совокупности</b>: Doubao Flash, GPT-4.1, Gemini 2.5 Pro Thinking — 100/100/100/100.",
    ],
}

# ── Build PDF ─────────────────────────────────────────────────────────────────
def build_pdf(path):
    doc = SimpleDocTemplate(
        path,
        pagesize=A4,
        leftMargin=1.8*cm, rightMargin=1.8*cm,
        topMargin=2.0*cm,  bottomMargin=2.0*cm,
        title="DataEyes Model Benchmark Report",
        author="DataEyes Benchmark Service",
    )

    story = []

    # ── Cover ────────────────────────────────────────────────────────────────
    story.append(SP(10))
    story.append(Paragraph("DataEyes Model Benchmark", title_style))
    story.append(Paragraph(
        "Deep Evaluation Report · 10 Models · 4 Complex Tasks · run_id: a7a0cf3c",
        subtitle_style
    ))
    story.append(SP(4))
    story.append(Paragraph(
        "Suite: <b>deep_eval</b> &nbsp;|&nbsp; "
        "Gateway: <b>LiteLLM Proxy → DataEyes API</b> &nbsp;|&nbsp; "
        "Date: <b>2026-06-10</b> &nbsp;|&nbsp; "
        "Results: <b>38/40 passed</b>",
        body_style
    ))
    story.append(SP(14))

    # ── Section 1: Overview charts ────────────────────────────────────────────
    story.append(H2("1. Overview — Quality & Latency"))
    story.append(chart_avg_score_vs_cost())
    story.append(SP(10))

    # ── Section 2: Cost & TPS ────────────────────────────────────────────────
    story.append(H2("2. Cost & Generation Speed"))
    story.append(chart_cost_tps())
    story.append(SP(10))

    # ── Section 3: Summary table ──────────────────────────────────────────────
    story.append(PageBreak())
    story.append(H2("3. Full Results Table — All Models × All Tasks"))
    story.append(SP(4))
    story.append(summary_table())
    story.append(SP(6))
    story.append(P(
        "✗ = failed/error case. Scores 0–100 partial credit. Cost = 4-task run via DataEyes API.",
        small_style
    ))
    story.append(SP(14))

    # ── Section 4: Heatmap ────────────────────────────────────────────────────
    story.append(H2("4. Score Heatmap — Quality by Model & Task"))
    story.append(chart_score_heatmap())
    story.append(SP(10))

    # ── Section 5: Quality vs cost scatter ───────────────────────────────────
    story.append(H2("5. Quality vs Cost Trade-off"))
    story.append(chart_scatter_quality_vs_cost())
    story.append(SP(10))

    # ── Section 6: Latency per case ───────────────────────────────────────────
    story.append(PageBreak())
    story.append(H2("6. Latency Breakdown — Per Task"))
    story.append(chart_latency_per_case())
    story.append(SP(8))
    story.append(P(
        "Latency includes full round-trip through LiteLLM Proxy → DataEyes API → model provider. "
        "Thinking models (gemini-*-thinking) have additional reasoning overhead. "
        "doubao-seed code_generation = 98.8s because model outputs ~9,000 tokens of detailed explanation.",
        note_style
    ))

    # ── Section 7: Analysis ───────────────────────────────────────────────────
    story.append(PageBreak())
    story.append(H2("7. Analysis — Key Findings"))

    for section_title, bullets in [
        ("Latency Deep-Dive", INSIGHTS["latency"]),
        ("Cost Analysis", INSIGHTS["cost"]),
        ("Quality Analysis", INSIGHTS["quality"]),
    ]:
        story.append(H3(f"7.{list(INSIGHTS.keys()).index(section_title.split()[0].lower()) + 1} {section_title}"))
        for b in bullets:
            story.append(Paragraph(f"• {b}", bullet_style))
            story.append(SP(3))

    # ── Section 8: Per-model detail ───────────────────────────────────────────
    story.append(PageBreak())
    story.append(H2("8. Per-Model Detailed Results"))

    for i, m in enumerate(MODELS_RANKED):
        d = DATA[m]
        avg = sum(d["scores"]) / 4
        total_lat = sum(d["lat_ms"]) / 1000
        total_cost = sum(d["costs"])
        avg_tps = sum(d["tps"]) / 4

        score_color = "#15803D" if avg >= 95 else ("#D97706" if avg >= 85 else "#DC2626")
        block = [
            Paragraph(
                f'<font color="{score_color}"><b>{SHORT[m]}</b></font>'
                f' &nbsp;·&nbsp; avg score: <b>{avg:.1f}/100</b>'
                f' &nbsp;·&nbsp; total latency: <b>{total_lat:.0f}s</b>'
                f' &nbsp;·&nbsp; avg TPS: <b>{avg_tps:.0f}</b>'
                f' &nbsp;·&nbsp; 4-task cost: <b>${total_cost:.4f}</b>',
                h3_style
            ),
            SP(4),
            per_model_detail_table(m),
            SP(10),
        ]
        story.append(KeepTogether(block))

    # ── Section 9: Latency table (numeric) ───────────────────────────────────
    story.append(PageBreak())
    story.append(H2("9. Latency Reference Table (milliseconds)"))
    story.append(SP(4))

    hdr_s = ParagraphStyle("thlat", fontSize=8, fontName="Helvetica-Bold",
                            textColor=colors.white, alignment=TA_CENTER)
    cell_s = ParagraphStyle("tdlat", fontSize=7.5, fontName="Helvetica",
                             textColor=colors.HexColor("#1E293B"), alignment=TA_CENTER)
    cell_ls = ParagraphStyle("tdlatl", fontSize=7.5, fontName="Helvetica",
                              textColor=colors.HexColor("#1E293B"), alignment=TA_LEFT)

    lat_headers = ["Model", "Reasoning\n(ms)", "Code Gen\n(ms)", "Instruction\n(ms)",
                   "LongCtx\n(ms)", "Total\n(ms)", "Total\n(s)", "Avg\n(s)"]
    lat_rows = [[Paragraph(h, hdr_s) for h in lat_headers]]
    for m in MODELS_RANKED:
        d = DATA[m]
        lats = [d["per_case"].get(c, {}).get("lat_ms", 0) for c in CASES]
        total = sum(lats)
        def latcol(v):
            if v < 5000: col = "#15803D"
            elif v < 20000: col = "#D97706"
            else: col = "#DC2626"
            return Paragraph(f'<font color="{col}">{v:,}</font>', cell_s)
        lat_rows.append([
            Paragraph(SHORT[m], cell_ls),
            latcol(lats[0]), latcol(lats[1]), latcol(lats[2]), latcol(lats[3]),
            Paragraph(f"<b>{total:,}</b>", cell_s),
            Paragraph(f"<b>{total/1000:.1f}</b>", cell_s),
            Paragraph(f"{total/4000:.1f}", cell_s),
        ])

    cw = [3.5*cm, 2.0*cm, 2.0*cm, 2.0*cm, 2.0*cm, 2.0*cm, 1.6*cm, 1.6*cm]
    lat_table = Table(lat_rows, colWidths=cw, repeatRows=1)
    lat_table.setStyle(TableStyle([
        ("BACKGROUND",   (0, 0), (-1, 0), BG_HEADER),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, BG_ALT]),
        ("GRID",         (0, 0), (-1, -1), 0.4, colors.HexColor("#CBD5E1")),
        ("VALIGN",       (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING",   (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 4),
        ("LEFTPADDING",  (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(lat_table)
    story.append(SP(6))
    story.append(P(
        "Green = < 5s · Orange = 5–20s · Red = > 20s. "
        "Thinking models add internal chain-of-thought overhead counted in output tokens.",
        small_style
    ))

    # ── Section 10: Methodology ───────────────────────────────────────────────
    story.append(PageBreak())
    story.append(H2("10. Benchmark Methodology"))
    for bullet in [
        "<b>reasoning_multistep</b>: SaaS pricing tier calculation — 5 interdependent business rules, 100-point partial credit (20 pts each).",
        "<b>code_generation</b>: Python function generation — AST parse + structural analysis: JSON valid (10), AST parse (30), 7 required dict keys (20), efficiency calc (10), edge case handling (15).",
        "<b>instruction_strict</b>: IFEval-style per-constraint scoring — 9 constraints including date format, exact field names, model count, strengths/weaknesses count, summary length.",
        "<b>long_context_qa</b>: Needle-in-haystack — 2,000+ token document with 5 verifiable questions requiring exact value retrieval and arithmetic.",
        "<b>Scoring</b>: Partial credit (0–100). Failing cases receive proportional credit for each correct sub-answer.",
        "<b>Gateway</b>: All calls routed through LiteLLM Proxy → DataEyes OpenAI-compatible API (cloud.dataeyes.ai/v1).",
        "<b>Latency</b>: Full round-trip including network, proxy, model inference. No streaming — wait for complete response.",
        "<b>Cost</b>: DataEyes per-call subscription pricing. Not per-token. Values represent actual billing units.",
    ]:
        story.append(Paragraph(f"• {bullet}", bullet_style))
        story.append(SP(3))

    doc.build(story)
    print(f"PDF saved: {path}")


if __name__ == "__main__":
    out = os.path.expanduser("~/Desktop/DataEyes_Benchmark_Report_2026-06-10.pdf")
    build_pdf(out)
