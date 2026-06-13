#!/usr/bin/env python3
"""Render the DataEyes partner pricing tables for the commercial proposal (КП).

Single source of truth = benchsvc.scoring. Run from model-bench/:

    .venv/bin/python scripts/compute_partner_pricing.py

The Markdown it prints is pasted verbatim into
dataeyes-docs/proposal/kp-dataeyes-partners-ru.md so КП numbers always match
the benchmark's pricing model.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from benchsvc.scoring import (  # noqa: E402
    DATAEYES_DISCOUNT_RANGE,
    DATAEYES_STABLE_COEFF,
    REP_MARGIN,
    VENDOR_PRICING,
    partner_price_per_million,
)

# Display order + vendor + tier label (real DataEyes catalog).
CATALOG = [
    ("claude-opus-4-6", "Anthropic", "Премиум"),
    ("gpt-5.4", "OpenAI", "Премиум"),
    ("gemini-3.1-pro-preview", "Google", "Премиум"),
    ("qwen3.6-plus", "Alibaba", "Премиум"),
    ("glm-5", "Z.AI", "Средний"),
    ("kimi-k2.5", "Moonshot", "Средний"),
    ("doubao-seed-2-0-pro-260215", "ByteDance", "Средний"),
    ("deepseek-v3.2-251201", "DeepSeek", "Эконом"),
    ("minimax-m2.5", "MiniMax", "Эконом"),
]


def fmt(x: float) -> str:
    s = f"{x:.3f}".rstrip("0").rstrip(".")
    return s


def main() -> None:
    print(f"REP_MARGIN = {REP_MARGIN:.0%}\n")
    header = (
        "| Модель | Вендор | Класс | Vendor-прайс вход/выход $/1M | "
        "Ваша цена вход/выход $/1M | Экономия vs vendor | Диапазон скидки DataEyes |"
    )
    sep = "|---|---|---|---|---|---:|---:|"
    print(header)
    print(sep)
    for model, vendor, tier in CATALOG:
        vin, vout = VENDOR_PRICING[model]
        pin, pout = partner_price_per_million(model)
        coeff = DATAEYES_STABLE_COEFF[model]
        factor = coeff * (1 + REP_MARGIN)
        econ = round((1 - factor) * 100)
        _dmin, dmax = DATAEYES_DISCOUNT_RANGE[model]
        print(
            f"| {model} | {vendor} | {tier} | {fmt(vin)} / {fmt(vout)} | "
            f"**{fmt(pin)} / {fmt(pout)}** | −{econ}% | до −{dmax}% |"
        )


if __name__ == "__main__":
    main()
