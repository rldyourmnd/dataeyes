#!/usr/bin/env python3
"""Direct benchmark runner — no HTTP server required."""
import sys
import time

sys.path.insert(0, "src")

from benchsvc.settings import get_settings
from benchsvc.db import SessionLocal
from benchsvc.benchmarks import BenchmarkRunner
from benchsvc.schemas import BenchmarkRunRequest

settings = get_settings()
db = SessionLocal()

runner = BenchmarkRunner(settings=settings, db=db)
request = BenchmarkRunRequest(suite="fast")

print("=== Запуск финального прогона (fast suite, 10 моделей) ===", flush=True)
t0 = time.time()
result = runner.run(request)
elapsed = time.time() - t0

print(f"\n=== ФИНИШ ===", flush=True)
print(f"run_id:        {result.run_id}", flush=True)
print(f"status:        {result.status}", flush=True)
print(f"models_tested: {result.models_tested}", flush=True)
print(f"elapsed:       {elapsed:.0f}s", flush=True)

summary = result.summary or {}
print(f"\nSummary:", flush=True)
for k, v in summary.items():
    print(f"  {k}: {v}", flush=True)

print("\nPer-model results:", flush=True)
from collections import defaultdict
by_model = defaultdict(list)
for r in result.results:
    by_model[r.model].append(r)

import statistics
for model, cases in sorted(by_model.items(), key=lambda x: -statistics.mean(c.score or 0 for c in x[1])):
    avg = statistics.mean(c.score or 0 for c in cases)
    total_cost = sum(c.estimated_cost_usd or 0 for c in cases)
    total_tok = sum(c.total_tokens or 0 for c in cases)
    print(f"  {model:<45} avg={avg:6.2f}  tokens={total_tok:6d}  cost=${total_cost:.4f}", flush=True)

db.close()
