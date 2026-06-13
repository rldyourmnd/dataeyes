#!/usr/bin/env python3
"""
Generate a comprehensive PDF benchmark report for DataEyes frontier models.
Usage: python scripts/generate_pdf_report.py [run_id] [output_path]
"""
from __future__ import annotations

import sys
import os
import math
from datetime import datetime
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import psycopg
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm, cm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, HRFlowable, KeepTogether,
)
from reportlab.platypus.flowables import Flowable
from reportlab.graphics.shapes import Drawing, Rect, String, Line, Polygon, Circle
from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.charts.legends import Legend
from reportlab.graphics import renderPDF
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY
from reportlab.pdfgen import canvas as pdf_canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import io

# ── Register Cyrillic-capable fonts ──────────────────────────────────────────
_FONT_SEARCH = [
    # macOS system fonts (Arial has full Cyrillic support)
    ("/System/Library/Fonts/Supplemental/Arial.ttf",
     "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
     "/System/Library/Fonts/Supplemental/Arial Italic.ttf",
     "/System/Library/Fonts/Supplemental/Arial Bold Italic.ttf"),
    # fallback: Arial Unicode (no bold variant, repeat for bold)
    ("/Library/Fonts/Arial Unicode.ttf",
     "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
     "/Library/Fonts/Arial Unicode.ttf",
     "/System/Library/Fonts/Supplemental/Arial Bold Italic.ttf"),
]

_fonts_registered = False
for _reg, _bold, _italic, _bolditalic in _FONT_SEARCH:
    try:
        pdfmetrics.registerFont(TTFont("Arial",           _reg))
        pdfmetrics.registerFont(TTFont("Arial-Bold",      _bold))
        pdfmetrics.registerFont(TTFont("Arial-Italic",    _italic))
        pdfmetrics.registerFont(TTFont("Arial-BoldItalic", _bolditalic))
        pdfmetrics.registerFontFamily(
            "Arial",
            normal="Arial",
            bold="Arial-Bold",
            italic="Arial-Italic",
            boldItalic="Arial-BoldItalic",
        )
        _fonts_registered = True
        break
    except Exception:
        continue

if not _fonts_registered:
    raise RuntimeError("Could not register any Cyrillic-capable font. "
                       "Install Arial or DejaVu fonts.")

# ── Color palette ─────────────────────────────────────────────────────────────
C_BG        = colors.HexColor("#0f1117")
C_SURFACE   = colors.HexColor("#1a1d27")
C_BORDER    = colors.HexColor("#2d3148")
C_ACCENT    = colors.HexColor("#6366f1")   # indigo
C_ACCENT2   = colors.HexColor("#22d3ee")   # cyan
C_GOLD      = colors.HexColor("#f59e0b")
C_GREEN     = colors.HexColor("#10b981")
C_RED       = colors.HexColor("#ef4444")
C_TEXT      = colors.HexColor("#e2e8f0")
C_TEXT_DIM  = colors.HexColor("#94a3b8")
C_WHITE     = colors.white

VENDOR_COLORS = {
    "google":     colors.HexColor("#4285f4"),
    "openai":     colors.HexColor("#10a37f"),
    "anthropic":  colors.HexColor("#d97706"),
    "deepseek":   colors.HexColor("#6366f1"),
    "alibaba":    colors.HexColor("#f97316"),
    "bytedance":  colors.HexColor("#ec4899"),
    "minimax":    colors.HexColor("#8b5cf6"),
    "moonshot":   colors.HexColor("#06b6d4"),
    "zhipu":      colors.HexColor("#84cc16"),
    "shanghaiAI": colors.HexColor("#f43f5e"),
}

VENDOR_MAP = {
    # ── v2 frontier (текущий запуск) ─────────────────────────────────────────
    "gemini-3-pro-preview":       ("Google",       "Gemini 3 Pro",           "google"),
    "gpt-5.5":                    ("OpenAI",        "GPT-5.5",                "openai"),
    "claude-fable-5":             ("Anthropic",     "Claude Fable 5",         "anthropic"),
    "deepseek-v4-pro":            ("DeepSeek",      "DeepSeek V4 Pro",        "deepseek"),
    # ── v1 frontier (предыдущие запуски) ─────────────────────────────────────
    "gemini-2.5-pro-nothinking":  ("Google",       "Gemini 2.5 Pro",         "google"),
    "gpt-4.1":                    ("OpenAI",        "GPT-4.1",                "openai"),
    "deepseek-v3-250324":         ("DeepSeek",      "DeepSeek V3",            "deepseek"),
    # ── общие (оба запуска) ───────────────────────────────────────────────────
    "qwen3.7-max":                ("Alibaba",       "Qwen 3.7 Max",           "alibaba"),
    "doubao-seed-2-0-pro-260215": ("ByteDance",     "Doubao Seed 2.0 Pro",    "bytedance"),
    "MiniMax-M2.7":               ("MiniMax",       "MiniMax M2.7",           "minimax"),
    "kimi-k2-thinking":           ("Moonshot AI",   "Kimi K2 Thinking",       "moonshot"),
    "glm-5-turbo":                ("Zhipu AI",      "GLM-5 Turbo",            "zhipu"),
    "mimo-v2.5-pro":              ("Shanghai AI",   "MiMo v2.5 Pro",          "shanghaiAI"),
}

PRICING = {
    # ── v2 frontier (official vendor prices, Jun 2026) ────────────────────────
    "claude-fable-5":             (10.00, 50.00),  # Anthropic Claude 5 flagship
    "gpt-5.5":                    ( 5.00, 30.00),  # OpenAI GPT-5.5
    "gemini-3-pro-preview":       ( 2.00, 12.00),  # Google Gemini 3 Pro (≤200k)
    "qwen3.7-max":                ( 2.50,  7.50),  # Alibaba Qwen 3.7 Max (list)
    "glm-5-turbo":                ( 1.20,  4.00),  # Zhipu AI GLM-5 Turbo
    "kimi-k2-thinking":           ( 0.60,  2.50),  # Moonshot Kimi K2 Thinking
    "doubao-seed-2-0-pro-260215": ( 0.44,  2.20),  # ByteDance Volcengine ¥3.2/¥16
    "deepseek-v4-pro":            ( 0.435, 0.87),  # DeepSeek V4 Pro
    "mimo-v2.5-pro":              ( 0.435, 0.87),  # Xiaomi MiMo v2.5 Pro
    "MiniMax-M2.7":               ( 0.28,  1.20),  # MiniMax official
    # ── v1 frontier ───────────────────────────────────────────────────────────
    "gemini-2.5-pro-nothinking":  ( 1.25, 10.00),
    "gpt-4.1":                    ( 2.00,  8.00),
    "deepseek-v3-250324":         ( 0.27,  1.10),
}

PAGE_W, PAGE_H = A4
MARGIN = 20 * mm


# ── Database helpers ──────────────────────────────────────────────────────────
def get_db_url() -> str:
    return os.getenv(
        "DATABASE_URL",
        "postgresql://benchmark:benchmark@localhost:5432/benchmark",
    ).replace("postgresql+psycopg://", "postgresql://")


def fetch_run_data(run_id: str) -> dict:
    url = get_db_url()
    with psycopg.connect(url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT suite, status, created_at, completed_at, summary "
                "FROM benchmark_runs WHERE id = %s",
                (run_id,),
            )
            row = cur.fetchone()
            if not row:
                raise ValueError(f"Run {run_id} not found")
            suite, status, created_at, completed_at, summary = row

            cur.execute(
                """SELECT model, case_id, score, input_tokens, output_tokens,
                          total_tokens, latency_ms_total, tokens_per_second,
                          estimated_cost_usd, error_type, error_message
                   FROM model_results
                   WHERE run_id = %s
                   ORDER BY model, case_id""",
                (run_id,),
            )
            rows = cur.fetchall()

    results: dict[str, dict] = {}
    for (model, case_id, score, inp, out, total, lat, tps,
         cost, err_type, err_msg) in rows:
        base = model.removeprefix("dataeyes/")
        if base not in results:
            results[base] = {}
        results[base][case_id] = {
            "score": float(score or 0),
            "input_tokens": inp,
            "output_tokens": out,
            "total_tokens": total,
            "latency_ms": lat,
            "tps": float(tps or 0),
            "cost_usd": float(cost or 0),
            "error_type": err_type,
        }

    # Aggregate per model
    aggregated = {}
    for base, tasks in results.items():
        scores = [t["score"] for t in tasks.values()]
        costs = [t["cost_usd"] for t in tasks.values()]
        lats = [t["latency_ms"] for t in tasks.values() if t["latency_ms"]]
        tps_vals = [t["tps"] for t in tasks.values() if t["tps"] > 0]
        in_toks = sum(t["input_tokens"] or 0 for t in tasks.values())
        out_toks = sum(t["output_tokens"] or 0 for t in tasks.values())
        aggregated[base] = {
            "tasks": tasks,
            "avg_score": sum(scores) / len(scores) if scores else 0,
            "total_cost": sum(costs),
            "avg_latency_ms": sum(lats) / len(lats) if lats else 0,
            "max_latency_ms": max(lats) if lats else 0,
            "avg_tps": sum(tps_vals) / len(tps_vals) if tps_vals else 0,
            "total_input_tokens": in_toks,
            "total_output_tokens": out_toks,
            "error_count": sum(1 for t in tasks.values() if t["error_type"]),
        }

    return {
        "run_id": run_id,
        "suite": suite,
        "status": status,
        "created_at": created_at,
        "completed_at": completed_at,
        "models": aggregated,
    }


# ── Custom Flowables ──────────────────────────────────────────────────────────
class ColorBar(Flowable):
    """Horizontal progress bar."""
    def __init__(self, value: float, max_val: float = 100,
                 width: float = 120, height: float = 8,
                 color=C_ACCENT):
        super().__init__()
        self.value = value
        self.max_val = max_val
        self.width = width
        self.height = height
        self.color = color

    def draw(self):
        c = self.canv
        # Background
        c.setFillColor(C_BORDER)
        c.roundRect(0, 0, self.width, self.height, 3, fill=1, stroke=0)
        # Fill
        fill_w = (self.value / self.max_val) * self.width
        if fill_w > 0:
            c.setFillColor(self.color)
            c.roundRect(0, 0, fill_w, self.height, 3, fill=1, stroke=0)

    def wrap(self, avail_w, avail_h):
        return self.width, self.height


class HorizontalBarChart(Flowable):
    """Custom horizontal bar chart for scores."""
    def __init__(self, data: list[tuple[str, float, object]],
                 width: float = 440, bar_h: float = 22, gap: float = 6):
        super().__init__()
        self.data = data  # [(label, value, color)]
        self.width = width
        self.bar_h = bar_h
        self.gap = gap
        self.label_w = 160
        self.val_w = 45
        self._height = len(data) * (bar_h + gap) + gap

    def wrap(self, avail_w, avail_h):
        return self.width, self._height

    def draw(self):
        c = self.canv
        chart_w = self.width - self.label_w - self.val_w - 10
        max_val = 100
        y = self._height - self.gap

        for label, value, color in self.data:
            y -= self.bar_h
            # Label
            c.setFillColor(C_TEXT)
            c.setFont("Arial", 8)
            c.drawString(0, y + self.bar_h / 2 - 4, label[:28])
            # Bar bg
            bx = self.label_w
            c.setFillColor(C_BORDER)
            c.roundRect(bx, y, chart_w, self.bar_h, 3, fill=1, stroke=0)
            # Bar fill
            fill_w = (value / max_val) * chart_w
            if fill_w > 0:
                c.setFillColor(color)
                c.roundRect(bx, y, fill_w, self.bar_h, 3, fill=1, stroke=0)
            # Value label
            c.setFillColor(C_TEXT)
            c.setFont("Arial-Bold", 9)
            c.drawString(bx + chart_w + 6, y + self.bar_h / 2 - 4,
                         f"{value:.1f}")
            y -= self.gap


class RadarChart(Flowable):
    """Simple radar/spider chart for 4 dimensions."""
    def __init__(self, models_data: list[tuple[str, list[float], object]],
                 labels: list[str], size: float = 160):
        super().__init__()
        self.models_data = models_data  # [(name, [v1,v2,v3,v4], color)]
        self.labels = labels
        self.size = size
        self.cx = size / 2
        self.cy = size / 2
        self.r = size * 0.35

    def wrap(self, avail_w, avail_h):
        return self.size, self.size

    def _point(self, angle_deg: float, radius: float) -> tuple[float, float]:
        a = math.radians(angle_deg - 90)
        return self.cx + radius * math.cos(a), self.cy + radius * math.sin(a)

    def draw(self):
        c = self.canv
        n = len(self.labels)
        angles = [360 / n * i for i in range(n)]

        # Grid rings
        for pct in [0.25, 0.5, 0.75, 1.0]:
            r = self.r * pct
            pts = []
            for ang in angles:
                x, y = self._point(ang, r)
                pts.extend([x, y])
            c.setStrokeColor(C_BORDER)
            c.setLineWidth(0.5)
            c.polygon(pts, fill=0, stroke=1)

        # Axes
        for ang in angles:
            x, y = self._point(ang, self.r)
            c.setStrokeColor(C_BORDER)
            c.setLineWidth(0.5)
            c.line(self.cx, self.cy, x, y)

        # Labels
        c.setFillColor(C_TEXT_DIM)
        c.setFont("Arial", 7)
        for i, (ang, label) in enumerate(zip(angles, self.labels)):
            x, y = self._point(ang, self.r + 12)
            c.drawCentredString(x, y - 3, label)

        # Data polygons
        for _, values, color in reversed(self.models_data):
            pts = []
            for ang, val in zip(angles, values):
                r = self.r * (val / 100)
                x, y = self._point(ang, r)
                pts.extend([x, y])
            # Fill (transparent)
            c.saveState()
            c.setFillColor(color)
            c.setStrokeColor(color)
            c.setLineWidth(1.5)
            c.polygon(pts, fill=0, stroke=1)
            c.restoreState()


class ScatterPlot(Flowable):
    """Score vs Cost scatter plot."""
    def __init__(self, data: list[tuple[str, float, float, object]],
                 width: float = 380, height: float = 220):
        super().__init__()
        self.data = data  # [(label, score, cost_usd, color)]
        self.width = width
        self.height = height
        self.margin_l = 45
        self.margin_b = 35
        self.margin_r = 15
        self.margin_t = 15

    def wrap(self, avail_w, avail_h):
        return self.width, self.height

    def draw(self):
        c = self.canv
        pw = self.width - self.margin_l - self.margin_r
        ph = self.height - self.margin_b - self.margin_t
        ox = self.margin_l
        oy = self.margin_b

        # Background
        c.setFillColor(C_SURFACE)
        c.rect(ox, oy, pw, ph, fill=1, stroke=0)

        costs = [d[2] for d in self.data]
        max_cost = max(costs) * 1.15 if costs else 0.1
        min_cost = 0

        # Grid lines
        for pct in [0, 0.25, 0.5, 0.75, 1.0]:
            y = oy + ph * pct
            score_val = 60 + 40 * pct
            c.setStrokeColor(C_BORDER)
            c.setLineWidth(0.3)
            c.line(ox, y, ox + pw, y)
            c.setFillColor(C_TEXT_DIM)
            c.setFont("Arial", 7)
            c.drawRightString(ox - 3, y - 3, f"{score_val:.0f}")

        # Axes labels
        c.setFillColor(C_TEXT_DIM)
        c.setFont("Arial", 7)
        c.drawCentredString(ox + pw / 2, 8, "Стоимость 4 задач (USD)")
        c.saveState()
        c.rotate(90)
        c.drawCentredString(oy + ph / 2, -10, "Средний балл")
        c.restoreState()

        # Cost axis ticks
        for i in range(5):
            pct = i / 4
            x = ox + pw * pct
            cost_v = min_cost + (max_cost - min_cost) * pct
            c.setStrokeColor(C_BORDER)
            c.setLineWidth(0.3)
            c.line(x, oy, x, oy + ph)
            c.setFillColor(C_TEXT_DIM)
            c.setFont("Arial", 6)
            c.drawCentredString(x, oy - 12, f"${cost_v:.3f}")

        # Points
        for label, score, cost, color in self.data:
            if max_cost == min_cost:
                px = ox + pw / 2
            else:
                px = ox + pw * (cost - min_cost) / (max_cost - min_cost)
            py = oy + ph * ((score - 60) / 40) if score >= 60 else oy
            # Circle
            c.setFillColor(color)
            c.circle(px, py, 5, fill=1, stroke=0)
            # Label
            c.setFillColor(C_TEXT)
            c.setFont("Arial", 6.5)
            short = label[:12]
            c.drawCentredString(px, py + 7, short)


# ── Page templates ────────────────────────────────────────────────────────────
class PageTemplate:
    def __init__(self, run_date: str):
        self.run_date = run_date

    def on_first_page(self, c, doc):
        self._draw_background(c, doc)

    def on_later_pages(self, c, doc):
        self._draw_background(c, doc)
        self._draw_header(c, doc)
        self._draw_footer(c, doc)

    def _draw_background(self, c, doc):
        c.setFillColor(C_BG)
        c.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)

    def _draw_header(self, c, doc):
        # Header line
        c.setStrokeColor(C_ACCENT)
        c.setLineWidth(1)
        c.line(MARGIN, PAGE_H - 15*mm, PAGE_W - MARGIN, PAGE_H - 15*mm)
        c.setFillColor(C_ACCENT)
        c.setFont("Arial-Bold", 8)
        c.drawString(MARGIN, PAGE_H - 12*mm, "DataEyes.ai Frontier Benchmark Report")
        c.setFillColor(C_TEXT_DIM)
        c.setFont("Arial", 8)
        c.drawRightString(PAGE_W - MARGIN, PAGE_H - 12*mm, f"Страница {doc.page}")

    def _draw_footer(self, c, doc):
        c.setStrokeColor(C_BORDER)
        c.setLineWidth(0.5)
        c.line(MARGIN, 12*mm, PAGE_W - MARGIN, 12*mm)
        c.setFillColor(C_TEXT_DIM)
        c.setFont("Arial", 7)
        c.drawString(MARGIN, 8*mm, f"DataEyes.ai · cloud.dataeyes.ai · {self.run_date}")
        c.drawRightString(PAGE_W - MARGIN, 8*mm, "Конфиденциально · Внутреннее исследование")


# ── Styles ────────────────────────────────────────────────────────────────────
def make_styles():
    s = getSampleStyleSheet()
    base = dict(textColor=C_TEXT, backColor=C_BG, fontName="Arial")

    styles = {
        "title": ParagraphStyle("title",
            fontSize=32, leading=38, textColor=C_WHITE,
            fontName="Arial-Bold", alignment=TA_CENTER),
        "subtitle": ParagraphStyle("subtitle",
            fontSize=14, leading=18, textColor=C_ACCENT2,
            fontName="Arial", alignment=TA_CENTER),
        "h1": ParagraphStyle("h1",
            fontSize=18, leading=22, textColor=C_WHITE,
            fontName="Arial-Bold", spaceBefore=8),
        "h2": ParagraphStyle("h2",
            fontSize=13, leading=17, textColor=C_ACCENT2,
            fontName="Arial-Bold", spaceBefore=6),
        "h3": ParagraphStyle("h3",
            fontSize=10, leading=14, textColor=C_ACCENT,
            fontName="Arial-Bold", spaceBefore=4),
        "body": ParagraphStyle("body",
            fontSize=9, leading=13, textColor=C_TEXT,
            fontName="Arial", alignment=TA_JUSTIFY),
        "note": ParagraphStyle("note",
            fontSize=8, leading=11, textColor=C_TEXT_DIM,
            fontName="Arial"),
        "caption": ParagraphStyle("caption",
            fontSize=8, leading=10, textColor=C_TEXT_DIM,
            fontName="Arial-Italic", alignment=TA_CENTER),
        "metric": ParagraphStyle("metric",
            fontSize=28, leading=32, textColor=C_ACCENT,
            fontName="Arial-Bold", alignment=TA_CENTER),
        "metric_label": ParagraphStyle("metric_label",
            fontSize=8, leading=10, textColor=C_TEXT_DIM,
            fontName="Arial", alignment=TA_CENTER),
    }
    return styles


# ── Table styles ──────────────────────────────────────────────────────────────
def table_style_main():
    return TableStyle([
        ("BACKGROUND",   (0, 0),  (-1, 0),  C_SURFACE),
        ("TEXTCOLOR",    (0, 0),  (-1, 0),  C_ACCENT2),
        ("FONTNAME",     (0, 0),  (-1, 0),  "Arial-Bold"),
        ("FONTSIZE",     (0, 0),  (-1, 0),  8),
        ("ALIGN",        (0, 0),  (-1, 0),  "CENTER"),
        ("BOTTOMPADDING",(0, 0),  (-1, 0),  8),
        ("TOPPADDING",   (0, 0),  (-1, 0),  8),
        ("ROWBACKGROUNDS",(0, 1), (-1, -1), [C_BG, C_SURFACE]),
        ("FONTNAME",     (0, 1),  (-1, -1), "Arial"),
        ("FONTSIZE",     (0, 1),  (-1, -1), 8),
        ("TEXTCOLOR",    (0, 1),  (-1, -1), C_TEXT),
        ("ALIGN",        (1, 1),  (-1, -1), "CENTER"),
        ("ALIGN",        (0, 1),  (0, -1),  "LEFT"),
        ("GRID",         (0, 0),  (-1, -1), 0.3, C_BORDER),
        ("TOPPADDING",   (0, 1),  (-1, -1), 6),
        ("BOTTOMPADDING",(0, 1),  (-1, -1), 6),
        ("LEFTPADDING",  (0, 0),  (-1, -1), 8),
        ("RIGHTPADDING", (0, 0),  (-1, -1), 8),
    ])


def medal(rank: int) -> str:
    return {1: "#1", 2: "#2", 3: "#3"}.get(rank, f"#{rank}")


# ── Report builder ────────────────────────────────────────────────────────────
def build_report(run_id: str, output_path: str):
    print(f"  Загрузка данных из БД для run {run_id}...")
    data = fetch_run_data(run_id)

    run_date = datetime.now().strftime("%d.%m.%Y")
    if data["created_at"]:
        run_date = data["created_at"].strftime("%d.%m.%Y %H:%M UTC")

    models = data["models"]
    # Sort by avg_score descending
    ranked = sorted(models.items(), key=lambda x: x[1]["avg_score"], reverse=True)

    pt = PageTemplate(run_date)
    styles = make_styles()

    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=22*mm, bottomMargin=22*mm,
        title="DataEyes Frontier Benchmark",
        author="DataEyes Model Bench",
    )

    story = []

    # ── COVER PAGE ────────────────────────────────────────────────────────────
    story.append(Spacer(1, 40*mm))
    story.append(Paragraph("DataEyes.ai", styles["subtitle"]))
    story.append(Spacer(1, 5*mm))
    story.append(Paragraph("Frontier Model<br/>Benchmark Report", styles["title"]))
    story.append(Spacer(1, 8*mm))
    story.append(HRFlowable(width="80%", thickness=1, color=C_ACCENT, spaceAfter=6))
    story.append(Paragraph(
        "Сравнительный анализ 10 frontier-моделей ведущих AI-вендоров<br/>"
        "через единый API-туннель DataEyes.ai", styles["subtitle"]))
    story.append(Spacer(1, 15*mm))

    # Meta info table on cover
    meta_data = [
        ["Дата прогона", run_date],
        ["Run ID", run_id[:8] + "..."],
        ["Набор тестов", "fast suite (4 задачи × 100 pts)"],
        ["Кол-во моделей", str(len(models))],
        ["API-шлюз", "cloud.dataeyes.ai/v1"],
        ["Статус", data["status"].upper()],
    ]
    meta_table = Table(meta_data, colWidths=[60*mm, 90*mm])
    meta_table.setStyle(TableStyle([
        ("BACKGROUND",   (0, 0), (-1, -1), C_SURFACE),
        ("TEXTCOLOR",    (0, 0), (0, -1),  C_ACCENT2),
        ("TEXTCOLOR",    (1, 0), (1, -1),  C_TEXT),
        ("FONTNAME",     (0, 0), (0, -1),  "Arial-Bold"),
        ("FONTNAME",     (1, 0), (1, -1),  "Arial"),
        ("FONTSIZE",     (0, 0), (-1, -1), 9),
        ("GRID",         (0, 0), (-1, -1), 0.3, C_BORDER),
        ("TOPPADDING",   (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 7),
        ("LEFTPADDING",  (0, 0), (-1, -1), 12),
        ("ALIGN",        (0, 0), (-1, -1), "LEFT"),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 10*mm))

    # Winner highlight on cover
    if ranked:
        top_model_id, top_data = ranked[0]
        vendor, full_name, vkey = VENDOR_MAP.get(top_model_id, (top_model_id, top_model_id, "deepseek"))
        vc = VENDOR_COLORS.get(vkey, C_ACCENT)

        winner_data = [[
            f"Лидер: {full_name} ({vendor})",
            f"{top_data['avg_score']:.2f} pts"
        ]]
        wt = Table(winner_data, colWidths=[120*mm, 30*mm])
        wt.setStyle(TableStyle([
            ("BACKGROUND",   (0, 0), (-1, -1), vc),
            ("TEXTCOLOR",    (0, 0), (-1, -1), C_WHITE),
            ("FONTNAME",     (0, 0), (0, 0),   "Arial-Bold"),
            ("FONTNAME",     (1, 0), (1, 0),   "Arial-Bold"),
            ("FONTSIZE",     (0, 0), (-1, -1), 11),
            ("ALIGN",        (1, 0), (1, 0),   "RIGHT"),
            ("TOPPADDING",   (0, 0), (-1, -1), 10),
            ("BOTTOMPADDING",(0, 0), (-1, -1), 10),
            ("LEFTPADDING",  (0, 0), (-1, -1), 15),
            ("RIGHTPADDING", (0, 0), (-1, -1), 15),
        ]))
        story.append(wt)

    story.append(Spacer(1, 30*mm))
    story.append(Paragraph(
        "Внутреннее исследование · DataEyes Model Bench v2026-06-10.5",
        styles["note"]))

    story.append(PageBreak())

    # ── PAGE 2: EXECUTIVE SUMMARY ─────────────────────────────────────────────
    story.append(Paragraph("Краткое резюме", styles["h1"]))
    story.append(HRFlowable(width="100%", thickness=1, color=C_BORDER, spaceAfter=4))
    story.append(Spacer(1, 3*mm))

    story.append(Paragraph(
        "DataEyes.ai предоставляет единый OpenAI-совместимый API-туннель к 157 моделям "
        "от 15+ вендоров. В данном исследовании мы протестировали 10 flagship-моделей — "
        "по одной от каждого крупного AI-вендора — используя <b>самый дешёвый доступный "
        "туннель DataEyes</b> для каждой модели. Все вызовы выполнены через единый ключ "
        "cloud.dataeyes.ai/v1.", styles["body"]))
    story.append(Spacer(1, 4*mm))

    # Key metrics row
    total_tasks = sum(len(d["tasks"]) for d in models.values())
    total_cost = sum(d["total_cost"] for d in models.values())
    errors = sum(d["error_count"] for d in models.values())
    avg_of_avgs = sum(d["avg_score"] for d in models.values()) / len(models) if models else 0

    metric_data = [
        [Paragraph(str(len(models)), styles["metric"]),
         Paragraph(f"{total_tasks}", styles["metric"]),
         Paragraph(f"{errors}", styles["metric"]),
         Paragraph(f"${total_cost:.2f}", styles["metric"])],
        [Paragraph("Вендоров", styles["metric_label"]),
         Paragraph("Задач выполнено", styles["metric_label"]),
         Paragraph("Ошибок", styles["metric_label"]),
         Paragraph("Общая стоимость", styles["metric_label"])],
    ]
    mt = Table(metric_data, colWidths=[37*mm]*4)
    mt.setStyle(TableStyle([
        ("BACKGROUND",   (0, 0), (-1, -1), C_SURFACE),
        ("GRID",         (0, 0), (-1, -1), 0.3, C_BORDER),
        ("TOPPADDING",   (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 8),
    ]))
    story.append(mt)
    story.append(Spacer(1, 5*mm))

    # Top-3 summary
    story.append(Paragraph("Топ-3 результата", styles["h2"]))
    for i, (mid, mdata) in enumerate(ranked[:3], 1):
        vendor, fname, vkey = VENDOR_MAP.get(mid, (mid, mid, "deepseek"))
        vc = VENDOR_COLORS.get(vkey, C_ACCENT)
        tasks = mdata["tasks"]
        scores_str = " | ".join(
            f"{k.replace('fast_','').title()}: {v['score']:.0f}"
            for k, v in sorted(tasks.items())
        )
        story.append(Paragraph(
            f"<b>{medal(i)} #{i} {fname}</b> ({vendor}) — "
            f"<b>{mdata['avg_score']:.2f} pts</b> avg · "
            f"${mdata['total_cost']:.4f} · {mdata['avg_latency_ms']/1000:.1f}s avg latency",
            styles["body"]))
        story.append(Paragraph(f"&nbsp;&nbsp;&nbsp;&nbsp;{scores_str}", styles["note"]))
        story.append(Spacer(1, 2*mm))

    story.append(Spacer(1, 3*mm))
    story.append(Paragraph("Ключевые выводы", styles["h2"]))

    # Dynamic findings computed from actual data
    _leader_id, _leader_data = ranked[0]
    _leader_vendor, _leader_name, _ = VENDOR_MAP.get(_leader_id, (_leader_id, _leader_id, "deepseek"))
    _cheapest_p = min(
        ((mid, PRICING.get(mid, (999, 0))[0]) for mid in models),
        key=lambda x: x[1]
    )
    _cv, _cn, _ = VENDOR_MAP.get(_cheapest_p[0], (_cheapest_p[0], _cheapest_p[0], "deepseek"))
    _fastest_id = min(models.items(), key=lambda x: x[1]["avg_latency_ms"])[0]
    _fv, _fn, _ = VENDOR_MAP.get(_fastest_id, (_fastest_id, _fastest_id, "deepseek"))
    _best_reas_id = max(
        models.items(),
        key=lambda x: x[1]["tasks"].get("fast_reasoning", {}).get("score", 0)
    )[0]
    _rv, _rn, _ = VENDOR_MAP.get(_best_reas_id, (_best_reas_id, _best_reas_id, "deepseek"))
    _thinking_models = [
        VENDOR_MAP.get(mid, (mid, mid, "d"))[1]
        for mid in models
        if any(k in mid.lower() for k in ["thinking", "glm", "doubao", "mimo"])
    ]

    findings = [
        f"Все {total_tasks} задач завершены. Лидер: {_leader_name} ({_leader_vendor}) — {_leader_data['avg_score']:.2f} pts avg.",
        f"Самый дешёвый туннель: {_cn} ({_cv}) — ${_cheapest_p[1]:.2f}/M input.",
        f"Минимальная латентность: {_fn} ({_fv}) — {models[_fastest_id]['avg_latency_ms']/1000:.1f}s в среднем.",
        f"Лучший reasoning: {_rn} ({_rv}) — {models[_best_reas_id]['tasks'].get('fast_reasoning',{}).get('score',0):.0f}/100 на логических задачах.",
        f"Общая стоимость прогона (10 моделей × 4 задачи): ${total_cost:.4f}.",
    ]
    if _thinking_models:
        findings.append(
            f"Thinking-модели ({', '.join(_thinking_models[:3])}) используют reasoning_content: медленнее, но сильнее в логике."
        )
    for f in findings:
        story.append(Paragraph(f"• {f}", styles["body"]))
    story.append(Spacer(1, 1*mm))

    story.append(PageBreak())

    # ── PAGE 3: PLATFORM OVERVIEW ─────────────────────────────────────────────
    story.append(Paragraph("Платформа DataEyes.ai", styles["h1"]))
    story.append(HRFlowable(width="100%", thickness=1, color=C_BORDER, spaceAfter=4))
    story.append(Spacer(1, 2*mm))

    story.append(Paragraph(
        "<b>DataEyes.ai</b> — агрегатор LLM-провайдеров с OpenAI-совместимым API. "
        "Работает как прозрачный прокси-шлюз: принимает запросы в формате "
        "OpenAI Chat Completions и маршрутизирует их к реальным моделям от разных вендоров.",
        styles["body"]))
    story.append(Spacer(1, 3*mm))

    # Endpoints table
    story.append(Paragraph("API-эндпоинты", styles["h2"]))
    ep_data = [
        ["Эндпоинт", "Назначение"],
        ["https://cloud.dataeyes.ai/v1", "Основной (глобальный)"],
        ["https://cloud-hk.dataeyes.ai/v1", "Резервный Гонконг"],
        ["https://cloud-cn.shuyanai.com/v1", "Резервный Китай"],
        ["https://api.dataeyes.ai/v1/search", "Web Search API"],
    ]
    ep_t = Table(ep_data, colWidths=[85*mm, 75*mm])
    ep_t.setStyle(table_style_main())
    story.append(ep_t)
    story.append(Spacer(1, 3*mm))

    story.append(Paragraph("Ключевые характеристики", styles["h2"]))
    features = [
        ("157 моделей", "от 15+ вендоров через единый API-ключ"),
        ("OpenAI-совместимый формат", "поддержка openai SDK, LiteLLM, LangChain"),
        ("Thinking-режим", "через extra_body.thinking для Claude/DeepSeek/Kimi/GLM"),
        ("Web Search", "встроенный поиск через api.dataeyes.ai"),
        ("Vertex AI туннель", "Claude через GCP Vertex AI (высокая latency ~170s)"),
        ("Единый биллинг", "один ключ для всех вендоров, оплата в $ по вендорским ценам"),
    ]
    feat_data = [["Функция", "Описание"]] + [[f, d] for f, d in features]
    feat_t = Table(feat_data, colWidths=[55*mm, 105*mm])
    feat_t.setStyle(table_style_main())
    story.append(feat_t)
    story.append(Spacer(1, 3*mm))

    # Model categories
    story.append(Paragraph("Распределение по категориям (124 текстовых модели из 157)", styles["h2"]))
    # Build category table from actual run data where possible
    _run_model_ids = set(models.keys())
    def _frontier_cell(candidates):
        for c in candidates:
            if c in _run_model_ids:
                return c
        return candidates[0]

    cat_data = [
        ["Вендор", "Доступные модели", "Frontier (тест)"],
        ["OpenAI",        "GPT-5.5, GPT-5.x, GPT-4.1, o3, o4-mini",        _frontier_cell(["gpt-5.5", "gpt-4.1"])],
        ["Anthropic",     "Claude Fable 5, Opus 4.x, Sonnet 4.x",           _frontier_cell(["claude-fable-5"])],
        ["Google",        "Gemini 3 Pro/Flash, Gemini 2.5 Pro/Flash",        _frontier_cell(["gemini-3-pro-preview", "gemini-2.5-pro-nothinking"])],
        ["DeepSeek",      "V4-pro/flash, V3-250324, R1-250528",              _frontier_cell(["deepseek-v4-pro", "deepseek-v3-250324"])],
        ["Alibaba/Qwen",  "Qwen3.7-max, Qwen2.5-VL",                        "qwen3.7-max"],
        ["ByteDance",     "Doubao Seed 2.0 lite/pro/mini",                   "doubao-seed-2-0-pro-260215"],
        ["MiniMax",       "M2.1, M2.5, M2.7, M2.7-highspeed",               "MiniMax-M2.7"],
        ["Moonshot AI",   "Kimi K2.5, K2.6, K2-thinking",                   "kimi-k2-thinking"],
        ["Zhipu AI",      "GLM-5-turbo, GLM-4v-plus",                       "glm-5-turbo"],
        ["Shanghai AI Lab","MiMo v2.5, v2.5-pro, v2-omni",                  "mimo-v2.5-pro"],
    ]
    cat_t = Table(cat_data, colWidths=[35*mm, 80*mm, 50*mm])
    cat_t.setStyle(table_style_main())
    story.append(cat_t)

    story.append(PageBreak())

    # ── PAGE 4: METHODOLOGY ───────────────────────────────────────────────────
    story.append(Paragraph("Методология тестирования", styles["h1"]))
    story.append(HRFlowable(width="100%", thickness=1, color=C_BORDER, spaceAfter=4))
    story.append(Spacer(1, 2*mm))

    story.append(Paragraph("Архитектура тестовой системы", styles["h2"]))
    story.append(Paragraph(
        "FastAPI (Python 3.13) · LiteLLM Proxy (Docker) · PostgreSQL 16 (Docker) · "
        "RustFS S3-совместимый (Docker) · Langfuse Cloud (трейсинг)",
        styles["note"]))
    story.append(Spacer(1, 2*mm))

    story.append(Paragraph(
        "Бенчмарк запускается синхронно через FastAPI: до 5 моделей работают параллельно "
        "через ThreadPoolExecutor, задачи внутри одной модели — последовательно. "
        "Каждый вызов проходит через LiteLLM Proxy на localhost:4000, который "
        "маршрутизирует к DataEyes OpenAI-совместимому API.",
        styles["body"]))
    story.append(Spacer(1, 3*mm))

    story.append(Paragraph("Параметры вызовов", styles["h2"]))
    params_data = [
        ["Параметр", "Значение", "Обоснование"],
        ["max_tokens", "5000", "Достаточно для thinking-моделей (reasoning_content)"],
        ["temperature", "0.2", "Детерминированность при допустимом разнообразии"],
        ["timeout", "300 сек", "Покрывает Vertex AI routing (~170s) и GLM (~200s)"],
        ["Параллельность", "5 моделей", "ThreadPoolExecutor(max_workers=5)"],
        ["Трейсинг", "Langfuse Cloud", "Все вызовы логируются с метриками"],
    ]
    pt_t = Table(params_data, colWidths=[40*mm, 30*mm, 95*mm])
    pt_t.setStyle(table_style_main())
    story.append(pt_t)
    story.append(Spacer(1, 3*mm))

    story.append(Paragraph("Тестовые задачи (Fast Suite)", styles["h2"]))
    tasks_desc = [
        ["Задача", "Макс. балл", "Описание", "Скоринг"],
        ["fast_algorithms", "100", "LRU Cache (Python): класс с get/put, O(1)",
         "AST-валидация, keywords, методы"],
        ["fast_code", "100", "Priority Queue + retry: Task, PriorityQueue, тесты",
         "JSON-ключи queue_code+test_code, heapq"],
        ["fast_reasoning", "100", "15 логических загадок (силлогизмы, числа)",
         "6 pts/вопрос × 15 = 90 + 10 бонус"],
        ["fast_system_design", "100", "URL-shortener: 100M URLs, 10K write/s, 100K read/s",
         "6 обязательных JSON-ключей"],
    ]
    td_t = Table(tasks_desc, colWidths=[38*mm, 18*mm, 72*mm, 38*mm])
    td_t.setStyle(table_style_main())
    story.append(td_t)
    story.append(Spacer(1, 3*mm))

    story.append(Paragraph("Модели и стоимость туннелей DataEyes", styles["h2"]))
    model_meta = [
        ["#", "Модель", "Вендор", "Input $/M", "Output $/M", "Тип"],
    ]
    for i, (mid, _) in enumerate(ranked, 1):
        vendor, fname, vkey = VENDOR_MAP.get(mid, (mid, mid, "deepseek"))
        pin, pout = PRICING.get(mid, (0, 0))
        mtype = "Thinking" if any(k in mid.lower() for k in ["thinking", "glm", "doubao", "mimo"]) else "Standard"
        model_meta.append([str(i), fname, vendor, f"${pin:.2f}", f"${pout:.2f}", mtype])
    mm_t = Table(model_meta, colWidths=[8*mm, 47*mm, 30*mm, 22*mm, 22*mm, 22*mm])
    mm_t.setStyle(table_style_main())
    story.append(mm_t)

    story.append(PageBreak())

    # ── PAGE 5: MAIN RESULTS TABLE ────────────────────────────────────────────
    story.append(Paragraph("Результаты — сводная таблица", styles["h1"]))
    story.append(HRFlowable(width="100%", thickness=1, color=C_BORDER, spaceAfter=4))
    story.append(Spacer(1, 2*mm))

    # Main leaderboard table
    lb_data = [["#", "Модель", "Вендор", "Avg\nScore", "Alg", "Code", "Reason", "SysDesign",
                "Avg\nLatency", "Стоимость\n4 задач"]]
    for i, (mid, mdata) in enumerate(ranked, 1):
        vendor, fname, vkey = VENDOR_MAP.get(mid, (mid, mid, "deepseek"))
        tasks = mdata["tasks"]
        alg = tasks.get("fast_algorithms", {}).get("score", 0)
        code = tasks.get("fast_code", {}).get("score", 0)
        reas = tasks.get("fast_reasoning", {}).get("score", 0)
        sysd = tasks.get("fast_system_design", {}).get("score", 0)
        lat_s = mdata["avg_latency_ms"] / 1000
        cost = mdata["total_cost"]
        lb_data.append([
            str(i),
            fname[:20],
            vendor,
            f"{mdata['avg_score']:.1f}",
            f"{alg:.0f}",
            f"{code:.0f}",
            f"{reas:.0f}",
            f"{sysd:.1f}",
            f"{lat_s:.1f}s",
            f"${cost:.4f}",
        ])
    lb_t = Table(lb_data, colWidths=[8, 45*mm, 28*mm, 15*mm, 12*mm, 12*mm, 15*mm, 19*mm, 16*mm, 18*mm])
    # Color top 3 rows
    style_lb = table_style_main()
    if len(ranked) >= 1:
        style_lb.add("BACKGROUND", (0, 1), (-1, 1), colors.HexColor("#1a2e1a"))
        style_lb.add("TEXTCOLOR", (3, 1), (3, 1), C_GREEN)
        style_lb.add("FONTNAME", (3, 1), (3, 1), "Arial-Bold")
    if len(ranked) >= 2:
        style_lb.add("BACKGROUND", (0, 2), (-1, 2), colors.HexColor("#1a1a2e"))
        style_lb.add("TEXTCOLOR", (3, 2), (3, 2), C_ACCENT2)
        style_lb.add("FONTNAME", (3, 2), (3, 2), "Arial-Bold")
    if len(ranked) >= 3:
        style_lb.add("BACKGROUND", (0, 3), (-1, 3), colors.HexColor("#2e1a1a"))
        style_lb.add("TEXTCOLOR", (3, 3), (3, 3), C_GOLD)
        style_lb.add("FONTNAME", (3, 3), (3, 3), "Arial-Bold")
    lb_t.setStyle(style_lb)
    story.append(lb_t)
    story.append(Spacer(1, 3*mm))
    story.append(Paragraph(
        "Все баллы по шкале 0–100. Avg Score = среднее арифметическое 4 задач. "
        "Стоимость рассчитана по официальным ценам DataEyes (input+output токены).",
        styles["note"]))

    story.append(PageBreak())

    # ── PAGE 6: SCORE BAR CHART ───────────────────────────────────────────────
    story.append(Paragraph("Рейтинг по среднему баллу", styles["h1"]))
    story.append(HRFlowable(width="100%", thickness=1, color=C_BORDER, spaceAfter=4))
    story.append(Spacer(1, 3*mm))

    bar_items = []
    for mid, mdata in ranked:
        vendor, fname, vkey = VENDOR_MAP.get(mid, (mid, mid, "deepseek"))
        vc = VENDOR_COLORS.get(vkey, C_ACCENT)
        bar_items.append((f"{fname} ({vendor})", mdata["avg_score"], vc))

    story.append(HorizontalBarChart(bar_items, width=PAGE_W - 2*MARGIN - 5, bar_h=24, gap=5))
    story.append(Spacer(1, 5*mm))

    # Per-task stacked comparison
    story.append(Paragraph("Результаты по задачам", styles["h2"]))
    story.append(Spacer(1, 2*mm))

    task_labels = ["fast_algorithms", "fast_code", "fast_reasoning", "fast_system_design"]
    task_display = ["Алгоритмы", "Кодогенерация", "Рассуждения", "Сис. дизайн"]

    for task_id, task_disp in zip(task_labels, task_display):
        story.append(Paragraph(task_disp, styles["h3"]))
        task_items = []
        for mid, mdata in ranked:
            vendor, fname, vkey = VENDOR_MAP.get(mid, (mid, mid, "deepseek"))
            vc = VENDOR_COLORS.get(vkey, C_ACCENT)
            score = mdata["tasks"].get(task_id, {}).get("score", 0)
            task_items.append((f"{fname}", score, vc))
        story.append(HorizontalBarChart(task_items, width=PAGE_W - 2*MARGIN - 5,
                                         bar_h=14, gap=3))
        story.append(Spacer(1, 2*mm))

    story.append(PageBreak())

    # ── PAGE 7: COST & LATENCY ANALYSIS ──────────────────────────────────────
    story.append(Paragraph("Анализ стоимости и производительности", styles["h1"]))
    story.append(HRFlowable(width="100%", thickness=1, color=C_BORDER, spaceAfter=4))
    story.append(Spacer(1, 3*mm))

    # Score vs Cost scatter
    story.append(Paragraph("Score vs Стоимость (цена/качество)", styles["h2"]))
    scatter_data = []
    for mid, mdata in ranked:
        vendor, fname, vkey = VENDOR_MAP.get(mid, (mid, mid, "deepseek"))
        vc = VENDOR_COLORS.get(vkey, C_ACCENT)
        scatter_data.append((fname[:15], mdata["avg_score"], mdata["total_cost"], vc))
    story.append(ScatterPlot(scatter_data, width=PAGE_W - 2*MARGIN, height=200))
    story.append(Spacer(1, 2*mm))
    story.append(Paragraph(
        "Точки ближе к верхнему левому углу (высокий балл, низкая стоимость) — "
        "наилучшее соотношение цена/качество.",
        styles["caption"]))
    story.append(Spacer(1, 4*mm))

    # Efficiency table (score per $)
    story.append(Paragraph("Эффективность (баллов на $1 затрат)", styles["h2"]))
    eff_ranked = sorted(
        [(mid, mdata) for mid, mdata in models.items()],
        key=lambda x: (x[1]["avg_score"] / x[1]["total_cost"]) if x[1]["total_cost"] > 0 else 0,
        reverse=True,
    )
    eff_data = [["#", "Модель", "Avg Score", "Стоимость", "Score/$1", "Latency avg"]]
    for i, (mid, mdata) in enumerate(eff_ranked, 1):
        vendor, fname, vkey = VENDOR_MAP.get(mid, (mid, mid, "deepseek"))
        eff = mdata["avg_score"] / mdata["total_cost"] if mdata["total_cost"] > 0 else 0
        eff_data.append([
            str(i),
            fname[:22],
            f"{mdata['avg_score']:.2f}",
            f"${mdata['total_cost']:.5f}",
            f"{eff:,.0f}",
            f"{mdata['avg_latency_ms']/1000:.1f}s",
        ])
    eff_t = Table(eff_data, colWidths=[10*mm, 55*mm, 22*mm, 25*mm, 30*mm, 25*mm])
    eff_style = table_style_main()
    eff_t.setStyle(eff_style)
    story.append(eff_t)
    story.append(Spacer(1, 3*mm))

    # Latency comparison
    story.append(Paragraph("Средняя латентность (сек/задача)", styles["h2"]))
    lat_items = []
    for mid, mdata in sorted(models.items(), key=lambda x: x[1]["avg_latency_ms"]):
        vendor, fname, vkey = VENDOR_MAP.get(mid, (mid, mid, "deepseek"))
        vc = VENDOR_COLORS.get(vkey, C_ACCENT)
        lat_s = mdata["avg_latency_ms"] / 1000
        lat_items.append((f"{fname} ({vendor})", lat_s, vc))
    max_lat = max(x[1] for x in lat_items) if lat_items else 1
    lat_chart_items = [(label, val/max_lat*100, color) for label, val, color in lat_items]
    story.append(Paragraph(
        "(100% = максимальная латентность среди протестированных)", styles["note"]))
    story.append(HorizontalBarChart(lat_chart_items, width=PAGE_W - 2*MARGIN - 5,
                                     bar_h=18, gap=4))
    story.append(Spacer(1, 2*mm))

    lat_table_data = [["Модель", "Avg Latency", "Max Latency", "Avg TPS"]]
    for mid, mdata in sorted(models.items(), key=lambda x: x[1]["avg_latency_ms"]):
        vendor, fname, vkey = VENDOR_MAP.get(mid, (mid, mid, "deepseek"))
        lat_table_data.append([
            f"{fname}",
            f"{mdata['avg_latency_ms']/1000:.1f}s",
            f"{mdata['max_latency_ms']/1000:.1f}s",
            f"{mdata['avg_tps']:.1f}",
        ])
    lat_t = Table(lat_table_data, colWidths=[70*mm, 30*mm, 30*mm, 30*mm])
    lat_t.setStyle(table_style_main())
    story.append(lat_t)

    story.append(PageBreak())

    # ── PAGE 8: DETAILED RESULTS PER MODEL ────────────────────────────────────
    story.append(Paragraph("Детальные результаты по моделям", styles["h1"]))
    story.append(HRFlowable(width="100%", thickness=1, color=C_BORDER, spaceAfter=4))
    story.append(Spacer(1, 2*mm))

    for rank_i, (mid, mdata) in enumerate(ranked, 1):
        vendor, fname, vkey = VENDOR_MAP.get(mid, (mid, mid, "deepseek"))
        vc = VENDOR_COLORS.get(vkey, C_ACCENT)
        pin, pout = PRICING.get(mid, (0, 0))

        title_data = [[f"{medal(rank_i)} {fname}", f"Avg: {mdata['avg_score']:.2f} pts"]]
        tt = Table(title_data, colWidths=[120*mm, 40*mm])
        tt.setStyle(TableStyle([
            ("BACKGROUND",   (0, 0), (-1, 0), vc),
            ("TEXTCOLOR",    (0, 0), (-1, 0), C_WHITE),
            ("FONTNAME",     (0, 0), (-1, 0), "Arial-Bold"),
            ("FONTSIZE",     (0, 0), (-1, 0), 10),
            ("ALIGN",        (1, 0), (1, 0),  "RIGHT"),
            ("TOPPADDING",   (0, 0), (-1, 0), 7),
            ("BOTTOMPADDING",(0, 0), (-1, 0), 7),
            ("LEFTPADDING",  (0, 0), (-1, 0), 10),
            ("RIGHTPADDING", (0, 0), (-1, 0), 10),
        ]))
        story.append(KeepTogether([
            tt,
            Spacer(1, 2*mm),
        ]))

        det_data = [["Задача", "Балл", "Latency", "In tok", "Out tok", "TPS", "Стоимость"]]
        for task_id in ["fast_algorithms", "fast_code", "fast_reasoning", "fast_system_design"]:
            t = mdata["tasks"].get(task_id, {})
            task_disp = task_id.replace("fast_", "").title()
            det_data.append([
                task_disp,
                f"{t.get('score', 0):.0f}",
                f"{(t.get('latency_ms') or 0)/1000:.1f}s",
                str(t.get("input_tokens", "-")),
                str(t.get("output_tokens", "-")),
                f"{t.get('tps', 0):.1f}",
                f"${t.get('cost_usd', 0):.5f}",
            ])
        # Total row
        det_data.append([
            "ИТОГО",
            f"{mdata['avg_score']:.2f}",
            f"{mdata['avg_latency_ms']/1000:.1f}s",
            str(mdata["total_input_tokens"]),
            str(mdata["total_output_tokens"]),
            f"{mdata['avg_tps']:.1f}",
            f"${mdata['total_cost']:.5f}",
        ])
        det_t = Table(det_data, colWidths=[30*mm, 14*mm, 18*mm, 18*mm, 18*mm, 14*mm, 22*mm])
        ds = table_style_main()
        ds.add("FONTNAME", (0, -1), (-1, -1), "Arial-Bold")
        ds.add("BACKGROUND", (0, -1), (-1, -1), C_SURFACE)
        ds.add("TEXTCOLOR", (1, -1), (1, -1), C_ACCENT)
        det_t.setStyle(ds)
        story.append(det_t)

        # Pricing note
        story.append(Paragraph(
            f"Цены DataEyes: ${pin:.2f}/M input · ${pout:.2f}/M output · "
            f"Вендор: {vendor}",
            styles["note"]))
        story.append(Spacer(1, 4*mm))

    story.append(PageBreak())

    # ── PAGE 9: VENDOR COMPARISON ─────────────────────────────────────────────
    story.append(Paragraph("Сравнение вендоров", styles["h1"]))
    story.append(HRFlowable(width="100%", thickness=1, color=C_BORDER, spaceAfter=4))
    story.append(Spacer(1, 2*mm))

    story.append(Paragraph(
        "Каждый вендор представлен своим cheapest frontier-туннелем через DataEyes.ai. "
        "Оценка отражает доступность модели по минимальной цене при максимальном качестве.",
        styles["body"]))
    story.append(Spacer(1, 3*mm))

    vendor_data = [["Вендор", "Модель (туннель)", "Score", "$/1M in", "$/1M out",
                    "Latency", "Best для"]]
    use_cases = {
        "gemini-3-pro-preview":       "Reasoning, vision, multimodal",
        "gpt-5.5":                    "Код, инструкции, enterprise",
        "claude-fable-5":             "Длинный контекст, анализ (Claude 5)",
        "deepseek-v4-pro":            "Frontier-код, RAG, batch",
        "gemini-2.5-pro-nothinking":  "Быстрый reasoning, мультимодал",
        "gpt-4.1":                    "Код, инструкции, enterprise",
        "deepseek-v3-250324":         "Дешёвый frontier, код, RAG",
        "qwen3.7-max":                "Многоязычность, Chinese NLP",
        "doubao-seed-2-0-pro-260215": "Streaming, thinking, агенты",
        "MiniMax-M2.7":               "Доступность, скорость",
        "kimi-k2-thinking":           "Deep reasoning, math",
        "glm-5-turbo":                "Китайский рынок, GLM",
        "mimo-v2.5-pro":              "Reasoning, math olympiad",
    }
    for mid, mdata in ranked:
        vendor, fname, vkey = VENDOR_MAP.get(mid, (mid, mid, "deepseek"))
        pin, pout = PRICING.get(mid, (0, 0))
        lat_s = mdata["avg_latency_ms"] / 1000
        vendor_data.append([
            vendor,
            fname[:22],
            f"{mdata['avg_score']:.2f}",
            f"${pin:.2f}",
            f"${pout:.2f}",
            f"{lat_s:.1f}s",
            use_cases.get(mid, "-")[:25],
        ])
    vend_t = Table(vendor_data, colWidths=[22*mm, 40*mm, 16*mm, 16*mm, 16*mm, 15*mm, 40*mm])
    vend_t.setStyle(table_style_main())
    story.append(vend_t)
    story.append(Spacer(1, 4*mm))

    # Pricing tiers explanation
    story.append(Paragraph("Ценовые категории (cheapest frontier через DataEyes)", styles["h2"]))
    # Dynamic tier table from actual run pricing
    _tier_rows: list[tuple[float, str, str]] = []
    for _mid, _md in ranked:
        _pin, _ = PRICING.get(_mid, (0, 0))
        _vn, _fn, _ = VENDOR_MAP.get(_mid, (_mid, _mid, "deepseek"))
        _tier_rows.append((_pin, _fn, _vn))
    _tier_rows.sort()

    def _tier_label(pin):
        if pin <= 0.30: return "Ultra Cheap (< $0.30/M)"
        if pin <= 0.70: return "Cheap ($0.30–$0.70/M)"
        if pin <= 1.50: return "Mid ($0.70–$1.50/M)"
        return "Premium (> $1.50/M)"

    from collections import defaultdict as _dd
    _tier_buckets = _dd(list)
    for _pin, _fn, _vn in _tier_rows:
        _tier_buckets[_tier_label(_pin)].append(f"{_fn} (${_pin:.2f})")

    tier_data = [["Tier", "Модели в тесте"]]
    for _tlabel in ["Ultra Cheap (< $0.30/M)", "Cheap ($0.30–$0.70/M)",
                    "Mid ($0.70–$1.50/M)", "Premium (> $1.50/M)"]:
        if _tlabel in _tier_buckets:
            tier_data.append([_tlabel, ", ".join(_tier_buckets[_tlabel])])
    tier_t = Table(tier_data, colWidths=[52*mm, 113*mm])
    tier_t.setStyle(table_style_main())
    story.append(tier_t)

    story.append(PageBreak())

    # ── PAGE 10: CONCLUSIONS ──────────────────────────────────────────────────
    story.append(Paragraph("Выводы и рекомендации", styles["h1"]))
    story.append(HRFlowable(width="100%", thickness=1, color=C_BORDER, spaceAfter=4))
    story.append(Spacer(1, 3*mm))

    story.append(Paragraph("Итоговый рейтинг", styles["h2"]))
    final_lb = [["Место", "Модель", "Вендор", "Avg Score", "Стоимость", "Рекомендация"]]
    recs = {
        1: "Лучший overall", 2: "Топ-2 overall", 3: "Топ-3",
    }
    for i, (mid, mdata) in enumerate(ranked, 1):
        vendor, fname, vkey = VENDOR_MAP.get(mid, (mid, mid, "deepseek"))
        final_lb.append([
            medal(i),
            fname,
            vendor,
            f"{mdata['avg_score']:.2f}",
            f"${mdata['total_cost']:.4f}",
            recs.get(i, "Высокий уровень"),
        ])
    fl_t = Table(final_lb, colWidths=[12*mm, 47*mm, 28*mm, 18*mm, 20*mm, 35*mm])
    fl_style = table_style_main()
    if len(ranked) >= 1:
        fl_style.add("BACKGROUND", (0, 1), (-1, 1), colors.HexColor("#1a2e1a"))
        fl_style.add("FONTNAME", (0, 1), (-1, 1), "Arial-Bold")
    fl_t.setStyle(fl_style)
    story.append(fl_t)
    story.append(Spacer(1, 4*mm))

    # Recommendations by use case
    story.append(Paragraph("Рекомендации по сценарию использования", styles["h2"]))
    story.append(Spacer(1, 2*mm))

    _best_value_id = min(
        ((mid, md) for mid, md in models.items() if md["avg_score"] > 70),
        key=lambda x: x[1]["total_cost"],
        default=(ranked[-1][0], ranked[-1][1])
    )[0]
    _fastest_id2 = min(models.items(), key=lambda x: x[1]["avg_latency_ms"])[0]
    _best_reas_id2 = max(
        models.items(),
        key=lambda x: x[1]["tasks"].get("fast_reasoning", {}).get("score", 0)
    )[0]
    _cheapest_id = min(
        models.keys(),
        key=lambda mid: PRICING.get(mid, (999, 0))[0]
    )
    _cjk_candidates = ["qwen3.7-max", "glm-5-turbo", "doubao-seed-2-0-pro-260215"]
    _cjk_id = next((m for m in _cjk_candidates if m in models), _cheapest_id)

    rec_items = [
        ("Максимальное качество без ограничений бюджета",
         ranked[0][0] if ranked else "—",
         f"Лидер рейтинга с avg {ranked[0][1]['avg_score']:.2f} pts" if ranked else ""),
        ("Лучшее соотношение цена/качество",
         _best_value_id,
         f"Минимальная стоимость при score > 70: ${models[_best_value_id]['total_cost']:.4f}"),
        ("Минимальная latency (real-time приложения)",
         _fastest_id2,
         f"Fastest: {models[_fastest_id2]['avg_latency_ms']/1000:.1f}s avg"),
        ("Reasoning / математика / логика",
         _best_reas_id2,
         f"Лучший балл на fast_reasoning: {models[_best_reas_id2]['tasks'].get('fast_reasoning',{}).get('score',0):.0f}/100"),
        ("Дешёвый frontier (RAG, batch-обработка)",
         _cheapest_id,
         f"Cheapest туннель: ${PRICING.get(_cheapest_id,(0,0))[0]:.2f}/M input"),
        ("Китайский рынок / многоязычность",
         _cjk_id,
         "Лучшая поддержка CJK и многоязычных задач"),
    ]
    for uc, model_id, note in rec_items:
        vendor, fname, vkey = VENDOR_MAP.get(model_id, (model_id, model_id, "deepseek"))
        vc = VENDOR_COLORS.get(vkey, C_ACCENT)
        mid_data = models.get(model_id, {})
        avg_s = mid_data.get("avg_score", 0)
        story.append(Paragraph(
            f"<b>{uc}:</b>", styles["h3"]))
        story.append(Paragraph(
            f"→ <b>{fname}</b> ({vendor}) · {avg_s:.1f} pts · {note}",
            styles["body"]))
        story.append(Spacer(1, 1.5*mm))

    story.append(Spacer(1, 4*mm))
    story.append(HRFlowable(width="100%", thickness=1, color=C_BORDER, spaceAfter=4))
    story.append(Spacer(1, 2*mm))

    story.append(Paragraph("Техническая конфигурация", styles["h2"]))
    tech_data = [
        ["Компонент", "Конфигурация"],
        ["Сервис", "FastAPI benchsvc · Python 3.13 · порт 8001"],
        ["LLM-шлюз", "LiteLLM Proxy v1.x (Docker) · порт 4000"],
        ["API", "cloud.dataeyes.ai/v1 (OpenAI-compatible)"],
        ["База данных", "PostgreSQL 16 (Docker) · Alembic migrations"],
        ["Артефакты", "RustFS S3 (Docker) · bucket: benchmark-artifacts"],
        ["Трейсинг", "Langfuse Cloud · https://cloud.langfuse.com"],
        ["Скоринг", "Детерминированный (без LLM-судьи) · AST + regex + JSON"],
        ["Версия бенчмарка", "BENCHMARK_VERSION=2026-06-10.5"],
    ]
    tech_t = Table(tech_data, colWidths=[40*mm, 120*mm])
    tech_t.setStyle(table_style_main())
    story.append(tech_t)

    story.append(Spacer(1, 4*mm))
    story.append(Paragraph(
        f"Отчёт сгенерирован автоматически · Run ID: {run_id} · "
        f"DataEyes Model Bench · {datetime.now().strftime('%d.%m.%Y %H:%M')}",
        styles["note"]))

    # ── Build ─────────────────────────────────────────────────────────────────
    print(f"  Генерация PDF: {output_path}")
    doc.build(
        story,
        onFirstPage=pt.on_first_page,
        onLaterPages=pt.on_later_pages,
    )
    print(f"  ✓ PDF создан: {output_path}")
    return output_path


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")

    run_id = sys.argv[1] if len(sys.argv) > 1 else None
    output = sys.argv[2] if len(sys.argv) > 2 else \
        os.path.expanduser("~/Desktop/DataEyes_Frontier_Benchmark.pdf")

    if not run_id:
        # Auto-detect latest completed run
        import psycopg
        db_url = os.getenv(
            "DATABASE_URL",
            "postgresql://benchmark:benchmark@localhost:5432/benchmark",
        ).replace("postgresql+psycopg://", "postgresql://")
        with psycopg.connect(db_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id FROM benchmark_runs "
                    "WHERE status IN ('completed', 'partial') "
                    "ORDER BY created_at DESC LIMIT 1"
                )
                row = cur.fetchone()
                if not row:
                    print("ERROR: No completed runs found in database")
                    sys.exit(1)
                run_id = str(row[0])
        print(f"  Auto-detected latest run: {run_id}")

    build_report(run_id, output)
