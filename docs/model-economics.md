# Model economics of the Gemini review/merge pipeline

Reference data for deciding which Gemini model each pipeline slot should run on, and
what a candidate model would cost. The **ratios** here (tokens per request, output
share, split between the review and merge slots) are properties of the workflows and
should hold for any deployment; the **absolute volumes** depend on how many consumer
repositories use the workflows and how busy they are, so re-measure those before
quoting a dollar figure.

Model comparisons for this pipeline are **Gemini vs Gemini**. The jobs run inside
`google-github-actions/run-gemini-cli`, so a non-Gemini model is not a configuration
change but a new feature; leaderboard positions of other vendors' models are not an
input to these decisions.

## 1. Where the numbers come from

- **Source:** the Google AI Studio usage dashboard ("Generate content & Live API",
  input tokens / output tokens / requests per model, daily) for the API key used by
  one deployment of these workflows (five consumer repositories), 2026-07-06 → 2026-10-01. The chart was digitised from a screenshot,
  so individual days are accurate to roughly ±10 %; weekly and multi-week sums are
  better than that.
- **Data file:** [`data/gemini-usage-2026q3.csv`](data/gemini-usage-2026q3.csv) —
  one row per day and model (`date,model,input_tokens,output_tokens,requests`).
- **Slot mapping:** during this period the consumer repositories set
  `GEMINI_MODEL=gemini-flash-lite-latest` (review + security-review jobs) and
  `GEMINI_MERGE_MODEL=gemini-flash-latest` (merge job). Both aliases float: on this
  chart `gemini-flash-latest` resolved to 3.5 → 3.6 (~Jul 20) → 3.7 (~Aug 10) → 3.8 Flash
  (~Aug 31), and `gemini-flash-lite-latest` to 3.1 → 3.5 Flash-Lite (~Jul 20). So
  **every Flash row is the merge job and every Flash-Lite row is the review jobs**.
  (A steady 20–40 requests/week on Gemini 3 Flash is a small unrelated consumer of the
  same key, kept in the data for honesty; it is under 1 % of tokens.)
- Open question: whether the dashboard's output series includes thinking tokens
  (billed as output). The per-request output figures below are small enough that it
  does not change any conclusion, but treat output cost as a lower bound.

## 2. The durable ratios (per request)

Twelve full weeks, 2026-07-06 → 2026-09-27:

| | Merge job (Flash alias) | Review jobs (Flash-Lite alias) |
|---|---:|---:|
| Requests | 8,513 (22 %) | 30,047 (78 %) |
| Input tokens per request | 41.4 K | 41.1 K |
| Output tokens per request | 451 | 180 |
| Output as a share of input | 1.09 % | 0.44 % |
| Share of all input tokens | 22 % | 78 % |

What this means:

- **The pipeline is an input-token workload.** Output is about 1 % of input on the
  merge job and under 0.5 % on the reviews. A candidate model's *input* price is the
  whole cost story; its output price and verbosity barely register (see §4).
- **Requests per job are stable at ~41 K input tokens** across four Flash versions
  (3.5 → 3.8) and two Lite versions — the prompt context, not the model, sets the size.
  A model with a different thinking style changes output, not input.
- **Reviews are ~78 % of requests and ~78 % of input tokens**; the merge job is the
  remaining ~22 %. So a price change on the review alias moves the bill about 3.5×
  more than the same change on the merge alias.

## 3. Weekly volume (for scale)

| Week of | Flash input (M) | Flash output (K) | Flash requests | Lite input (M) | Lite output (K) | Lite requests |
|---|---:|---:|---:|---:|---:|---:|
| 2026-07-06 | 21.3 | 297 | 578 | 24.3 | 387 | 780 |
| 2026-07-13 | 47.8 | 544 | 1255 | 115.4 | 1454 | 3400 |
| 2026-07-20 | 17.5 | 223 | 497 | 126.1 | 899 | 3224 |
| 2026-07-27 | 23.4 | 216 | 589 | 91.7 | 265 | 2209 |
| 2026-08-03 | 89.3 | 1174 | 1755 | 46.6 | 145 | 1151 |
| 2026-08-10 | 28.3 | 312 | 815 | 109.4 | 277 | 2462 |
| 2026-08-17 | 23.6 | 183 | 574 | 85.5 | 248 | 2176 |
| 2026-08-24 | 29.6 | 151 | 624 | 131.5 | 376 | 3661 |
| 2026-08-31 | 24.5 | 258 | 657 | 166.8 | 451 | 3831 |
| 2026-09-07 | 21.6 | 219 | 524 | 84.8 | 165 | 1702 |
| 2026-09-14 | 13.2 | 111 | 345 | 108.6 | 303 | 2309 |
| 2026-09-21 | 12.2 | 152 | 300 | 144.2 | 434 | 3142 |
| **12-week total** | **352** | **3841** | **8513** | **1235** | **5406** | **30047** |

Weeks are Monday–Sunday. Week-to-week swings follow PR activity (Dependabot waves,
review rounds); the data file has the daily detail.

## 4. Cost model

Weekly cost of one slot = `input_tokens/wk × input_price + output_tokens/wk × output_price`
(prices per 1M tokens). For a candidate model, scale the output term by the ratio of
its output tokens per task to the incumbent's at the **same thinking level** (§5), and
leave the input term alone.

Worked example on the 3.8 Flash era (2026-09-02 → 09-28, 27 days): merge job
446 requests/week, 18.4 M input and 167 K output tokens per week.

| Merge-job model and price (input / output per 1M) | Input $/wk | Output $/wk | Total $/wk | ≈ $/month |
|---|---:|---:|---:|---:|
| Gemini 3.8 Flash, introductory price (to 2026-12-31) ($0.75 / $3.75) | 13.80 | 0.63 | 14.43 | 63 |
| Gemini 3.8 Flash, standard price (from 2027-01-01) ($1.5 / $7.5) | 27.61 | 1.25 | 28.86 | 125 |
| Gemini 4 Argon, introductory price (announced; output ×1.17) ($2 / $10) | 36.81 | 1.95 | 38.76 | 168 |
| Gemini 4 Argon, standard price (output ×1.17) ($4 / $20) | 73.63 | 3.90 | 77.53 | 336 |
| Gemini 4 Argon, introductory price, output ×20 (stress case) ($2 / $10) | 36.81 | 33.35 | 70.16 | 304 |

For comparison the review jobs on 3.5 Flash-Lite ($0.30 / $2.50) cost about
$40/week over the same period (130 M input, 337 K output,
2832 requests per week), so the whole key ran at roughly $54/week.

Reading the table: at the measured verbosity ratio the output column stays under
$4/week, and even the 20× stress case adds $33/week, while the input column alone moves
by the full price ratio. **The decision
for any candidate is its input price relative to the incumbent's, times that slot's
share of input tokens.** Not modelled: cached-input discounts (Gemini bills cache hits
on repeated prefixes at a large discount, and the merge prompt has a fixed prefix), so
real input cost can come in below the table.

## 5. Comparing candidates like for like (Artificial Analysis)

Artificial Analysis evaluates every Gemini Flash release at every thinking level, but
the default charts show only one level per model. Use the per-level model pages
(`/models/<model>-medium` etc.) or the comparison tool, and compare at the level the
pipeline actually runs: the Gemini CLI sends no `thinkingLevel` for the `-latest`
aliases, so the **API default applies — medium for 3.8 Flash, minimal for 3.5
Flash-Lite**. Each model page's data also carries the reasoning/answer token split per
Intelligence Index task, which is the figure to scale the output term with.

Snapshot taken 2026-10-01 (Intelligence Index v4.3.2, output tokens per index task):

| Model (thinking level) | Index | Reasoning tokens | Answer tokens | Output total | Cost per task |
|---|---:|---:|---:|---:|---:|
| Gemini 3.8 Flash (medium — what the merge job runs) | 40 | 26,956 | 25,643 | 52,599 | $0.93 |
| Gemini 3.8 Flash (high) | 41 | 42,727 | 28,275 | 71,003 | $1.24 |
| Gemini 4 Argon (high; announced 2026-09-30, not yet callable) | 53 | 35,546 | 26,011 | 61,558 | $1.99 (intro) |

So Argon at high writes **1.17× the output of 3.8 Flash at medium** (answer tokens are
the same; it thinks ~30 % more) — the ratio used in §4. Its index gain over the
incumbent is +13 points at 2.7× the input price (intro) or 5.3× (standard), and its
measured hallucination rate on AA-Omniscience is 15 %, the lowest of any model in its
score range, which is the property that matters most for a yes/no merge verdict.
Argon is not a Flash variation, so the Flash aliases will not move to it; using it
means setting `GEMINI_MERGE_MODEL` to its model name once published.

## 6. Re-measuring

1. Export or screenshot the AI Studio usage chart for the pipeline's key with the
   model filter on "All Models"; the three panels share one x-axis.
2. Attribute rows to slots by alias (Flash → merge, Flash-Lite → review) unless the
   consumer variables have changed — check `gh variable list -R <consumer>`.
3. Recompute §2 first; if the per-request figures moved materially, something in the
   prompt context changed and the cost model needs the new per-request numbers.
4. Append the new period to the CSV rather than replacing it, so the alias float
   history stays visible.
