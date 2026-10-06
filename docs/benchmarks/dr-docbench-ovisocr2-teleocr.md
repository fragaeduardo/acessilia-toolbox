# OvisOCR2 and TeleOCR evaluation on Dr.DocBench

**Date:** October 5, 2026  
**Latest update:** October 6, 2026<br>
**Sample:** 66 paired pages from the `dev` split, seed `20261003`  
**Dataset revision:** `7a2bc3882dff68e883fb55d10d4df22865ce2b07`

> Historical Acessilia pipeline result, retained for comparison. This report used
> the earlier Toolbox TeleOCR `/parse` backend and cached predictions. The current
> Toolbox adapter uses an external image-only `/predict` service with model-version
> validation; rerun this benchmark with that service before treating these scores as
> current-provider results. The separate provider evaluation is in
> [`docs/teleocr-evaluation.md`](../teleocr-evaluation.md).

## Question

Measure whether OvisOCR2 or TeleOCR improves structured extraction enough to justify integration into the Acessilia pipeline. Both models were connected to the Toolbox `document.structure.extract` provider and evaluated on the same pages and ground truth. We ran the official Dr.DocBench evaluator as well as Acessilia's internal scorer.

## Configuration

- **OvisOCR2:** `ATH-MaaS/OvisOCR2`, model revision `1fc9221b7823a371d6e97f92d527cc847e24e107`, vLLM `0.22.1`. The integration follows the inference format in the [model card](https://huggingface.co/ATH-MaaS/OvisOCR2).
- **TeleOCR:** upstream code pinned to `1e71f4fe792d12bbb86d2671c5ed6f3a1499b27d`; `StarDoc-AI/TeleOCR` weights pinned to `e92585356c0d0b7b7a65938f3da035c6593cc9a6`. The integration uses the parser from the [official TeleOCR repository](https://github.com/caipeng328/TeleOCR) behind a local API.
- **Test hardware:** NVIDIA RTX 4050 with 6 GB VRAM, local execution, one page at a time.
- **TeleOCR GPU settings:** `max_pixels=1280×1280`, `max_model_len=8192`, and `gpu_memory_utilization=0.9`. The upstream visual limit failed to initialize on this GPU, so these TeleOCR results measure a reduced-resolution configuration, not the model's ceiling on larger hardware.
- **TeleOCR run:** all 66 pages completed without extraction errors. Endpoint latency was 8.74 s mean, 6.58 s median, 17.87 s p95, and 65.24 s maximum; cumulative inference time was 9.61 min. Model initialization and compilation occurred before the batch; a separate smoke test took 92.7 s.

## Official Dr.DocBench

Lower `Edit_dist` is better; higher TEDS is better. All providers and baselines used the same set of 66 pages. One page had empty ground truth, which produced the same warning for the baselines.

| Metric | Docling | MinerU | OvisOCR2 | TeleOCR |
|---|---:|---:|---:|---:|
| Text — Edit_dist, page average | 0.2428 | 0.2621 | **0.2156** | 0.2189 |
| Formulas — Edit_dist, page average | 0.9685 | 1.0000 | **0.8546** | 0.8546 |
| Tables — TEDS | no samples | no samples | 0.5986 | **0.6112** |
| Tables — Edit_dist, page average | no samples | no samples | 0.4744 | **0.4082** |
| Reading order — Edit_dist, page average | **0.4386** | 0.4484 | **0.3886** | 0.4644 |

TEDS was calculated over 13 tables with ground truth. Docling and MinerU have no table result because those baselines produced no corresponding samples in this evaluation.

## Applied fusion and combination matrix

Dr.DocBench reports edit distance, where lower is better. For an easier comparison, this table converts each edit distance to `100 × (1 − Edit_dist)`, so all displayed scores increase with quality. TEDS is shown as a percentage. Deltas in parentheses are percentage points versus the current Docling+MinerU fusion. Dr.DocBench returned no table samples for that baseline: its final Markdown contains no HTML `<table>` structures recognized by the evaluator. **“No result” means unscored, not zero.**

### Test protocol

- Ran the official `DrDocBench/tools/multipage_pdf_validation.py` entrypoint with the benchmark's `multipage_md2md_dataset` configuration, `quick_match`, and the official `dev` ground truth.
- Every row uses the same 66 manifest IDs: one randomly selected page per document, seed `20261003`, dataset revision `7a2bc3882dff68e883fb55d10d4df22865ce2b07`. The four configured official metrics ran for each row: text, display formula, table, and reading order. The common empty-ground-truth-page warning was present across runs.
- On October 6, the official evaluator also ran two TeleOCR ablations—formulas only and tables only—on those same 66 pages. Both reused cached TeleOCR predictions; no new model inference was run.
- This is the complete official scoring pipeline on the 66-page paired sample, **not a run over all 986 `dev` documents**. The official report does not provide a single composite score here, so I keep the task metrics separate.

### Scores

| Scenario | Text (Δ) | Formulas (Δ) | Table TEDS | Table Edit score | Reading order (Δ) | TEDS records |
|---|---:|---:|---:|---:|---:|---:|
| Docling | 75.72 (-6.27) | 3.15 (+0.00) | — | — | 56.14 (-22.21) | 0 |
| MinerU | 73.79 (-8.19) | 0.00 (-3.15) | — | — | 55.16 (-23.19) | 0 |
| OvisOCR2 | 78.44 (-3.55) | 14.54 (+11.40) | 59.86 | 52.56 | 61.14 (-17.22) | 12 |
| TeleOCR | 78.11 (-3.87) | 14.54 (+11.40) | 61.12 | 59.18 | 53.56 (-24.80) | 13 |
| Docling + MinerU (production baseline) | 81.98 (+0.00) | 3.15 (+0.00) | — | — | 78.36 (+0.00) | 0 |
| Docling + OvisOCR2 (Ovis supplies order skeleton) | 75.76 (-6.23) | 17.29 (+14.14) | 59.86 | 52.56 | 73.12 (-5.24) | 12 |
| OvisOCR2 + MinerU (MinerU supplies order skeleton) | 80.49 (-1.49) | 16.26 (+13.11) | 59.86 | 52.56 | 67.11 (-11.24) | 12 |
| Docling + TeleOCR (Tele supplies order skeleton) | 77.23 (-4.75) | 13.43 (+10.28) | 61.12 | 59.18 | 71.78 (-6.57) | 13 |
| TeleOCR + MinerU (MinerU supplies order skeleton) | 81.21 (-0.78) | 12.72 (+9.58) | 61.12 | 59.18 | 54.99 (-23.36) | 13 |
| OvisOCR2 + TeleOCR (Tele supplies order skeleton) | 78.68 (-3.30) | 16.40 (+13.25) | 61.67 | 55.17 | 68.43 (-9.93) | 13 |
| TeleOCR + OvisOCR2 (Ovis supplies order skeleton) | 78.54 (-3.45) | 16.45 (+13.30) | 61.12 | 59.18 | 69.20 (-9.15) | 13 |
| MinerU + Docling (Docling supplies order skeleton) | 80.69 (-1.30) | 3.15 (+0.00) | — | — | 76.01 (-2.35) | 0 |
| OvisOCR2 + Docling (Docling supplies order skeleton) | 73.74 (-8.24) | 17.15 (+14.00) | 59.86 | 52.56 | 67.61 (-10.75) | 12 |
| TeleOCR + Docling (Docling supplies order skeleton) | 74.38 (-7.60) | 13.43 (+10.28) | 61.12 | 59.18 | 68.19 (-10.17) | 13 |
| MinerU + OvisOCR2 (Ovis supplies order skeleton) | 81.27 (-0.72) | 16.26 (+13.11) | 59.86 | 52.56 | 68.34 (-10.01) | 12 |
| MinerU + TeleOCR (Tele supplies order skeleton) | 82.37 (+0.38) | 12.72 (+9.58) | 61.12 | 59.18 | 54.24 (-24.11) | 13 |
| Docling + MinerU + OvisOCR2 (current pair, then Ovis) | 69.83 (-12.15) | 14.58 (+11.43) | 59.86 | 52.56 | 70.99 (-7.37) | 12 |
| Docling + MinerU + TeleOCR (current pair, then Tele) | 73.40 (-8.59) | 13.06 (+9.91) | 61.12 | 59.18 | 72.47 (-5.88) | 13 |
| Docling + OvisOCR2 + TeleOCR (D+O pair, then Tele) | 66.43 (-15.55) | 17.29 (+14.15) | 61.12 | 59.18 | 62.38 (-15.97) | 13 |
| MinerU + OvisOCR2 + TeleOCR (O+M pair, then Tele) | 70.49 (-11.50) | 16.57 (+13.43) | 61.12 | 59.18 | 62.87 (-15.48) | 13 |
| Docling + MinerU + OvisOCR2 + TeleOCR (Ovis then Tele) | 68.65 (-13.34) | 17.07 (+13.93) | 61.12 | 59.18 | 65.74 (-12.61) | 13 |
| Docling + MinerU + TeleOCR + OvisOCR2 (Tele then Ovis) | 66.41 (-15.58) | 14.70 (+11.55) | 61.67 | 55.17 | 67.97 (-10.39) | 13 |
| Current fusion + Ovis tables/formulas | 77.52 (-4.46) | 12.82 (+9.67) | 59.86 | 52.56 | 76.25 (-2.11) | 12 |
| Current fusion + Tele tables/formulas | 77.53 (-4.46) | 12.97 (+9.82) | 61.12 | 59.18 | 76.26 (-2.10) | 13 |
| Current fusion + both models’ tables/formulas | 77.53 (-4.45) | 12.97 (+9.82) | 61.12 | 59.18 | 76.24 (-2.11) | 13 |
| Current fusion + Ovis tables/formulas | 81.98 (+0.00) | 13.22 (+10.07) | 59.86 | 52.56 | 78.36 (+0.00) | 12 |
| Current fusion + Tele tables/formulas | 81.98 (+0.00) | 13.34 (+10.19) | 61.12 | 59.18 | 78.36 (+0.00) | 13 |
| Current fusion + Tele formulas only (ablation) | 81.98 (+0.00) | 13.34 (+10.19) | — | — | 78.36 (+0.00) | 0 |
| Current fusion + Tele tables only (ablation) | 81.98 (+0.00) | 3.15 (+0.00) | 61.12 | 59.18 | 78.36 (+0.00) | 13 |
| Current fusion + Ovis formulas, Tele tables | 81.98 (+0.00) | 13.22 (+10.07) | 61.12 | 59.18 | 78.36 (+0.00) | 13 |
| Current fusion + Ovis tables, Tele tables/formulas | 81.98 (+0.00) | 13.34 (+10.19) | 61.54 | 59.21 | 78.36 (+0.00) | 13 |
| Current fusion + both models’ tables/formulas | 81.98 (+0.00) | 12.98 (+9.83) | 61.54 | 59.21 | 78.36 (+0.00) | 13 |

`TEDS records` counts table instances that the evaluator scored; the number of pages is 66 for every row. A dash means the metric had no scored samples.

### How to read the multi-provider rows

Pairwise rows use the existing binary `docstruct` v12 fusion directly; the second provider supplies the reading-order skeleton. Both input orders are included for every provider pair. `Docling + MinerU` is the current production output; the reverse order is a v12 experimental fusion.

The current fusion interface accepts two providers and returns Markdown, not the geometry-bearing block set needed for a native 3- or 4-provider merge. The triple and quartet rows are therefore **sequential experimental proxies**: start from the indicated pair output, parse it back into blocks, then add the next provider; synthetic vertical positions are used only to place unmatched blocks, and matching uses text. Their numbers are official scores for those generated files, but the substantial text/order losses show that this is not a production-quality n-way fusion. They do not prove that a properly designed n-way fusion must lose that much.

The “Structure-only v12 re-pass” rows are another diagnostic: they re-run v12 using only new table/formula blocks against the current Markdown. Because the serialized baseline lacks its original block metadata, these runs alter text/order and should not be treated as the recommended route.

The additive structure rows keep the current Docling+MinerU Markdown exactly as the base and append non-duplicate table/formula blocks from the requested model source(s). The TeleOCR-only route is now implemented as an opt-in side channel in Acessilia and preserves baseline text and reading-order scores on this sample. TeleOCR does not provide geometry in the current response, so blocks are appended in page order; geometric placement remains future work before broad product use.

## Acessilia internal scorer

These are standalone-model scores from Acessilia's internal evaluator, separate from the official Dr.DocBench matrix above.

| Metric | Docling | MinerU | OvisOCR2 | TeleOCR |
|---|---:|---:|---:|---:|
| Text | 66.33 | 67.73 | **72.79** | 71.48 |
| Reading order | 66.92 | 68.47 | **74.37** | 72.34 |
| TEDS | — | — | 28.46 | **39.74** |
| CDM | 71.81 | — | 56.28 | 56.63 |
| Overall | 67.37 | 68.34 | **73.51** | 72.05 |

## Findings

- Do not replace the current Docling+MinerU fusion wholesale with any tested pair: every direct replacement loses text and/or reading-order score.
- The best measured additive combination is **current fusion + OvisOCR2 tables + TeleOCR tables/formulas**: text **81.985** and reading order **78.355** stay unchanged; formula score is **13.341** (**+10.192 pp**); table TEDS is **61.543** and table edit score **59.212**. Relative to using TeleOCR structures alone, adding OvisOCR2 tables raises TEDS by **0.422 pp** and table edit by **0.034 pp** on this small sample.
- The simpler **current fusion + TeleOCR tables/formulas** route also preserves text/order and scores **13.341** on formulas, **61.121 TEDS**, and **59.178 table-edit points**. This is the cleanest first integration candidate. The extra OvisOCR2 tables produce only a small table gain here; adding both models’ formulas introduces conflicts and lowers formula score to **12.978**.
- The implemented TeleOCR route was re-scored with the official evaluator after integrating it into the current fusion path. Its displayed metrics match the additive TeleOCR row above; the report and score files are listed under reproducibility artifacts. The predictions reused cached TeleOCR responses, so this verifies current routing and official scoring, not a fresh model-inference run.
- The October 6 ablation confirms the formula gain comes from TeleOCR formulas: the formulas-only row matches the combined route at **13.341**, while tables-only leaves formulas at the **3.148** baseline. Tables-only scores **61.121 TEDS** and **59.178 table-edit points** over 13 tables. Both ablations leave text and reading order unchanged. The baseline has no scored table samples, so the table row measures added coverage and quality, not a delta against an existing table score.
- Treat the multi-pass triple/quartet losses as a warning about the current binary API and missing intermediate geometry. A proper implementation should preserve the existing text/order blocks and their boxes, then align new formula/table blocks against those blocks instead of re-parsing a flattened Markdown string.
- Before broad adoption, validate on the complete `dev` split or a larger paired sample and place the new table/formula blocks using page geometry. TeleOCR was run with a reduced `1280×1280` image limit on 6 GB VRAM, so a larger-GPU rerun remains useful for measuring its ceiling.

## Implementation decision

Keep Docling+MinerU as the text and reading-order path, and keep TeleOCR as the only new structure provider. It is opt-in with `FUSION_STRUCTURE_PROVIDER=teleocr`; the DrDocBench runner exposes the same route with `--current-fusion --supplement-provider teleocr`. The implementation adds TeleOCR formula/table candidates while preserving the current fusion's text and reading order.

On 66 paired pages, official scoring gives text **81.985/100** and reading order **78.355/100**, unchanged from baseline; formulas **13.341/100** (**+10.192 pp**); table TEDS **61.121** and table edit **59.178/100**. OvisOCR2 adds only **0.422 pp** TEDS and **0.034 pp** table-edit over TeleOCR alone in the strongest historical combination, which does not justify keeping a second GPU service. Its historical measurements remain in the comparison matrix, but its integration was removed.

This implementation currently appends typed structure blocks in page order because TeleOCR does not return geometry. Use it to measure the structure-score lift; add geometric placement/alignment and rerun on a larger sample before relying on these blocks as positioned content in the general product pipeline.


## Reproducibility artifacts

Inputs, predictions, logs, and per-scenario official evaluator output are under the ignored `var/drbench/experiments/ovisocr2-dev66/` directory in the Acessilia repository. The implemented-route prediction set is `var/drbench/experiments/ovisocr2-dev66/official-predictions/implementation-current-plus-teleocr/`; its official evaluator output is `var/drbench/experiments/ovisocr2-dev66/scoring/tele-sidecar-replay/result/implementation-current-plus-teleocr_metric_result.json` (with per-task JSON files alongside it). Ablation predictions are in `official-predictions/ablation-tele-formulas-only/` and `official-predictions/ablation-tele-tables-only/`; their metric JSON files are in `scoring/tele-ablation/result/`. The complete scorecard is also available as [dr-docbench-fusion-matrix.csv](dr-docbench-fusion-matrix.csv). Internal standalone reports are `local-ovisocr2.json` and `local-teleocr.json`; standalone official summaries are `result/ovisocr2-dev66_metric_result.json` and `result/teleocr-dev66_metric_result.json`.
