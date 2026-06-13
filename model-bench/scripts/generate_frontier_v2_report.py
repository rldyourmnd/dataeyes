#!/usr/bin/env python3
"""Generate PDF report for DataEyes Frontier v2 benchmark (2026-06-10)."""
import io
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.gridspec import GridSpec

# ── raw data ────────────────────────────────────────────────────────────────
RESULTS = [
    ("claude-fable-5",             "Anthropic",  "code_generation",     100, 12331,  906),
    ("claude-fable-5",             "Anthropic",  "instruction_strict",   90, 17666, 1410),
    ("claude-fable-5",             "Anthropic",  "long_context_qa",     100,  7315,  424),
    ("claude-fable-5",             "Anthropic",  "reasoning_multistep", 100,  7746,  439),
    ("deepseek-v4-flash",          "DeepSeek",   "code_generation",     100, 14947,  952),
    ("deepseek-v4-flash",          "DeepSeek",   "instruction_strict",  100, 38714, 2231),
    ("deepseek-v4-flash",          "DeepSeek",   "long_context_qa",      80, 20529, 1686),
    ("deepseek-v4-flash",          "DeepSeek",   "reasoning_multistep",  60, 16444, 1128),
    ("doubao-seed-2-0-pro-260215", "ByteDance",  "code_generation",     100, 75440, 3504),
    ("doubao-seed-2-0-pro-260215", "ByteDance",  "instruction_strict",  100, 51850, 2455),
    ("doubao-seed-2-0-pro-260215", "ByteDance",  "long_context_qa",     100, 40034, 1838),
    ("doubao-seed-2-0-pro-260215", "ByteDance",  "reasoning_multistep", 100, 26338, 1210),
    ("gemini-3.5-flash",           "Google",     "code_generation",     100, 10950, 2247),
    ("gemini-3.5-flash",           "Google",     "instruction_strict",  100, 12188, 2578),
    ("gemini-3.5-flash",           "Google",     "long_context_qa",     100,  8551, 1830),
    ("gemini-3.5-flash",           "Google",     "reasoning_multistep", 100,  6416, 1031),
    ("glm-5-turbo",                "Zhipu AI",   "code_generation",     100, 36260, 2898),
    ("glm-5-turbo",                "Zhipu AI",   "instruction_strict",  100, 23042, 1508),
    ("glm-5-turbo",                "Zhipu AI",   "long_context_qa",     100, 15307, 1001),
    ("glm-5-turbo",                "Zhipu AI",   "reasoning_multistep", 100, 19919, 1171),
    ("gpt-5.5",                    "OpenAI",     "code_generation",     100, 11299,  768),
    ("gpt-5.5",                    "OpenAI",     "instruction_strict",  100, 11631,  599),
    ("gpt-5.5",                    "OpenAI",     "long_context_qa",     100,  7021,  357),
    ("gpt-5.5",                    "OpenAI",     "reasoning_multistep", 100,  6847,  307),
    ("kimi-k2-thinking",           "Moonshot",   "code_generation",     100,138318, 8625),
    ("kimi-k2-thinking",           "Moonshot",   "instruction_strict",   90, 25666, 1706),
    ("kimi-k2-thinking",           "Moonshot",   "long_context_qa",     100, 42985, 2855),
    ("kimi-k2-thinking",           "Moonshot",   "reasoning_multistep", 100, 24978, 1342),
    ("mimo-v2.5-pro",              "MiMo",       "code_generation",     100, 15536,  598),
    ("mimo-v2.5-pro",              "MiMo",       "instruction_strict",   90, 15073,  568),
    ("mimo-v2.5-pro",              "MiMo",       "long_context_qa",      80,  5703,   90),
    ("mimo-v2.5-pro",              "MiMo",       "reasoning_multistep", 100, 15445,  406),
    ("MiniMax-M2.7",               "MiniMax",    "code_generation",     100, 11504, 2593),
    ("MiniMax-M2.7",               "MiniMax",    "instruction_strict",  100,  4331,  899),
    ("MiniMax-M2.7",               "MiniMax",    "long_context_qa",     100,  3132,  665),
    ("MiniMax-M2.7",               "MiniMax",    "reasoning_multistep", 100,  3723,  696),
    ("qwen3.7-max",                "Alibaba",    "code_generation",     100,101312, 4922),
    ("qwen3.7-max",                "Alibaba",    "instruction_strict",  100, 71892, 3847),
    ("qwen3.7-max",                "Alibaba",    "long_context_qa",     100, 20775,  945),
    ("qwen3.7-max",                "Alibaba",    "reasoning_multistep", 100, 33556, 1552),
]

CASES = ["reasoning_multistep", "code_generation", "instruction_strict", "long_context_qa"]
CASE_LABELS = {
    "reasoning_multistep": "Reasoning\nMultistep",
    "code_generation":     "Code\nGeneration",
    "instruction_strict":  "Instruction\nFollowing",
    "long_context_qa":     "Long\nContext QA",
}

# aggregate per model
from collections import defaultdict
model_data = defaultdict(lambda: {"company": "", "scores": {}, "latencies": {}, "tokens": {}})
for model, company, case, score, lat, toks in RESULTS:
    model_data[model]["company"] = company
    model_data[model]["scores"][case] = score
    model_data[model]["latencies"][case] = lat
    model_data[model]["tokens"][case] = toks

MODELS_ORDERED = [
    "gpt-5.5",
    "gemini-3.5-flash",
    "claude-fable-5",
    "MiniMax-M2.7",
    "qwen3.7-max",
    "glm-5-turbo",
    "doubao-seed-2-0-pro-260215",
    "kimi-k2-thinking",
    "deepseek-v4-flash",
    "mimo-v2.5-pro",
]

SHORT = {
    "gpt-5.5":                    "GPT-5.5\n(OpenAI)",
    "gemini-3.5-flash":           "Gemini 3.5\n(Google)",
    "claude-fable-5":             "Claude Fable-5\n(Anthropic)",
    "MiniMax-M2.7":               "MiniMax M2.7\n(MiniMax)",
    "qwen3.7-max":                "Qwen 3.7 Max\n(Alibaba)",
    "glm-5-turbo":                "GLM-5 Turbo\n(Zhipu AI)",
    "doubao-seed-2-0-pro-260215": "Doubao Seed\n(ByteDance)",
    "kimi-k2-thinking":           "Kimi K2\n(Moonshot)",
    "deepseek-v4-flash":          "DeepSeek V4\n(DeepSeek)",
    "mimo-v2.5-pro":              "MiMo 2.5\n(MiMo)",
}

COMPANY_COLOR = {
    "OpenAI":    "#10a37f",
    "Google":    "#4285f4",
    "Anthropic": "#c96442",
    "MiniMax":   "#7b5ea7",
    "Alibaba":   "#ff6a00",
    "Zhipu AI":  "#0077cc",
    "ByteDance": "#1f8eff",
    "Moonshot":  "#8a2be2",
    "DeepSeek":  "#e63946",
    "MiMo":      "#2a9d8f",
}

def total_score(m):
    return sum(model_data[m]["scores"].values())

def avg_latency_s(m):
    return sum(model_data[m]["latencies"].values()) / 4000  # ms → s

def bar_colors(models):
    return [COMPANY_COLOR[model_data[m]["company"]] for m in models]


# ── PDF ─────────────────────────────────────────────────────────────────────
OUTPUT = Path.home() / "Desktop" / "DataEyes_Frontier_v2_2026-06-10.pdf"

with PdfPages(str(OUTPUT)) as pdf:

    # ── PAGE 1: Cover ────────────────────────────────────────────────────────
    fig = plt.figure(figsize=(11, 8.5))
    fig.patch.set_facecolor("#0d1117")
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis("off")
    ax.set_facecolor("#0d1117")

    # gradient band
    for i, y in enumerate(np.linspace(0.58, 0.62, 40)):
        alpha = 0.3 + 0.4 * abs(i - 20) / 20
        ax.axhline(y, color="#1e3a5f", lw=3, alpha=alpha)

    ax.text(0.5, 0.78, "DataEyes Platform", ha="center", va="center",
            fontsize=14, color="#4a90d9", fontweight="bold")
    ax.text(0.5, 0.68, "Frontier Model Benchmark", ha="center", va="center",
            fontsize=32, color="white", fontweight="bold")
    ax.text(0.5, 0.59, "Top 10 Latest 2026 Models · 1 Model per Company", ha="center",
            va="center", fontsize=14, color="#a0b4c8")
    ax.text(0.5, 0.52, "June 10, 2026", ha="center", va="center",
            fontsize=11, color="#606878")

    # score table
    sorted_m = sorted(MODELS_ORDERED, key=total_score, reverse=True)
    cols = ["Rank", "Model", "Company", "Total Score", "Avg Latency"]
    col_x = [0.04, 0.12, 0.40, 0.62, 0.80]
    row_h = 0.042
    header_y = 0.435
    ax.text(0.5, 0.47, "Results Summary", ha="center", va="center",
            fontsize=13, color="#4a90d9", fontweight="bold")
    for i, (col, x) in enumerate(zip(cols, col_x)):
        ax.text(x, header_y, col, fontsize=8.5, color="#4a90d9",
                fontweight="bold", va="center")
    ax.axhline(header_y - 0.008, color="#1e3a5f", lw=1, xmin=0.03, xmax=0.97)

    for rank, m in enumerate(sorted_m, 1):
        y = header_y - row_h * rank
        bg_color = "#111820" if rank % 2 == 0 else "#0d1117"
        rect = mpatches.FancyBboxPatch((0.03, y - 0.018), 0.94, row_h,
                                       boxstyle="round,pad=0", fc=bg_color, ec="none", zorder=0)
        ax.add_patch(rect)
        medal = {1: "#1", 2: "#2", 3: "#3"}.get(rank, f"#{rank}")
        c = COMPANY_COLOR[model_data[m]["company"]]
        ax.text(col_x[0], y, medal if rank <= 3 else f"#{rank}",
                fontsize=8.5, color=c, va="center")
        ax.text(col_x[1], y, m[:28], fontsize=8, color="white", va="center")
        ax.text(col_x[2], y, model_data[m]["company"], fontsize=8, color="#a0b4c8", va="center")
        score = total_score(m)
        score_color = "#10d98f" if score == 400 else "#ffcc44" if score >= 380 else "#ff6b6b"
        ax.text(col_x[3], y, f"{score} / 400", fontsize=8.5, color=score_color,
                va="center", fontweight="bold")
        ax.text(col_x[4], y, f"{avg_latency_s(m):.1f}s avg", fontsize=8,
                color="#a0b4c8", va="center")

    ax.text(0.5, 0.05, "Suite: deep_eval  ·  Tasks: reasoning_multistep, code_generation, "
            "instruction_strict, long_context_qa  ·  100 pts/task",
            ha="center", va="center", fontsize=8, color="#404858")
    pdf.savefig(fig, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)

    # ── PAGE 2: Overall Scores Bar Chart ────────────────────────────────────
    fig, ax = plt.subplots(figsize=(13, 7))
    fig.patch.set_facecolor("#0d1117")
    ax.set_facecolor("#111820")

    sorted_m = sorted(MODELS_ORDERED, key=total_score, reverse=True)
    scores = [total_score(m) for m in sorted_m]
    labels = [SHORT[m] for m in sorted_m]
    colors = [COMPANY_COLOR[model_data[m]["company"]] for m in sorted_m]

    bars = ax.bar(range(len(sorted_m)), scores, color=colors, width=0.65,
                  edgecolor="#ffffff22", linewidth=0.5, zorder=3)
    for i, (bar, s) in enumerate(zip(bars, scores)):
        ax.text(bar.get_x() + bar.get_width() / 2, s + 1.5, str(s),
                ha="center", va="bottom", fontsize=10, color="white", fontweight="bold")

    ax.set_xticks(range(len(sorted_m)))
    ax.set_xticklabels(labels, fontsize=9, color="#a0b4c8", linespacing=1.4)
    ax.set_ylim(0, 430)
    ax.set_ylabel("Total Score (max 400)", color="#a0b4c8", fontsize=11)
    ax.set_title("Overall Benchmark Scores — Top 10 Frontier Models 2026",
                 color="white", fontsize=14, fontweight="bold", pad=16)
    ax.axhline(400, color="#ffffff33", lw=1, linestyle="--", zorder=2)
    ax.tick_params(colors="#606878")
    for spine in ax.spines.values():
        spine.set_color("#1e3a5f")
    ax.yaxis.set_tick_params(colors="#606878")
    ax.grid(axis="y", color="#1e3a5f", lw=0.8, zorder=1)
    fig.tight_layout(pad=2)
    pdf.savefig(fig, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)

    # ── PAGE 3: Per-Task Heatmap ─────────────────────────────────────────────
    fig, ax = plt.subplots(figsize=(13, 7))
    fig.patch.set_facecolor("#0d1117")
    ax.set_facecolor("#111820")

    sorted_m2 = sorted(MODELS_ORDERED, key=total_score, reverse=True)
    matrix = np.array([[model_data[m]["scores"].get(c, 0) for c in CASES] for m in sorted_m2])
    im = ax.imshow(matrix, aspect="auto", cmap="RdYlGn", vmin=50, vmax=100)

    for i, m in enumerate(sorted_m2):
        for j, c in enumerate(CASES):
            v = model_data[m]["scores"].get(c, 0)
            ax.text(j, i, str(v), ha="center", va="center",
                    fontsize=11, color="black" if v >= 80 else "white", fontweight="bold")

    ax.set_xticks(range(4))
    ax.set_xticklabels([CASE_LABELS[c] for c in CASES], color="white", fontsize=10)
    ax.set_yticks(range(len(sorted_m2)))
    ax.set_yticklabels([SHORT[m].replace("\n", " ") for m in sorted_m2], color="#a0b4c8", fontsize=9)
    ax.set_title("Per-Task Score Heatmap", color="white", fontsize=14, fontweight="bold", pad=14)
    cbar = fig.colorbar(im, ax=ax, fraction=0.03, pad=0.02)
    cbar.ax.yaxis.set_tick_params(colors="#a0b4c8")
    cbar.set_label("Score (pts)", color="#a0b4c8")
    fig.tight_layout(pad=2)
    pdf.savefig(fig, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)

    # ── PAGE 4: Latency Bar Chart ─────────────────────────────────────────────
    fig, ax = plt.subplots(figsize=(13, 7))
    fig.patch.set_facecolor("#0d1117")
    ax.set_facecolor("#111820")

    sorted_lat = sorted(MODELS_ORDERED, key=avg_latency_s)
    lats = [avg_latency_s(m) for m in sorted_lat]
    colors2 = [COMPANY_COLOR[model_data[m]["company"]] for m in sorted_lat]
    bars2 = ax.barh(range(len(sorted_lat)), lats, color=colors2, height=0.6,
                    edgecolor="#ffffff22", linewidth=0.5, zorder=3)
    for i, (bar, v) in enumerate(zip(bars2, lats)):
        ax.text(v + 0.3, bar.get_y() + bar.get_height() / 2,
                f"{v:.1f}s", va="center", fontsize=9, color="white")

    ax.set_yticks(range(len(sorted_lat)))
    ax.set_yticklabels([SHORT[m].replace("\n", " ") for m in sorted_lat],
                       fontsize=9, color="#a0b4c8")
    ax.set_xlabel("Average Latency per Task (seconds)", color="#a0b4c8", fontsize=11)
    ax.set_title("Average Response Latency per Task", color="white", fontsize=14,
                 fontweight="bold", pad=14)
    ax.tick_params(colors="#606878")
    for spine in ax.spines.values():
        spine.set_color("#1e3a5f")
    ax.grid(axis="x", color="#1e3a5f", lw=0.8, zorder=1)
    fig.tight_layout(pad=2)
    pdf.savefig(fig, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)

    # ── PAGE 5: Score vs Latency Scatter ─────────────────────────────────────
    fig, ax = plt.subplots(figsize=(11, 7))
    fig.patch.set_facecolor("#0d1117")
    ax.set_facecolor("#111820")

    for m in MODELS_ORDERED:
        s = total_score(m)
        l = avg_latency_s(m)
        c = COMPANY_COLOR[model_data[m]["company"]]
        ax.scatter(l, s, s=180, color=c, zorder=5, edgecolors="white", linewidths=0.7)
        label = SHORT[m].replace("\n", " ")
        offset_x = 0.5
        offset_y = -4 if m in ("kimi-k2-thinking", "qwen3.7-max") else 3
        ax.annotate(label, (l, s), xytext=(l + offset_x, s + offset_y),
                    fontsize=7.5, color="#a0b4c8",
                    arrowprops=dict(arrowstyle="-", color="#404858", lw=0.5))

    ax.set_xlabel("Average Latency per Task (seconds)", color="#a0b4c8", fontsize=11)
    ax.set_ylabel("Total Score (max 400)", color="#a0b4c8", fontsize=11)
    ax.set_title("Score vs. Latency: Quality-Speed Trade-off", color="white",
                 fontsize=14, fontweight="bold", pad=14)
    ax.tick_params(colors="#606878")
    for spine in ax.spines.values():
        spine.set_color("#1e3a5f")
    ax.grid(color="#1e3a5f", lw=0.6, zorder=1)

    # quadrant labels
    ax.text(0.02, 0.97, "Fast & Accurate", transform=ax.transAxes,
            fontsize=9, color="#10d98f", alpha=0.7, va="top")
    ax.text(0.7, 0.97, "Slow & Accurate", transform=ax.transAxes,
            fontsize=9, color="#ffcc44", alpha=0.7, va="top")
    ax.text(0.7, 0.1, "Slow & Inaccurate", transform=ax.transAxes,
            fontsize=9, color="#ff6b6b", alpha=0.7, va="bottom")

    fig.tight_layout(pad=2)
    pdf.savefig(fig, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)

    # ── PAGE 6: Per-Model Deep Dives (spider / radar) ────────────────────────
    angles = np.linspace(0, 2 * np.pi, 4, endpoint=False).tolist()
    angles += angles[:1]

    fig = plt.figure(figsize=(13, 10))
    fig.patch.set_facecolor("#0d1117")
    fig.suptitle("Per-Model Task Profile (Radar)", color="white",
                 fontsize=14, fontweight="bold", y=0.97)

    for idx, m in enumerate(MODELS_ORDERED):
        ax = fig.add_subplot(2, 5, idx + 1, polar=True)
        ax.set_facecolor("#111820")
        vals = [model_data[m]["scores"].get(c, 0) / 100 for c in CASES] + \
               [model_data[m]["scores"].get(CASES[0], 0) / 100]
        color = COMPANY_COLOR[model_data[m]["company"]]
        ax.plot(angles, vals, color=color, lw=1.8, zorder=5)
        ax.fill(angles, vals, color=color, alpha=0.25)
        ax.set_xticks(angles[:-1])
        ax.set_xticklabels(["Reason", "Code", "Instr", "LongCtx"],
                           fontsize=6.5, color="#a0b4c8")
        ax.set_ylim(0, 1.05)
        ax.set_yticks([0.5, 1.0])
        ax.set_yticklabels(["50", "100"], fontsize=5, color="#606878")
        ax.grid(color="#1e3a5f", lw=0.6)
        ax.spines["polar"].set_color("#1e3a5f")
        short_title = SHORT[m].replace("\n", " ")
        ax.set_title(short_title, fontsize=7.5, color="white", pad=8, fontweight="bold")
        # total score annotation
        ts = total_score(m)
        score_c = "#10d98f" if ts == 400 else "#ffcc44" if ts >= 380 else "#ff6b6b"
        ax.text(0, -0.28, f"{ts}/400", transform=ax.transAxes,
                ha="center", fontsize=8, color=score_c, fontweight="bold")

    fig.tight_layout(rect=[0, 0, 1, 0.95], pad=1.5)
    pdf.savefig(fig, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)

    # ── PAGE 7: Detailed Stats Table ─────────────────────────────────────────
    fig = plt.figure(figsize=(13, 9))
    fig.patch.set_facecolor("#0d1117")
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_facecolor("#0d1117"); ax.axis("off")
    ax.set_xlim(0, 1); ax.set_ylim(0, 1)
    ax.text(0.5, 0.96, "Detailed Results Table", ha="center", va="top",
            fontsize=14, color="white", fontweight="bold")

    col_defs = [
        ("Model", 0.02, 0.20),
        ("Task", 0.23, 0.15),
        ("Score", 0.40, 0.08),
        ("Latency (s)", 0.50, 0.10),
        ("Out Tokens", 0.62, 0.10),
        ("Tok/s", 0.73, 0.08),
    ]
    header_y = 0.90
    for name, x, _ in col_defs:
        ax.text(x, header_y, name, fontsize=8, color="#4a90d9", fontweight="bold", va="top")
    ax.axhline(header_y - 0.015, color="#1e3a5f", lw=0.8, xmin=0.01, xmax=0.99)

    row_h = 0.021
    y = header_y - 0.025
    sorted_m3 = sorted(MODELS_ORDERED, key=total_score, reverse=True)
    for mi, m in enumerate(sorted_m3):
        mc = COMPANY_COLOR[model_data[m]["company"]]
        for ci, case in enumerate(CASES):
            bg = "#111820" if (mi * 4 + ci) % 2 == 0 else "#0d1117"
            rect = mpatches.FancyBboxPatch((0.01, y - 0.005), 0.98, row_h,
                                           boxstyle="round,pad=0", fc=bg, ec="none", zorder=0)
            ax.add_patch(rect)
            score = model_data[m]["scores"].get(case, 0)
            lat_s = model_data[m]["latencies"].get(case, 0) / 1000
            toks = model_data[m]["tokens"].get(case, 0)
            tok_s = toks / lat_s if lat_s > 0 else 0

            ax.text(0.02, y + 0.005, m if ci == 0 else "", fontsize=7, color=mc, va="center")
            ax.text(0.23, y + 0.005, CASE_LABELS[case].replace("\n", " "), fontsize=7,
                    color="#a0b4c8", va="center")
            sc_c = "#10d98f" if score == 100 else "#ffcc44" if score >= 80 else "#ff6b6b"
            ax.text(0.40, y + 0.005, str(score), fontsize=7.5, color=sc_c,
                    fontweight="bold", va="center")
            ax.text(0.50, y + 0.005, f"{lat_s:.1f}s", fontsize=7, color="#a0b4c8", va="center")
            ax.text(0.62, y + 0.005, f"{toks:,}", fontsize=7, color="#a0b4c8", va="center")
            ax.text(0.73, y + 0.005, f"{tok_s:.1f}", fontsize=7, color="#a0b4c8", va="center")
            y -= row_h
        ax.axhline(y + row_h - 0.002, color="#1e3a5f", lw=0.4, xmin=0.01, xmax=0.99)

    pdf.savefig(fig, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)

    # ── metadata ────────────────────────────────────────────────────────────
    d = pdf.infodict()
    d["Title"] = "DataEyes Frontier Model Benchmark v2 — 2026-06-10"
    d["Author"] = "DataEyes Benchmark Service"
    d["Subject"] = "Top 10 frontier models, 1 per company, June 2026"

print(f"PDF saved → {OUTPUT}")
