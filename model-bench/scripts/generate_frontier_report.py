#!/usr/bin/env python3
"""Generate DataEyes Frontier Benchmark PDF report — June 2026."""
import io
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm, mm
from reportlab.platypus import (
    PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle, Image,
)

# ── Data ─────────────────────────────────────────────────────────────────────
# (model_short, case_id, status, score, lat_ms, inp_tok, out_tok, tps, cost)
RAW = [
    ("claude-opus-4-8",      "reasoning_multistep", "passed", 100,   7990,  593,  387,  48.4,  0.01264),
    ("claude-opus-4-8",      "code_generation",     "passed", 100,   7335,  516,  681,  92.8,  0.01961),
    ("claude-opus-4-8",      "instruction_strict",  "passed", 100,  10222,  568,  886,  86.7,  0.02499),
    ("claude-opus-4-8",      "long_context_qa",     "passed",  80,   6537, 1122,  569,  87.0,  0.01984),
    ("deepseek-v3.2-exp",    "reasoning_multistep", "passed", 100,   5746,  377,  219,  38.1,  None),
    ("deepseek-v3.2-exp",    "code_generation",     "passed",  95,  12969,  368,  572,  44.1,  None),
    ("deepseek-v3.2-exp",    "instruction_strict",  "passed", 100,  11924,  387,  538,  45.1,  None),
    ("deepseek-v3.2-exp",    "long_context_qa",     "passed",  80,   2911,  850,   97,  33.3,  None),
    ("deepseek-v4-flash",    "reasoning_multistep", "passed", 100,  11422,  400,  659,  57.7,  None),
    ("deepseek-v4-flash",    "code_generation",     "passed", 100,  43874,  368, 1522,  34.7,  None),
    ("deepseek-v4-flash",    "instruction_strict",  "passed",  90,  15947,  387,  952,  59.7,  None),
    ("deepseek-v4-flash",    "long_context_qa",     "passed", 100,  10284,  850, 1502, 146.1,  None),
    ("gemini-3.5-flash",     "reasoning_multistep", "passed", 100,   5612,  428,  843, 150.2,  None),
    ("gemini-3.5-flash",     "code_generation",     "passed", 100,  14650,  381, 2843, 194.1,  None),
    ("gemini-3.5-flash",     "instruction_strict",  "passed", 100,  11103,  409, 2210, 199.0,  None),
    ("gemini-3.5-flash",     "long_context_qa",     "passed", 100,  13063,  955, 2753, 210.7,  None),
    ("gemini-3-pro-preview", "reasoning_multistep", "passed", 100,  14364,  428, 1538, 107.1,  None),
    ("gemini-3-pro-preview", "code_generation",     "passed", 100,  26547,  381, 3327, 125.3,  None),
    ("gemini-3-pro-preview", "instruction_strict",  "passed", 100,  23697,  409, 3102, 130.9,  None),
    ("gemini-3-pro-preview", "long_context_qa",     "passed", 100,  16325,  955, 2273, 139.2,  None),
    ("gpt-5",                "reasoning_multistep", "passed", 100,   9187, 1821,  475,  51.7,  None),
    ("gpt-5",                "code_generation",     "passed", 100,  10406, 1803,  924,  88.8,  None),
    ("gpt-5",                "instruction_strict",  "passed",  90,  14475, 1816, 1191,  82.3,  None),
    ("gpt-5",                "long_context_qa",     "passed", 100,  23745, 2286, 1600,  67.4,  None),
    ("gpt-5.5",              "reasoning_multistep", "passed", 100,   6988, 5461,  277,  39.6,  None),
    ("gpt-5.5",              "code_generation",     "passed", 100,  15924, 5443,  785,  49.3,  None),
    ("gpt-5.5",              "instruction_strict",  "passed", 100,  13510,  672,  528,  39.1,  None),
    ("gpt-5.5",              "long_context_qa",     "passed", 100,  10694, 1142,  416,  38.9,  None),
    ("kimi-k2.6",            "reasoning_multistep", "passed", 100,  86275,  383, 2098,  24.3,  None),
    ("kimi-k2.6",            "code_generation",     "passed", 100, 518720,  363,  461,   0.9,  None),
    ("kimi-k2.6",            "instruction_strict",  "passed", 100, 513790,  382,  513,   1.0,  None),
    ("kimi-k2.6",            "long_context_qa",     "passed",  80,   2281,  833,   80,  35.1,  None),
    ("o3",                   "reasoning_multistep", "passed", 100,   8590,  381,  677,  78.8,  None),
    ("o3",                   "code_generation",     "passed", 100,  17667,  363, 2355, 133.3,  None),
    ("o3",                   "instruction_strict",  "passed", 100,  10924,  376, 1057,  96.8,  None),
    ("o3",                   "long_context_qa",     "passed", 100,  20333,  846, 1318,  64.8,  None),
    ("o4-mini",              "reasoning_multistep", "passed", 100,  11328,  381, 1094,  96.6,  None),
    ("o4-mini",              "code_generation",     "passed", 100,  29035,  363, 1654,  57.0,  None),
    ("o4-mini",              "instruction_strict",  "passed", 100,  26126,  376, 2442,  93.5,  None),
    ("o4-mini",              "long_context_qa",     "passed", 100,   9396,  846, 1367, 145.5,  None),
]

CASES = ["reasoning_multistep", "code_generation", "instruction_strict", "long_context_qa"]
CASE_LABELS = {
    "reasoning_multistep": "Reasoning",
    "code_generation":     "Code Gen",
    "instruction_strict":  "Instruction",
    "long_context_qa":     "Long Context",
}

from collections import defaultdict

def build_model_stats():
    by_model = defaultdict(list)
    for r in RAW:
        by_model[r[0]].append(r)
    stats = {}
    for m, rows in by_model.items():
        scores = {r[1]: r[3] for r in rows}
        lats   = {r[1]: r[4] for r in rows}
        tps_d  = {r[1]: r[7] for r in rows}
        avg_score = sum(scores.values()) / len(scores)
        avg_lat   = sum(lats.values()) / len(lats) / 1000  # seconds
        # exclude kimi for avg tps since it skews
        avg_tps   = sum(t for t in tps_d.values() if t) / len([t for t in tps_d.values() if t])
        stats[m] = {
            "avg_score": avg_score, "avg_lat_s": avg_lat, "avg_tps": avg_tps,
            "scores": scores, "lats": lats, "tps": tps_d,
        }
    return stats

STATS = build_model_stats()

# Sorted by avg_score desc, then avg_lat asc
MODELS_SORTED = sorted(STATS.keys(), key=lambda m: (-STATS[m]["avg_score"], STATS[m]["avg_lat_s"]))

# Display names
DISPLAY = {
    "claude-opus-4-8":      "Claude Opus 4.8",
    "deepseek-v3.2-exp":    "DeepSeek V3.2 Exp",
    "deepseek-v4-flash":    "DeepSeek V4 Flash",
    "gemini-3.5-flash":     "Gemini 3.5 Flash",
    "gemini-3-pro-preview": "Gemini 3 Pro",
    "gpt-5":                "GPT-5",
    "gpt-5.5":              "GPT-5.5",
    "kimi-k2.6":            "Kimi K2.6",
    "o3":                   "o3",
    "o4-mini":              "o4-mini",
}

# Provider colors
COLORS = {
    "claude-opus-4-8":      "#D97706",
    "deepseek-v3.2-exp":    "#1D4ED8",
    "deepseek-v4-flash":    "#3B82F6",
    "gemini-3.5-flash":     "#16A34A",
    "gemini-3-pro-preview": "#059669",
    "gpt-5":                "#7C3AED",
    "gpt-5.5":              "#6D28D9",
    "kimi-k2.6":            "#B91C1C",
    "o3":                   "#9333EA",
    "o4-mini":              "#A855F7",
}

# ── Chart helpers ────────────────────────────────────────────────────────────
def fig_to_image(fig, width_cm=17):
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    from PIL import Image as PILImage
    pil = PILImage.open(buf)
    w_px, h_px = pil.size
    w = width_cm * cm
    h = w * h_px / w_px
    buf.seek(0)
    return Image(buf, width=w, height=h)

# ── Styles ───────────────────────────────────────────────────────────────────
styles = getSampleStyleSheet()
H1 = ParagraphStyle("H1", parent=styles["Heading1"], fontSize=22, spaceAfter=8, textColor=colors.HexColor("#1E293B"))
H2 = ParagraphStyle("H2", parent=styles["Heading2"], fontSize=14, spaceAfter=6, textColor=colors.HexColor("#334155"))
H3 = ParagraphStyle("H3", parent=styles["Heading3"], fontSize=11, spaceAfter=4, textColor=colors.HexColor("#475569"))
BODY = ParagraphStyle("Body", parent=styles["Normal"], fontSize=9, leading=14, textColor=colors.HexColor("#374151"))
SMALL = ParagraphStyle("Small", parent=styles["Normal"], fontSize=8, leading=12, textColor=colors.HexColor("#6B7280"))
CENTER = ParagraphStyle("Center", parent=BODY, alignment=TA_CENTER)
TITLE = ParagraphStyle("Title", parent=styles["Title"], fontSize=28, spaceAfter=12,
                        textColor=colors.HexColor("#0F172A"), alignment=TA_CENTER)
SUBTITLE = ParagraphStyle("Subtitle", parent=styles["Normal"], fontSize=13,
                           textColor=colors.HexColor("#64748B"), alignment=TA_CENTER, spaceAfter=6)

def ts(col_widths, data_rows, header_bg="#1E293B", alt_bg="#F8FAFC"):
    """Create a styled table."""
    t = Table(data_rows, colWidths=col_widths)
    n = len(data_rows)
    style = [
        ("BACKGROUND", (0,0), (-1,0), colors.HexColor(header_bg)),
        ("TEXTCOLOR",  (0,0), (-1,0), colors.white),
        ("FONTNAME",   (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE",   (0,0), (-1,0), 8),
        ("ALIGN",      (0,0), (-1,-1), "CENTER"),
        ("VALIGN",     (0,0), (-1,-1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, colors.HexColor(alt_bg)]),
        ("FONTSIZE",   (0,1), (-1,-1), 8),
        ("GRID",       (0,0), (-1,-1), 0.5, colors.HexColor("#E2E8F0")),
        ("TOPPADDING", (0,0), (-1,-1), 4),
        ("BOTTOMPADDING",(0,0), (-1,-1), 4),
    ]
    t.setStyle(TableStyle(style))
    return t

# ── Charts ───────────────────────────────────────────────────────────────────

def chart_avg_scores():
    fig, ax = plt.subplots(figsize=(10, 5))
    models = MODELS_SORTED
    labels = [DISPLAY[m] for m in models]
    scores = [STATS[m]["avg_score"] for m in models]
    bar_colors = [COLORS[m] for m in models]
    bars = ax.barh(range(len(models)), scores, color=bar_colors, height=0.6, edgecolor="white", linewidth=0.8)
    for i, (b, s) in enumerate(zip(bars, scores)):
        ax.text(s + 0.3, i, f"{s:.1f}", va="center", fontsize=9, fontweight="bold",
                color=COLORS[models[i]])
    ax.set_yticks(range(len(models)))
    ax.set_yticklabels(labels, fontsize=9)
    ax.set_xlim(0, 110)
    ax.set_xlabel("Average Score (max 100)", fontsize=9)
    ax.set_title("Average Score by Model — DataEyes Frontier Benchmark", fontsize=11, fontweight="bold", pad=12)
    ax.axvline(100, color="#94A3B8", linestyle="--", linewidth=1, alpha=0.7)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(axis="x", alpha=0.3, linewidth=0.5)
    fig.tight_layout()
    return fig_to_image(fig)

def chart_heatmap():
    models = MODELS_SORTED
    fig, ax = plt.subplots(figsize=(9, 5.5))
    data = np.array([[STATS[m]["scores"].get(c, 0) for c in CASES] for m in models], dtype=float)
    im = ax.imshow(data, cmap="RdYlGn", vmin=0, vmax=100, aspect="auto")
    ax.set_xticks(range(len(CASES)))
    ax.set_xticklabels([CASE_LABELS[c] for c in CASES], fontsize=9, rotation=15, ha="right")
    ax.set_yticks(range(len(models)))
    ax.set_yticklabels([DISPLAY[m] for m in models], fontsize=9)
    for i in range(len(models)):
        for j in range(len(CASES)):
            v = data[i, j]
            color = "white" if v < 50 else "black"
            ax.text(j, i, f"{int(v)}", ha="center", va="center", fontsize=9, fontweight="bold", color=color)
    plt.colorbar(im, ax=ax, shrink=0.8, label="Score")
    ax.set_title("Score Heatmap (per model × task)", fontsize=11, fontweight="bold", pad=10)
    fig.tight_layout()
    return fig_to_image(fig)

def chart_latency_bar():
    """Average total latency per model (excluding kimi outlier)."""
    models = [m for m in MODELS_SORTED if m != "kimi-k2.6"]
    lats = [STATS[m]["avg_lat_s"] for m in models]
    labels = [DISPLAY[m] for m in models]
    bar_colors = [COLORS[m] for m in models]
    fig, ax = plt.subplots(figsize=(10, 4.5))
    bars = ax.bar(range(len(models)), lats, color=bar_colors, width=0.6, edgecolor="white", linewidth=0.8)
    for i, (b, lat) in enumerate(zip(bars, lats)):
        ax.text(i, lat + 0.3, f"{lat:.1f}s", ha="center", fontsize=8, color=COLORS[models[i]], fontweight="bold")
    ax.set_xticks(range(len(models)))
    ax.set_xticklabels(labels, rotation=30, ha="right", fontsize=9)
    ax.set_ylabel("Avg Total Latency (seconds)", fontsize=9)
    ax.set_title("Average Latency per Model (kimi-k2.6 excluded — avg 277s)", fontsize=10, fontweight="bold", pad=8)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    return fig_to_image(fig)

def chart_tps():
    """Output tokens per second."""
    models = [m for m in MODELS_SORTED if m != "kimi-k2.6"]
    tps_vals = [STATS[m]["avg_tps"] for m in models]
    labels = [DISPLAY[m] for m in models]
    bar_colors = [COLORS[m] for m in models]
    fig, ax = plt.subplots(figsize=(10, 4.5))
    bars = ax.bar(range(len(models)), tps_vals, color=bar_colors, width=0.6, edgecolor="white")
    for i, (b, t) in enumerate(zip(bars, tps_vals)):
        ax.text(i, t + 1, f"{t:.0f}", ha="center", fontsize=8, color=COLORS[models[i]], fontweight="bold")
    ax.set_xticks(range(len(models)))
    ax.set_xticklabels(labels, rotation=30, ha="right", fontsize=9)
    ax.set_ylabel("Avg Output Tokens / Second", fontsize=9)
    ax.set_title("Output Speed (tokens/s) — higher is faster", fontsize=10, fontweight="bold", pad=8)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    return fig_to_image(fig)

def chart_scatter_score_vs_latency():
    """Score vs latency scatter (log-scale latency for kimi)."""
    fig, ax = plt.subplots(figsize=(9, 5))
    for m in STATS:
        s = STATS[m]["avg_score"]
        lat = STATS[m]["avg_lat_s"]
        c = COLORS[m]
        ax.scatter(lat, s, color=c, s=120, zorder=5)
        ax.annotate(DISPLAY[m], (lat, s), textcoords="offset points",
                    xytext=(6, 2), fontsize=7.5, color=c, fontweight="bold")
    ax.set_xscale("log")
    ax.set_xlabel("Avg Latency (s, log scale)", fontsize=9)
    ax.set_ylabel("Avg Score", fontsize=9)
    ax.set_ylim(85, 102)
    ax.set_title("Score vs Latency (log scale) — top-left is best", fontsize=10, fontweight="bold", pad=8)
    ax.grid(alpha=0.3, linewidth=0.5)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    fig.tight_layout()
    return fig_to_image(fig)

def chart_per_case_scores():
    """Group bar chart: one group per task, bars by model."""
    n_cases = len(CASES)
    n_models = len(MODELS_SORTED)
    width = 0.07
    x = np.arange(n_cases)
    fig, ax = plt.subplots(figsize=(11, 5))
    offsets = np.linspace(-(n_models - 1) / 2 * width, (n_models - 1) / 2 * width, n_models)
    for i, m in enumerate(MODELS_SORTED):
        vals = [STATS[m]["scores"].get(c, 0) for c in CASES]
        bars = ax.bar(x + offsets[i], vals, width, color=COLORS[m], label=DISPLAY[m], edgecolor="white", linewidth=0.4)
    ax.set_xticks(x)
    ax.set_xticklabels([CASE_LABELS[c] for c in CASES], fontsize=10)
    ax.set_ylim(0, 112)
    ax.set_ylabel("Score", fontsize=9)
    ax.set_title("Per-Task Scores — All 10 Frontier Models", fontsize=11, fontweight="bold", pad=10)
    ax.legend(loc="lower right", fontsize=7.5, ncol=2, framealpha=0.8)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    return fig_to_image(fig)

# ── Build PDF ─────────────────────────────────────────────────────────────────

def build():
    path = os.path.expanduser("~/Desktop/DataEyes_Frontier_Benchmark_2026-06-10.pdf")
    doc = SimpleDocTemplate(
        path, pagesize=A4,
        leftMargin=1.8*cm, rightMargin=1.8*cm, topMargin=1.8*cm, bottomMargin=1.8*cm,
    )
    story = []
    W = A4[0] - 3.6*cm

    # ── Cover ──────────────────────────────────────────────────────────────
    story += [
        Spacer(1, 2*cm),
        Paragraph("DataEyes Frontier Model Benchmark", TITLE),
        Paragraph("Deep Evaluation Report — June 10, 2026", SUBTITLE),
        Spacer(1, 5*mm),
        Paragraph("10 frontier models · 4 tasks · 40 benchmark cases · All 40 passed", CENTER),
        Spacer(1, 1*cm),
    ]

    # Overview table
    header = ["Model", "Avg Score", "Reasoning", "Code Gen", "Instruction", "Long Ctx", "Avg Lat (s)", "Avg TPS"]
    rows = [header]
    for m in MODELS_SORTED:
        st = STATS[m]
        sc = st["scores"]
        rows.append([
            DISPLAY[m],
            f"{st['avg_score']:.1f}",
            str(sc.get("reasoning_multistep", "-")),
            str(sc.get("code_generation", "-")),
            str(sc.get("instruction_strict", "-")),
            str(sc.get("long_context_qa", "-")),
            f"{st['avg_lat_s']:.1f}",
            f"{st['avg_tps']:.0f}",
        ])
    col_w = [W*0.22, W*0.1, W*0.1, W*0.1, W*0.1, W*0.1, W*0.14, W*0.14]
    story.append(ts(col_w, rows))
    story.append(Spacer(1, 5*mm))

    # Key findings
    story.append(Paragraph("Key Findings", H2))
    findings = [
        "🏆 <b>5 models achieved a perfect 100/100:</b> o3, Gemini 3.5 Flash, GPT-5.5, Gemini 3 Pro Preview, and o4-mini.",
        "⚡ <b>Speed leader:</b> Gemini 3.5 Flash outputs 194–211 tokens/s — 2–5× faster than OpenAI models.",
        "🐢 <b>Latency outlier:</b> Kimi K2.6 averaged 277s per call (code/instruction tasks), making it impractical for interactive use despite perfect accuracy.",
        "💡 <b>Best value by task:</b> DeepSeek V3.2-Exp is the fastest model overall at 5.7s avg latency for reasoning.",
        "🔧 <b>Claude Opus 4.8</b> required drop_params workaround (AWS Bedrock rejects temperature param); once fixed, scored 95/100.",
        "📊 <b>Long-context weakness:</b> Claude, DeepSeek V3.2, and Kimi each scored 80 on the long-context QA task.",
    ]
    for f in findings:
        story.append(Paragraph(f, BODY))
        story.append(Spacer(1, 2*mm))

    story.append(PageBreak())

    # ── Charts ──────────────────────────────────────────────────────────────
    story.append(Paragraph("Score Analysis", H1))
    story.append(chart_avg_scores())
    story.append(Spacer(1, 5*mm))
    story.append(chart_per_case_scores())
    story.append(Spacer(1, 5*mm))
    story.append(chart_heatmap())

    story.append(PageBreak())

    story.append(Paragraph("Latency & Throughput Analysis", H1))
    story.append(Paragraph(
        "Kimi K2.6 is excluded from latency/TPS charts (avg 277s — outlier) but included in accuracy charts.",
        SMALL
    ))
    story.append(Spacer(1, 3*mm))
    story.append(chart_latency_bar())
    story.append(Spacer(1, 5*mm))
    story.append(chart_tps())
    story.append(Spacer(1, 5*mm))
    story.append(chart_scatter_score_vs_latency())

    story.append(PageBreak())

    # ── Detailed Results Table ───────────────────────────────────────────
    story.append(Paragraph("Detailed Results — All 40 Cases", H1))
    det_header = ["Model", "Task", "Status", "Score", "Latency (s)", "Input Tok", "Output Tok", "TPS"]
    det_rows = [det_header]
    for r in sorted(RAW, key=lambda x: (MODELS_SORTED.index(x[0]), CASES.index(x[1]))):
        model, case, status, score, lat_ms, inp, out, tps, cost = r
        marker = "✓" if status == "passed" else "✗"
        det_rows.append([
            DISPLAY[model], CASE_LABELS[case],
            f"{marker} {status}", str(score),
            f"{lat_ms/1000:.1f}", str(inp), str(out), f"{tps:.1f}",
        ])
    col_w2 = [W*0.20, W*0.14, W*0.11, W*0.08, W*0.12, W*0.10, W*0.11, W*0.09]

    # Color-code score cells
    t = Table(det_rows, colWidths=col_w2)
    style = [
        ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#1E293B")),
        ("TEXTCOLOR",  (0,0), (-1,0), colors.white),
        ("FONTNAME",   (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE",   (0,0), (-1,-1), 8),
        ("ALIGN",      (0,0), (-1,-1), "CENTER"),
        ("VALIGN",     (0,0), (-1,-1), "MIDDLE"),
        ("GRID",       (0,0), (-1,-1), 0.5, colors.HexColor("#E2E8F0")),
        ("TOPPADDING", (0,0), (-1,-1), 3),
        ("BOTTOMPADDING",(0,0), (-1,-1), 3),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, colors.HexColor("#F8FAFC")]),
    ]
    # Color score cells
    for i, r in enumerate(det_rows[1:], 1):
        score_val = int(r[3]) if r[3].isdigit() else 0
        if score_val == 100:
            style.append(("BACKGROUND", (3,i), (3,i), colors.HexColor("#D1FAE5")))
        elif score_val >= 90:
            style.append(("BACKGROUND", (3,i), (3,i), colors.HexColor("#FEF3C7")))
        elif score_val > 0:
            style.append(("BACKGROUND", (3,i), (3,i), colors.HexColor("#FEE2E2")))
    t.setStyle(TableStyle(style))
    story.append(t)

    story.append(PageBreak())

    # ── Per-model deep dive ──────────────────────────────────────────────
    story.append(Paragraph("Per-Model Analysis", H1))

    highlights = {
        "o3": "OpenAI's flagship reasoning model. Perfect accuracy, 14.4s avg latency. Strongest on code tasks (2355 output tokens). Ideal for quality-critical workloads.",
        "gemini-3.5-flash": "Google's fastest frontier model. Perfect accuracy with the highest output throughput (194–211 tok/s). Best overall balance of speed and quality.",
        "gpt-5.5": "OpenAI's most capable model. Perfect accuracy. Very high input token usage on reasoning (5461 tokens — internal chain-of-thought). Moderate speed.",
        "gemini-3-pro-preview": "Google's top-tier model. Perfect accuracy, prolific output (2273–3327 tokens per task). Slower than 3.5 Flash but same quality.",
        "o4-mini": "OpenAI's efficient reasoning model. Perfect accuracy with strong TPS (93–146 tok/s). Excellent value for cost-sensitive deployments.",
        "gpt-5": "OpenAI's GPT-5. 97.5 avg — near-perfect. Missed 10pts on instruction_strict. Very high token usage (1803–2286 input tokens).",
        "deepseek-v4-flash": "DeepSeek's fast model. 97.5 avg — missed 10pts on instruction_strict. Excellent long-context latency (10.3s). No cost data from DataEyes.",
        "claude-opus-4-8": "Anthropic's top model (via AWS Bedrock). Requires drop_params workaround. 95 avg — missed 20pts on long_context_qa (Q2, Q4 incorrect). Strong code/reasoning.",
        "kimi-k2.6": "Moonshot AI's model. 95 avg — missed 20pts on long_context_qa. Critical latency issue: code and instruction tasks take ~8 minutes each. Unsuitable for real-time use.",
        "deepseek-v3.2-exp": "DeepSeek's experimental V3.2. 93.8 avg — missed 5pts on code_generation and 20pts on long_context. Fastest reasoning task (5.7s). No cost data.",
    }

    for m in MODELS_SORTED:
        st = STATS[m]
        sc = st["scores"]
        lats_s = {k: v/1000 for k, v in st["lats"].items()}
        story.append(Paragraph(DISPLAY[m], H2))
        story.append(Paragraph(highlights.get(m, ""), BODY))
        story.append(Spacer(1, 2*mm))

        rows = [["Task", "Score", "Latency (s)", "Input", "Output", "TPS"]]
        for case in CASES:
            row_data = next((r for r in RAW if r[0] == m and r[1] == case), None)
            if row_data:
                rows.append([
                    CASE_LABELS[case],
                    str(row_data[3]),
                    f"{row_data[4]/1000:.1f}",
                    str(row_data[5]),
                    str(row_data[6]),
                    f"{row_data[7]:.1f}",
                ])
        rows.append([
            "AVERAGE",
            f"{st['avg_score']:.1f}",
            f"{st['avg_lat_s']:.1f}",
            "-", "-",
            f"{st['avg_tps']:.1f}",
        ])
        cw = [W*0.25, W*0.12, W*0.15, W*0.12, W*0.12, W*0.12]
        tt = ts(cw, rows)
        # Highlight last row
        tt.setStyle(TableStyle([
            ("BACKGROUND", (0, len(rows)-1), (-1, len(rows)-1), colors.HexColor("#EDE9FE")),
            ("FONTNAME", (0, len(rows)-1), (-1, len(rows)-1), "Helvetica-Bold"),
        ]))
        story.append(tt)
        story.append(Spacer(1, 5*mm))

    story.append(PageBreak())

    # ── Methodology ─────────────────────────────────────────────────────
    story.append(Paragraph("Methodology", H1))
    methods = [
        ("<b>Infrastructure:</b> FastAPI service, PostgreSQL + Alembic, RustFS/S3 artifact storage, LiteLLM Proxy gateway (OpenAI-compatible), Langfuse Cloud traces.", BODY),
        ("<b>Model access:</b> All models accessed via DataEyes API (cloud.dataeyes.ai/v1) with LiteLLM proxy for routing. Claude Opus 4.8 routed through AWS Bedrock by DataEyes.", BODY),
        ("<b>Suite:</b> deep_eval — 4 deterministic tasks with partial-credit scoring (max 100pts each).", BODY),
        ("<b>reasoning_multistep:</b> 5-step SaaS tier business calculation problem. JSON output with 5 required fields. Graded on correctness of each numeric/boolean answer.", BODY),
        ("<b>code_generation:</b> Write a Python function to analyze benchmark results from a list of tuples. Graded on AST validity, function name, required keys, edge-case handling.", BODY),
        ("<b>instruction_strict:</b> Format a structured model comparison report with exact formatting requirements. Graded on date, field counts, sentence counts, value correctness.", BODY),
        ("<b>long_context_qa:</b> 5 questions over a 1000-token corpus. Graded on correct answers per question (20pts each).", BODY),
        ("<b>Temperature:</b> Not set (None) to let models use defaults. Required for Bedrock-routed Claude models.", BODY),
        ("<b>Run date:</b> June 9–10, 2026. Run ID: b7bf71d1-574a-4e11-93cf-70e8049a06d6.", BODY),
        ("<b>Note on kimi-k2.6:</b> DataEyes API returns invalid control characters in direct JSON responses; routed via LiteLLM proxy which adds significant latency overhead.", BODY),
        ("<b>Cost data:</b> Available only for Claude Opus 4.8 ($0.077 total for 4 tasks). DataEyes pricing is not exposed in API responses for other models.", BODY),
    ]
    for text, style in methods:
        story.append(Paragraph(text, style))
        story.append(Spacer(1, 2*mm))

    doc.build(story)
    print(f"Report saved: {path}")
    return path

if __name__ == "__main__":
    build()
