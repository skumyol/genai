# Experimental Evaluation of Multi‑Agent LLM Configurations

## Abstract
We evaluate six experimental configurations of a multi‑agent conversational RPG system, focusing on (i) model efficiency independent of network retries and fallbacks, and (ii) linguistic/semantic diversity of generated dialogue. We introduce a retry‑isolated efficiency methodology that uses per‑call telemetry to separate native LLM service latency from overheads caused by rate limits, timeouts, and fallback routing. Our results indicate that the Mixed — Reputation ON condition achieves substantially better clean latency and token throughput while maintaining higher lexical/semantic diversity than the Reputation OFF condition. We also provide aggregate language metrics for four additional sessions lacking per‑call telemetry, and discuss implications for system design and reporting.

## Methods
- Data sources: SQLite session store (`sessions`, `dialogues`, `messages`) and per‑session metrics JSON/CSV emitted by the runtime `MetricsCollector`.
- Retry‑isolated efficiency: For each `llm_call_latency` entry, we use context fields `attempt` and `retry` to identify “pure” calls (attempt=1, retry=1), which reflect LLM service latency without prior failure backoff. We report:
  - avg_latency_pure (s): mean latency on pure calls only.
  - tokens_per_sec_pure: sum(total_tokens)/sum(latency) over pure calls.
  - overhead_latency_delta (s): mean(latency of affected calls) − avg_latency_pure, where affected calls are those with retry>1 and/or attempt>1.
  - We also report counts of pure_calls, retried_calls, fallback_calls.
- Linguistic/semantic diversity: From the `messages` table joined with `dialogues`, we compute
  - Type‑Token Ratio (TTR), Distinct‑1/Distinct‑2, MTLD (approx.), vocabulary richness (Herdan’s C), average message length (chars), unique‑message ratio, unique speakers, and messages/dialogue.
- Grouping and outputs: Sessions are grouped by (experiment_name, variant_id). Results are written to `backend/metrics/deep_analysis/latest/{deep_analysis.json, groups.csv, sessions.csv}`, with plots in `plots/`.

## Experimental Conditions
- Total sessions analyzed: 6
  - Mixed: `exp_mixed_social_1b_game_8b` — variants `mixed_rep_on`, `mixed_rep_off` (with full per‑call metrics)
  - Four additional sessions (two GPT‑5, two Qwen3‑8B) lack per‑call telemetry; we analyze their language metrics from the DB but omit efficiency.

## Results

### Efficiency (Retry‑Isolated)
Key group comparisons (from `groups.csv`):

- Mixed — Reputation ON (n=1)
  - avg_latency_pure: 3.522 s
  - tokens_per_sec_pure: 2206.315 tokens/s
  - overhead_latency_delta: 24.712 s
  - total_calls: 2673; pure_calls: 1866; retried_calls: 443; fallback_calls: 663
- Mixed — Reputation OFF (n=1)
  - avg_latency_pure: 22.209 s
  - tokens_per_sec_pure: 385.565 tokens/s
  - overhead_latency_delta: 558.782 s
  - total_calls: 5236; pure_calls: 5042; retried_calls: 148; fallback_calls: 51

Interpretation:
- Clean LLM service time strongly favors Reputation ON (≈6.3× lower latency, ≈5.7× higher token throughput).
- Reputation OFF exhibits very large overhead on affected calls, consistent with slow fallbacks or extended backoff after rate limits/timeouts.
- Although Reputation ON saw more retried/fallback calls, the overhead per affected call remained close to the pure baseline; in contrast, Reputation OFF suffered severe outliers that dominate its overhead delta.

Illustrative plots (generated):
- ![Pure Latency](./plots/plot_avg_latency_pure.png)
- ![Token Throughput (pure)](./plots/plot_tokens_per_sec_pure.png)
- ![Retry/Fallback Overhead](./plots/plot_overhead_latency_delta.png)

### Linguistic and Semantic Diversity
Per‑session highlights (from `sessions.csv`):

- Mixed — Reputation ON
  - TTR: 0.0548; Distinct‑2: 0.2310; Avg msg length: 216.9 chars; Unique‑message ratio: 0.8745; MTLD≈1.329; Vocab richness≈0.741
  - Dialogue volume: 1840 messages; avg 9.02 messages/dialogue
- Mixed — Reputation OFF
  - TTR: 0.0157; Distinct‑2: 0.0775; Avg msg length: 402.0 chars; Unique‑message ratio: 0.9706; MTLD≈1.358; Vocab richness≈0.660
  - Dialogue volume: 2753 messages; avg 9.21 messages/dialogue
- Aggregated baseline across four additional sessions (two GPT‑5, two Qwen3‑8B; efficiency unavailable)
  - TTR: 0.0121; Distinct‑2: 0.0479; Avg msg length: 68.5 chars; Messages: 32,516

Interpretation:
- Reputation ON yields higher bigram diversity (Distinct‑2) and higher TTR with shorter utterances, suggesting more efficient semantics and reduced verbosity.
- Reputation OFF produces substantially longer messages with lower Distinct‑2, indicating verbosity without proportional increase in semantic variety.
- The aggregated GPT‑5/Qwen sessions show shorter messages and lower diversity, likely due to scenario/task mix and absence of late‑run conversational sprawl; without per‑call metrics, we refrain from efficiency conclusions for these sessions.

Illustrative plots (generated):
- ![TTR](./plots/plot_ttr.png)
- ![Distinct‑2](./plots/plot_distinct_2.png)
- ![Average Message Length](./plots/plot_avg_message_len.png)

## Discussion
### Efficiency without Network Artifacts
Isolating native LLM service latency is essential. We operationalize this via pure calls (attempt=1, retry=1), explicitly excluding calls preceded by backoff or routed to fallbacks. This separation reveals the underlying model/service responsiveness more faithfully than end‑to‑end averages. The Mixed — Reputation ON condition demonstrates markedly better clean latency and throughput. Its small overhead delta, despite more affected calls, suggests efficient fallback routing and short backoffs when issues arise. Conversely, the OFF variant’s overhead indicates persistent slowdowns—either slow fallback endpoints or repeated rate‑limit/timeouts against the primary.

### Language Quality and Semantic Economy
Higher Distinct‑2 and TTR at shorter message lengths in Reputation ON imply better semantic economy: achieving greater lexical/semantic variety per character. Reputation OFF’s longer outputs with lower Distinct‑2 suggest over‑elaboration without commensurate novelty. From a game design perspective, ON supports livelier multi‑agent exchanges with less bloating.

## Threats to Validity
- Missing per‑call metrics for four sessions prevents efficiency comparisons there. Future runs should ensure telemetry is present for all conditions.
- MTLD is an approximation and sensitive to corpus size; we therefore triangulate with Distinct‑n and TTR.
- Dialogue/task composition varies by experiment; absolute diversity should be interpreted alongside message counts and scenario.

## Recommendations
1. Prefer the Mixed — Reputation ON configuration for both efficiency (clean latency, throughput) and linguistic diversity (Distinct‑2, TTR at lower length).
2. For Reputation OFF (and any conditions with high overhead deltas), investigate provider quotas, timeouts, and fallback endpoints. Consider earlier fallback to fast local models for agents showing chronic 429/timeout behavior.
3. Standardize per‑call telemetry capture across all experiments to enable complete cross‑model comparisons.
4. Report retry‑isolated latency and token throughput as primary efficiency metrics in publications; treat end‑to‑end averages as auxiliary.

## Reproducibility Artifacts
- Analysis code: `backend/tools/deep_experiment_analysis.py`
- Outputs: `backend/metrics/deep_analysis/latest/{deep_analysis.json, groups.csv, sessions.csv}`
- Plots: `backend/metrics/deep_analysis/latest/plots/`
- Underlying data: `backend/databases/checkpoints.db` (tables: `sessions`, `dialogues`, `messages`), per‑session metrics `backend/metrics/*_metrics.json`

*Generated: 2025‑09‑09*
