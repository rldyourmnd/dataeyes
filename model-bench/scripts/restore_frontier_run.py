"""Insert the known-good results from the frontier benchmark run b7bf71d1."""
import sys
sys.path.insert(0, "src")

from datetime import datetime, timezone
from benchsvc.db import engine
from sqlalchemy import text

RUN_ID = "b7bf71d1-574a-4e11-93cf-70e8049a06d6"
CREATED_AT = "2026-06-09 20:00:00+00"

# All 40 rows from the frontier run (captured before DB was wiped)
# claude errors will be re-run fresh; we insert them as-is so run totals are complete
RESULTS = [
    ("dataeyes/claude-opus-4-8",      "code_generation",     "error",  0,  528,   None,   None, None, None, "Error code: 400 - {'error': {'message': 'litellm.BadRequestError: OpenAIException'}}"),
    ("dataeyes/claude-opus-4-8",      "instruction_strict",  "error",  0,  630,   None,   None, None, None, "Error code: 400 - {'error': {'message': 'litellm.BadRequestError: OpenAIException'}}"),
    ("dataeyes/claude-opus-4-8",      "long_context_qa",     "error",  0,  546,   None,   None, None, None, "Error code: 400 - {'error': {'message': 'litellm.BadRequestError: OpenAIException'}}"),
    ("dataeyes/claude-opus-4-8",      "reasoning_multistep", "error",  0,  490,   None,   None, None, None, "Error code: 400 - {'error': {'message': 'litellm.BadRequestError: OpenAIException'}}"),
    ("dataeyes/deepseek-v3.2-exp",    "code_generation",     "passed", 95, 12969, 368,    572,  44.1, None, None),
    ("dataeyes/deepseek-v3.2-exp",    "instruction_strict",  "passed", 100,11924, 387,    538,  45.1, None, None),
    ("dataeyes/deepseek-v3.2-exp",    "long_context_qa",     "passed", 80, 2911,  850,    97,   33.3, None, None),
    ("dataeyes/deepseek-v3.2-exp",    "reasoning_multistep", "passed", 100,5746,  377,    219,  38.1, None, None),
    ("dataeyes/deepseek-v4-flash",    "code_generation",     "passed", 100,43874, 368,    1522, 34.7, None, None),
    ("dataeyes/deepseek-v4-flash",    "instruction_strict",  "passed", 90, 15947, 387,    952,  59.7, None, None),
    ("dataeyes/deepseek-v4-flash",    "long_context_qa",     "passed", 100,10284, 850,    1502, 146.1,None, None),
    ("dataeyes/deepseek-v4-flash",    "reasoning_multistep", "passed", 100,11422, 400,    659,  57.7, None, None),
    ("dataeyes/gemini-3.5-flash",     "code_generation",     "passed", 100,14650, 381,    2843, 194.1,None, None),
    ("dataeyes/gemini-3.5-flash",     "instruction_strict",  "passed", 100,11103, 409,    2210, 199.0,None, None),
    ("dataeyes/gemini-3.5-flash",     "long_context_qa",     "passed", 100,13063, 955,    2753, 210.7,None, None),
    ("dataeyes/gemini-3.5-flash",     "reasoning_multistep", "failed", 0,  5612,  428,    843,  150.2,None, None),
    ("dataeyes/gemini-3-pro-preview", "code_generation",     "passed", 100,26547, 381,    3327, 125.3,None, None),
    ("dataeyes/gemini-3-pro-preview", "instruction_strict",  "passed", 100,23697, 409,    3102, 130.9,None, None),
    ("dataeyes/gemini-3-pro-preview", "long_context_qa",     "passed", 100,16325, 955,    2273, 139.2,None, None),
    ("dataeyes/gemini-3-pro-preview", "reasoning_multistep", "passed", 100,14364, 428,    1538, 107.1,None, None),
    ("dataeyes/gpt-5",                "code_generation",     "passed", 100,10406, 1803,   924,  88.8, None, None),
    ("dataeyes/gpt-5",                "instruction_strict",  "passed", 90, 14475, 1816,   1191, 82.3, None, None),
    ("dataeyes/gpt-5",                "long_context_qa",     "passed", 100,23745, 2286,   1600, 67.4, None, None),
    ("dataeyes/gpt-5",                "reasoning_multistep", "passed", 100,9187,  1821,   475,  51.7, None, None),
    ("dataeyes/gpt-5.5",              "code_generation",     "passed", 100,15924, 5443,   785,  49.3, None, None),
    ("dataeyes/gpt-5.5",              "instruction_strict",  "passed", 100,13510, 672,    528,  39.1, None, None),
    ("dataeyes/gpt-5.5",              "long_context_qa",     "passed", 100,10694, 1142,   416,  38.9, None, None),
    ("dataeyes/gpt-5.5",             "reasoning_multistep",  "passed", 100,6988,  5461,   277,  39.6, None, None),
    ("dataeyes/kimi-k2.6",            "code_generation",     "passed", 100,518720,363,    461,  0.9,  None, None),
    ("dataeyes/kimi-k2.6",            "instruction_strict",  "passed", 100,513790,382,    513,  1.0,  None, None),
    ("dataeyes/kimi-k2.6",            "long_context_qa",     "passed", 80, 2281,  833,    80,   35.1, None, None),
    ("dataeyes/kimi-k2.6",            "reasoning_multistep", "passed", 100,86275, 383,    2098, 24.3, None, None),
    ("dataeyes/o3",                   "code_generation",     "passed", 100,17667, 363,    2355, 133.3,None, None),
    ("dataeyes/o3",                   "instruction_strict",  "passed", 100,10924, 376,    1057, 96.8, None, None),
    ("dataeyes/o3",                   "long_context_qa",     "passed", 100,20333, 846,    1318, 64.8, None, None),
    ("dataeyes/o3",                   "reasoning_multistep", "passed", 100,8590,  381,    677,  78.8, None, None),
    ("dataeyes/o4-mini",              "code_generation",     "passed", 100,29035, 363,    1654, 57.0, None, None),
    ("dataeyes/o4-mini",              "instruction_strict",  "passed", 100,26126, 376,    2442, 93.5, None, None),
    ("dataeyes/o4-mini",              "long_context_qa",     "passed", 100,9396,  846,    1367, 145.5,None, None),
    ("dataeyes/o4-mini",             "reasoning_multistep",  "passed", 100,11328, 381,    1094, 96.6, None, None),
]

with engine.connect() as conn:
    # Insert the run record
    conn.execute(text("""
        INSERT INTO benchmark_runs (id, suite, status, created_at, completed_at, summary)
        VALUES (:id, 'deep_eval', 'partial', :created_at, :created_at, :summary)
        ON CONFLICT (id) DO NOTHING
    """), {"id": RUN_ID, "created_at": CREATED_AT,
           "summary": '{"tag":"frontier_v1","restored":true,"total":40,"passed":35,"failed":1,"errors":4}'})

    inserted = 0
    for r in RESULTS:
        model, case_id, status, score, lat_ms, inp_tok, out_tok, tps, cost, err = r
        total_tok = (inp_tok or 0) + (out_tok or 0) if inp_tok or out_tok else None
        conn.execute(text("""
            INSERT INTO model_results
              (id, run_id, model, suite, case_id, status, score,
               latency_ms_total, input_tokens, output_tokens, total_tokens,
               tokens_per_second, estimated_cost_usd, cost_status,
               json_valid, schema_valid, error_message, created_at)
            VALUES
              (gen_random_uuid(), :run_id, :model, 'deep_eval', :case_id, :status, :score,
               :lat_ms, :inp_tok, :out_tok, :total_tok,
               :tps, :cost, 'unavailable',
               :jv, NULL, :err, :created_at)
            ON CONFLICT DO NOTHING
        """), {
            "run_id": RUN_ID, "model": model, "case_id": case_id,
            "status": status, "score": score, "lat_ms": lat_ms,
            "inp_tok": inp_tok, "out_tok": out_tok, "total_tok": total_tok,
            "tps": tps, "cost": cost, "err": err, "created_at": CREATED_AT,
            "jv": status != "error",
        })
        inserted += 1

    conn.commit()
    print(f"Inserted run {RUN_ID} with {inserted} results")
