"""
Long synthetic technical document for ultra_long_context benchmark task.

The document is a dense 4000-word evaluation report with specific numbers
scattered throughout. 12 questions with deterministic answers are appended.
"""

LONG_DOC = """
═══════════════════════════════════════════════════════════════════════════════
DataEyes AI Infrastructure Evaluation Report — Q2 2026
Internal Document: Strictly Confidential
Prepared by: Platform Engineering Team
Document ID: DE-EVAL-2026-Q2-0047
═══════════════════════════════════════════════════════════════════════════════

EXECUTIVE SUMMARY
─────────────────
This report presents findings from the DataEyes AI Infrastructure evaluation
conducted between April 1 and May 31, 2026 covering 14 frontier model providers,
3 infrastructure tiers, and 6 geographical deployment regions. The evaluation
processed a total of 2,847,391 API calls consuming 18.3 billion tokens at a
blended average cost of $0.00043 per 1,000 tokens. Infrastructure uptime across
all regions averaged 99.71%, with the lowest availability recorded in the
Singapore (AP-SE-1) region at 98.94%. The highest throughput region was
US-EAST-1 at 4,420 requests per second peak.

The top-performing model for general-purpose tasks was Gemini-3.5-Flash with
a mean accuracy score of 94.2 / 100 and a median first-token latency of 187ms.
The most cost-efficient model was MiniMax-M2.7 at $0.000018 per 1K output tokens.
The highest-context model evaluated was GLM-5-Turbo with a verified 1,048,576
token context window. DeepSeek-V4-Flash demonstrated the fastest sustained
throughput at 312 tokens/second under concurrent load.

──────────────────────────────────────────────────────────────────────────────
SECTION 1: EVALUATION SCOPE AND METHODOLOGY
──────────────────────────────────────────────────────────────────────────────

1.1 Models Under Test
The evaluation covered the following 14 model endpoints:

  MODEL_ID                     PROVIDER         CONTEXT_WINDOW  INPUT_$/1M  OUTPUT_$/1M
  ─────────────────────────────────────────────────────────────────────────────────────
  gpt-5.5                      OpenAI            256,000          $4.50       $18.00
  gpt-4.5-turbo                OpenAI            128,000          $2.50       $10.00
  claude-fable-5               Anthropic         200,000          $5.00       $20.00
  claude-haiku-5               Anthropic         200,000          $0.40        $1.60
  gemini-3.5-flash             Google DeepMind   1,000,000        $0.10        $0.40
  gemini-3.5-pro               Google DeepMind   1,000,000        $1.25        $5.00
  deepseek-v4-flash            DeepSeek          65,536           $0.07        $0.28
  deepseek-v4-pro              DeepSeek          65,536           $0.55        $2.20
  qwen3.7-max                  Alibaba Cloud     131,072          $0.80        $3.20
  qwen3.7-turbo                Alibaba Cloud     131,072          $0.15        $0.60
  kimi-k2-thinking             Moonshot AI       131,072          $1.20        $4.80
  MiniMax-M2.7                 MiniMax           65,536           $0.004       $0.018
  glm-5-turbo                  Zhipu AI         1,048,576         $0.10        $0.40
  doubao-seed-2-0-pro-260215   ByteDance         262,144          $0.25        $1.00

1.2 Evaluation Dimensions
Each model was evaluated across 7 dimensions:
  (a) Reasoning accuracy         — 30% weight
  (b) Code generation quality    — 20% weight
  (c) Instruction following      — 15% weight
  (d) Long-context faithfulness  — 15% weight
  (e) Throughput (tok/s)         — 10% weight
  (f) First-token latency (P50)  — 5%  weight
  (g) Cost efficiency            — 5%  weight

Composite scores were calculated as weighted averages, normalised to 100.

1.3 Test Infrastructure
All tests were run on DataEyes Cloud infrastructure:
  • Regions: US-EAST-1, US-WEST-2, EU-WEST-1, AP-SE-1, AP-NE-1, ME-SOUTH-1
  • Gateway: LiteLLM Proxy v1.43.2 with Redis-backed rate limiting
  • Observability: Langfuse Cloud with OTEL export, 15-second flush interval
  • Database: PostgreSQL 17.2 on r6g.2xlarge, 3-node HA cluster
  • Storage: RustFS v0.9.4, 12-node erasure-coded cluster, 3.2 PB usable

──────────────────────────────────────────────────────────────────────────────
SECTION 2: LATENCY AND THROUGHPUT RESULTS
──────────────────────────────────────────────────────────────────────────────

2.1 First-Token Latency (TTFT)
Measured at P50 / P95 / P99 under 50 concurrent users (ms):

  MODEL                        P50     P95     P99
  ────────────────────────────────────────────────
  gpt-5.5                      210     490     820
  gpt-4.5-turbo                185     440     710
  claude-fable-5               240     570     940
  claude-haiku-5               105     230     380
  gemini-3.5-flash             187     370     590
  gemini-3.5-pro               320     680    1100
  deepseek-v4-flash             98     210     340
  deepseek-v4-pro              280     610    1020
  qwen3.7-max                  445     980    1800
  qwen3.7-turbo                155     320     520
  kimi-k2-thinking            1240    2800    5400
  MiniMax-M2.7                  77     165     270
  glm-5-turbo                  198     420     680
  doubao-seed-2-0-pro-260215   310     670    1090

2.2 Sustained Throughput (tokens/second, averaged over 60s burst)

  MODEL                        MIN     AVG     MAX
  ──────────────────────────────────────────────────
  gpt-5.5                       48      87     134
  gpt-4.5-turbo                 55      95     148
  claude-fable-5                42      78     121
  claude-haiku-5               180     240     310
  gemini-3.5-flash             140     198     261
  gemini-3.5-pro                68     112     165
  deepseek-v4-flash            210     312     408
  deepseek-v4-pro               80     130     188
  qwen3.7-max                   22      41      67
  qwen3.7-turbo                120     178     235
  kimi-k2-thinking              18      34      55
  MiniMax-M2.7                 195     268     340
  glm-5-turbo                  105     162     220
  doubao-seed-2-0-pro-260215    44      79     118

──────────────────────────────────────────────────────────────────────────────
SECTION 3: ACCURACY AND QUALITY SCORES
──────────────────────────────────────────────────────────────────────────────

3.1 Composite Weighted Score (0–100)

  MODEL                        SCORE   RANK
  ──────────────────────────────────────────
  gemini-3.5-flash              94.2     1
  gpt-5.5                       93.8     2
  claude-fable-5                92.1     3
  MiniMax-M2.7                  91.7     4
  qwen3.7-max                   90.4     5
  glm-5-turbo                   89.9     6
  doubao-seed-2-0-pro-260215    89.3     7
  kimi-k2-thinking              88.7     8
  deepseek-v4-flash             87.4     9
  deepseek-v4-pro               86.9    10
  gpt-4.5-turbo                 85.3    11
  qwen3.7-turbo                 83.1    12
  claude-haiku-5                81.8    13
  gemini-3.5-pro                80.4    14

3.2 Per-dimension score breakdown (top 5 models only):

  MODEL               Reasoning  Code   Instr  LongCtx  Throughput  TTFT   Cost
  ─────────────────────────────────────────────────────────────────────────────
  gemini-3.5-flash       97.1    93.4   96.8    95.3       88.2      94.0   97.8
  gpt-5.5                96.4    94.7   95.1    93.8       74.2      88.5   72.3
  claude-fable-5         95.8    93.2   97.4    94.1       70.1      85.2   68.9
  MiniMax-M2.7           92.3    90.8   93.5    89.4       94.6      98.4  100.0
  qwen3.7-max            94.1    91.6   92.7    91.8       52.3      71.2   78.4

3.3 Long-Context Faithfulness (needle-in-haystack, tested at 4K / 32K / 128K tokens)

  MODEL                        4K      32K     128K    512K   1M
  ──────────────────────────────────────────────────────────────
  gemini-3.5-flash             99.8    99.1     98.4   96.2   94.7
  glm-5-turbo                  99.4    98.7     97.9   95.8   93.1
  gpt-5.5                      99.9    99.4     98.8    N/A    N/A
  claude-fable-5               99.7    99.2     98.6    N/A    N/A
  kimi-k2-thinking             99.1    97.8     95.4    N/A    N/A
  qwen3.7-max                  98.9    97.3     94.1    N/A    N/A
  deepseek-v4-flash            97.2    93.4     82.1    N/A    N/A

──────────────────────────────────────────────────────────────────────────────
SECTION 4: COST ANALYSIS
──────────────────────────────────────────────────────────────────────────────

4.1 Cost per 1,000 requests (typical workload: 1,200 input + 800 output tokens)

  MODEL                        COST ($)   vs. cheapest   RANK
  ─────────────────────────────────────────────────────────
  MiniMax-M2.7                 0.0000190    1.0×           1
  deepseek-v4-flash            0.0000308    1.6×           2
  glm-5-turbo                  0.0000440    2.3×           3
  gemini-3.5-flash             0.0000440    2.3×           3
  qwen3.7-turbo                0.0000660    3.5×           5
  doubao-seed-2-0-pro-260215   0.0001100    5.8×           6
  qwen3.7-max                  0.0002160   11.4×           7
  deepseek-v4-pro              0.0002420   12.7×           8
  kimi-k2-thinking             0.0005280   27.8×           9
  gpt-4.5-turbo                0.0011000   57.9×          10
  gemini-3.5-pro               0.0019000  100.0×          11
  gpt-5.5                      0.0198000  1042.1×         12
  claude-haiku-5               0.0001760    9.3×          (uses separate pricing tier)
  claude-fable-5               0.0220000  1157.9×         13

4.2 Monthly cost projection for 10M API calls/month

  Based on 1,200 input + 800 output tokens per call:
  MiniMax-M2.7               $   190
  gemini-3.5-flash           $   440
  deepseek-v4-flash          $   308
  glm-5-turbo                $   440
  qwen3.7-max                $ 2,160
  kimi-k2-thinking           $ 5,280
  gpt-5.5                    $198,000
  claude-fable-5             $220,000

──────────────────────────────────────────────────────────────────────────────
SECTION 5: RELIABILITY AND AVAILABILITY
──────────────────────────────────────────────────────────────────────────────

5.1 Region availability (April–May 2026, excluding planned maintenance)

  REGION          AVAILABILITY  INCIDENTS  MTTR (min)
  ────────────────────────────────────────────────────
  US-EAST-1          99.98%         1          8
  US-WEST-2          99.95%         2         15
  EU-WEST-1          99.92%         3         22
  AP-SE-1            98.94%         7         48
  AP-NE-1            99.87%         2         18
  ME-SOUTH-1         99.81%         3         27
  ── OVERALL ──      99.71%        18         28

5.2 Error rates by type (% of total requests)

  Timeout errors:             0.14%
  5xx gateway errors:         0.08%
  Model capacity errors:      0.03%
  Authentication errors:      0.02%
  Total error rate:           0.27%

5.3 Notable incidents

  INC-2026-0341 (AP-SE-1, Apr 14): 73-minute partial outage due to
  upstream BGP route flap. Affected 3 of 14 models. 41,882 requests
  failed or timed out. Root cause: peering link reconfiguration by ISP
  without advance notice.

  INC-2026-0389 (EU-WEST-1, May 02): 18-minute degraded performance
  window during model weight reload for kimi-k2-thinking v2.3.1.
  Average latency increased to 8.4s TTFT during window.

──────────────────────────────────────────────────────────────────────────────
SECTION 6: SPECIAL CAPABILITIES EVALUATION
──────────────────────────────────────────────────────────────────────────────

6.1 Tool/Function Calling Success Rate

  MODEL                        SIMPLE   PARALLEL   NESTED
  ─────────────────────────────────────────────────────────
  gpt-5.5                       99.1%     97.4%     94.2%
  claude-fable-5                98.7%     96.8%     93.1%
  gemini-3.5-flash              98.3%     95.9%     91.8%
  deepseek-v4-flash             95.1%     88.4%     78.9%
  kimi-k2-thinking              97.8%     94.2%     89.7%
  MiniMax-M2.7                  94.3%     86.7%     74.1%
  qwen3.7-max                   96.4%     92.1%     86.3%
  glm-5-turbo                   93.8%     85.4%     73.2%

6.2 Structured Output (JSON mode) Compliance

  MODEL                        VALID_JSON%   SCHEMA_COMPLY%
  ──────────────────────────────────────────────────────────
  gpt-5.5                        100.0%           99.7%
  gemini-3.5-flash                99.9%           99.4%
  claude-fable-5                  99.8%           99.2%
  kimi-k2-thinking                99.3%           97.8%
  deepseek-v4-flash               98.7%           96.4%
  MiniMax-M2.7                    97.4%           94.1%
  qwen3.7-max                     98.9%           97.3%
  glm-5-turbo                     97.1%           93.8%

──────────────────────────────────────────────────────────────────────────────
SECTION 7: RECOMMENDATIONS AND CONCLUSIONS
──────────────────────────────────────────────────────────────────────────────

7.1 Model Selection Guidelines

  Use Case                    Recommended Primary      Backup
  ───────────────────────────────────────────────────────────
  High-volume, cost-sensitive  MiniMax-M2.7            gemini-3.5-flash
  Maximum quality              gemini-3.5-flash        gpt-5.5
  Long-context (>100K)         glm-5-turbo             gemini-3.5-flash
  Low-latency chatbot          MiniMax-M2.7 / deepseek deepseek-v4-flash
  Complex reasoning            kimi-k2-thinking        qwen3.7-max
  Code generation              gpt-5.5                 claude-fable-5

7.2 Infrastructure Recommendations

  1. Increase AP-SE-1 capacity by 40% and add a third upstream ISP provider.
     Estimated cost: $12,400/month additional infrastructure.

  2. Implement model health scoring with automatic routing fallback.
     This would have prevented 38% of errors in the evaluation period.

  3. Migrate kimi-k2-thinking to dedicated hardware pool to eliminate
     TTFT spikes during weight reloads (ref INC-2026-0389).

  4. Establish Redis sentinel cluster with 5 nodes for rate-limit state.
     Current 3-node setup showed split-brain risk during INC-2026-0341.

  5. Consider pre-warming gemini-3.5-flash in all 6 regions for failover.
     Current cold-start adds 1.2–2.4s TTFT penalty.

7.3 Cost Optimisation

  Switching the "high-volume, cost-sensitive" workload from deepseek-v4-flash
  to MiniMax-M2.7 would reduce monthly costs by 38.3% with only a 0.9-point
  composite accuracy reduction (87.4 → 91.7 is actually an improvement;
  cost reduction is from throughput-volume blending at 10M calls/month):
    deepseek-v4-flash: $308/month → MiniMax-M2.7: $190/month
    Net savings: $118/month at current volume.
  At projected Q3 2026 volume of 45M calls/month, savings would be $531/month.

7.4 Conclusion

  The DataEyes platform achieved an overall SLA of 99.71% during Q2 2026.
  Gemini-3.5-Flash leads the composite ranking with score 94.2, followed
  closely by GPT-5.5 at 93.8. For cost-optimised production workloads,
  MiniMax-M2.7 provides the best quality-per-dollar ratio. The AP-SE-1
  region requires immediate attention to meet the 99.9% SLA target.

  Total evaluation cost: $7,841 across 18.3 billion tokens evaluated.

══════════════════════════════════════════════════════════════════════════════
END OF REPORT
Document ID: DE-EVAL-2026-Q2-0047 | Pages: 24 | Classification: Confidential
══════════════════════════════════════════════════════════════════════════════
"""

LONG_DOC_QUESTIONS = """
Study the DataEyes AI Infrastructure Evaluation Report above carefully, then
answer ALL 12 questions. For numeric answers, use exact values from the report.
Show your step-by-step reasoning in the "reasoning" field.

Return ONLY this JSON at the very end of your response (after any thinking):

{
  "q1_overall_sla_pct": <float: overall SLA percentage across all regions>,
  "q2_cheapest_model": "<model name with lowest cost per 1K requests>",
  "q3_highest_composite_score": <float: top composite score>,
  "q4_total_evaluation_cost_usd": <integer: total cost in dollars>,
  "q5_ap_se1_incidents": <integer: number of incidents in AP-SE-1>,
  "q6_deepseek_v4_flash_avg_throughput": <integer: avg tokens/sec>,
  "q7_minimax_vs_deepseek_monthly_savings_usd": <integer: monthly savings at current volume>,
  "q8_kimi_k2_ttft_p50_ms": <integer: P50 TTFT for kimi-k2-thinking>,
  "q9_models_tested_count": <integer: number of models in evaluation>,
  "q10_glm5_context_window_tokens": <integer: context window size for glm-5-turbo>,
  "q11_top_region_peak_rps": <integer: peak RPS in highest throughput region>,
  "q12_eu_west1_mttr_min": <integer: MTTR in minutes for EU-WEST-1>,
  "reasoning": "<brief explanation of how you found each answer>"
}
"""

# Correct answers for scoring:
# q1:  99.71
# q2:  "MiniMax-M2.7"
# q3:  94.2
# q4:  7841
# q5:  7
# q6:  312
# q7:  118
# q8:  1240
# q9:  14
# q10: 1048576
# q11: 4420
# q12: 22
