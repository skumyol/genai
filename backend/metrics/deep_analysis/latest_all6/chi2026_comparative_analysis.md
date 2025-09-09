# Comparative Analysis of Six Multi‑Agent LLM Experiments (CHI 2026 Submission Draft)

## Abstract
We present a comparative evaluation of six experimental configurations of a multi‑agent conversational RPG system. Our primary contributions are (1) a retry‑isolated efficiency methodology that separates native LLM service latency from network‑level artifacts (rate limits, timeouts, fallbacks), and (2) a cross‑condition comparison of linguistic and semantic diversity. We find consistent efficiency benefits for Reputation‑ON variants across model families and markedly higher linguistic diversity for the Mixed configuration with Reputation ON. We discuss implications for interaction quality, system design, and reproducible reporting.

## Methodology
- Data sources: SQLite session database (`sessions`, `dialogues`, `messages`) and per‑session metrics JSON/CSV (`*_metrics.json/.csv`) emitted by the runtime `MetricsCollector`.
- Retry‑isolated efficiency (per session):
  - Pure calls: entries with context `attempt=1` and `retry=1` (no prior failures, no fallbacks).
  - Metrics: `avg_latency_pure` (s), `tokens_per_sec_pure`, and `overhead_latency_delta` (s), defined as the mean latency of affected calls (retried or fallback) minus `avg_latency_pure`.
  - We also report counts for `pure_calls`, `retried_calls`, and `fallback_calls`.
- Linguistic and semantic diversity (from DB):
  - Type‑Token Ratio (TTR), Distinct‑1/Distinct‑2, MTLD (approx.), vocabulary richness (Herdan’s C), average message length (chars), unique‑message ratio, unique speakers, and messages/dialogue.
- Conditions (N=6; one complete session per condition):
  - Mixed (local small social + remote 8B game): Reputation ON, Reputation OFF
  - GPT‑5 (OpenRouter): Reputation ON, Reputation OFF
  - Qwen3‑8B (OpenRouter): Reputation ON, Reputation OFF

All metrics were produced by `backend/tools/deep_experiment_analysis.py` and written to `backend/metrics/deep_analysis/latest_all6/`.

## Results
### Efficiency (Retry‑Isolated)
- Mixed
  - Rep ON: `avg_latency_pure` = 3.52 s; `tokens_per_sec_pure` = 2206; `overhead_latency_delta` = 24.71 s; total/pure/affected = 2673 / 1866 / (443 retried, 663 fallback)
  - Rep OFF: `avg_latency_pure` = 22.21 s; `tokens_per_sec_pure` = 386; `overhead_latency_delta` = 558.78 s; total/pure/affected = 5236 / 5042 / (148 retried, 51 fallback)
- GPT‑5
  - Rep ON: `avg_latency_pure` = 3.40 s; `tokens_per_sec_pure` = 3976; `overhead_latency_delta` = 11.43 s; total/pure/affected = 2530 / 2433 / (12 retried, 86 fallback)
  - Rep OFF: `avg_latency_pure` = 4.20 s; `tokens_per_sec_pure` = 4657; `overhead_latency_delta` = 274.30 s; total/pure/affected = 3986 / 3954 / (31 retried, 2 fallback)
- Qwen3‑8B
  - Rep ON: `avg_latency_pure` = 5.52 s; `tokens_per_sec_pure` = 4041; `overhead_latency_delta` = 25.79 s; total/pure/affected = 2300 / 2241 / (17 retried, 42 fallback)
  - Rep OFF: `avg_latency_pure` = 5.84 s; `tokens_per_sec_pure` = 4458; `overhead_latency_delta` = 164.03 s; total/pure/affected = 2339 / 2288 / (21 retried, 30 fallback)

Interpretation:
- Across all three families, Reputation ON reduces clean service latency relative to OFF (Mixed: 3.52 vs 22.21 s; GPT‑5: 3.40 vs 4.20 s; Qwen: 5.52 vs 5.84 s).
- Overhead penalties on affected calls are consistently higher in Reputation OFF (Mixed: +558.8 s; GPT‑5: +274.3 s; Qwen: +164.0 s), suggesting slower fallbacks or longer backoff in OFF conditions.
- Pure token throughput is highest for GPT‑5 and Qwen families (≈4k–4.7k tokens/s) and markedly lower for Mixed‑ON (≈2.2k) and especially Mixed‑OFF (≈0.39k), reflecting different prompt sizes/models and degraded performance in Mixed‑OFF.

### Linguistic/Semantic Diversity
- Distinct‑2 (higher is better semantic/structural diversity):
  - Mixed‑ON: 0.2310 (highest)
  - Qwen‑OFF: 0.0949; Qwen‑ON: 0.0900
  - Mixed‑OFF: 0.0775
  - GPT‑5‑ON: 0.0054; GPT‑5‑OFF: 0.0012 (lowest)
- TTR (token level variety):
  - Mixed‑ON: 0.0548 (highest); Mixed‑OFF: 0.0157; Qwen‑ON: 0.0214; Qwen‑OFF: 0.0227; GPT‑5‑ON: 0.0033; GPT‑5‑OFF: 0.0008
- Average message length (chars):
  - Mixed‑OFF: 402.0 (longest); Mixed‑ON: 216.9; Qwen‑ON: 72.8; Qwen‑OFF: 64.1; GPT‑5‑ON: 83.2; GPT‑5‑OFF: 54.0

Interpretation:
- Mixed‑ON exhibits substantially greater bigram diversity and TTR at shorter message lengths than Mixed‑OFF, indicating better semantic economy (more novelty per character).
- Qwen shows moderate diversity, with OFF slightly higher Distinct‑2 than ON, but both well below Mixed‑ON.
- GPT‑5 sessions exhibit very low Distinct‑n and TTR despite short messages and high message counts, suggesting repetitive or templated outputs in those runs (see Threats to Validity).

## Cross‑Condition Synthesis
- Efficiency: Reputation ON consistently improves clean latency and reduces the severity of overheads for affected calls across model families. Mixed‑OFF is particularly inefficient.
- Diversity: Mixed‑ON dominates semantic diversity (Distinct‑2, TTR) while keeping message length moderate. In contrast, Mixed‑OFF produces long messages with lower diversity, implying verbosity rather than expressive variety. Qwen is mid‑tier; GPT‑5 shows repetitive behavior in this corpus.
- Reliability profile: OFF variants incur larger overhead deltas even when the fraction of affected calls is small (e.g., GPT‑5‑OFF), implying that rare failures become disproportionately expensive in OFF configurations. ON variants appear to handle backoff/fallbacks with less degradation.

## Design Implications for CHI
- Reputation mechanisms may improve not only social coherence but also runtime behavior by modulating prompt structure, leading to shorter, more focused messages and better clean latency.
- For multi‑agent systems, reporting efficiency without retry isolation can be misleading; we recommend including `avg_latency_pure`, `tokens_per_sec_pure`, and `overhead_latency_delta` in all model comparisons.
- Mixed configurations benefit from Reputation ON in both human‑perceivable qualities (diversity, brevity) and underlying system performance; they are promising for scalable, multi‑party interactions.

## Threats to Validity
- GPT‑5/Qwen sessions likely differ in scenario composition and dialogue segmentation (e.g., GPT‑5 average messages/dialogue ≈180), which can depress Distinct‑n and TTR despite high throughput.
- MTLD is an approximation sensitive to corpus size; we triangulate with Distinct‑n and TTR to mitigate single‑metric artifacts.
- Token throughput reflects both model speed and prompt/response tokenization; cross‑model absolute values should be interpreted cautiously.

## Recommendations
1. Favor Reputation‑ON across families for both efficiency and interaction quality; for Mixed configurations, ON is decisively superior.
2. Diagnose OFF variants with large `overhead_latency_delta` by inspecting rate‑limit/timeouts and fallback endpoints; prefer quicker local fallbacks for agents with recurrent issues.
3. Adopt retry‑isolated metrics as primary efficiency reporting in publications; treat end‑to‑end averages as secondary context.
4. Align task/dialogue segmentation across conditions to improve comparability of linguistic metrics in future studies.

## Artifacts and Reproducibility
- Analysis: `backend/tools/deep_experiment_analysis.py`
- Outputs: `backend/metrics/deep_analysis/latest_all6/{deep_analysis.json, groups.csv, sessions.csv}`
- Plots: `backend/metrics/deep_analysis/latest_all6/plots/`
- Data: `backend/databases/checkpoints.db` and per‑session `backend/metrics/*_metrics.json`

*Generated: 2025‑09‑09*
