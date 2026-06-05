# Local Markdown Review Workflow

Use this workflow when the user provides or names `local_framework.md`. This route is forced: do not use the ordinary `paper_type` / `section` drafting path until the local workflow has prepared evidence and citations.

## Required inputs

- `local_framework.md`: user-controlled review framework.
- A local directory containing Markdown papers.
- Optional output directory. If omitted, create a new timestamped subfolder under the paper directory.

`local_framework.md` must contain:

- `#` headings for H1 sections.
- `##` headings for H2 sections.
- One total word target in one of these forms:
  - `total_word_target: 6000`
  - `<!-- total_word_target: 6000 -->`
  - `总体字数：6000`
  - `Total word target: 6000`

Optional H2 word targets may be placed under an H2 as `<!-- word_target: 300 -->`.

## Preparation

Run `scripts/prepare_local_md_review.py` before spawning subagents:

```bash
python scripts/prepare_local_md_review.py --framework /path/to/local_framework.md --corpus /path/to/papers
```

The script writes all intermediate and final-ready artifacts to:

`<paper_dir>/nature_local_review_YYYYMMDD_HHMMSS/`

unless `--outdir` is provided. It must exclude the output directory and `local_framework.md` from recursive paper collection.

## Subagent concurrency

At most six subagents may be active at once.

- **Phase 1 — Doctor subagents**: one per paper batch, each batch has at most 20 Markdown papers.
- If more than six doctor batches exist, run them in waves. Wait for a wave to finish and close completed agents before spawning the next wave.
- **Phase 2 — Thinking/voter subagents**: exactly three, launched only after all doctor waves are complete.
- **Phase 3 — Expert merge**: one subagent, launched after voting is complete.
- **Phase 4 — Table-first synthesizers**: one per H1 section that has ≥1 H2 child with evidence. Launched after expert merge, before main writer. Subject to the same six-agent cap.
- **Phase 5 — Main writer**: one subagent, launched after all synthesizers are complete.
- The main agent does not count toward the subagent cap.

## Doctor subagent task

Each doctor subagent receives:

- The full H1/H2 framework and writing notes.
- The assigned paper paths and metadata.
- The fixed evidence schema below.

It must read the assigned Markdown papers and output only relevant or possibly relevant H2 evidence. Do not emit large empty matrices for every paper-H2 pair.

Evidence item schema:

```json
{
  "paper_id": "filename_without_ext",
  "citation_key": "author_year_keyword",
  "target_heading": "Exact H2 title",
  "support_level": "direct | partial | negative | irrelevant",
  "claim_supported": "One sentence claim supported or limited by the paper",
  "evidence_summary": "One to two sentence evidence summary",
  "source_anchor": "Markdown heading, section, paragraph, table, or page marker",
  "short_quote": "Source wording, 200 characters or fewer",
  "limitations": "Boundary or caveat",
  "tags": {
    "methodology": [],
    "topic": [],
    "evidence_strength": "strong | moderate | weak",
    "year": "Unknown",
    "venue": "Unknown",
    "has_open_data": false,
    "relevance_to_which_H2": {
      "Exact H2 title": "high | medium | low | none"
    }
  },
  "comparative_dimensions": {
    "device_type": "finger_PPG | wrist_PPG | ring_PPG | chest_ECG | dry_EEG | ...",
    "modalities": ["PPG", "ACC"],
    "sample_size": 394,
    "population": "healthy | OSA | insomnia | pediatric | elderly | mixed_clinical",
    "n_classes": 4,
    "label_standard": "AASM | R&K | other",
    "validation": "LOSO | k_fold | hold_out | external | multi_source",
    "primary_metric": {"name": "kappa", "value": 0.638},
    "model_class": "CNN | RNN | Transformer | GNN | hybrid | classical_ML",
    "parameter_count": "190K or unknown"
  }
}
```

Rules:

- `support_level` must be one of `direct`, `partial`, `negative`, or `irrelevant`.
- `relevance_to_which_H2` must use exact H2 titles as keys.
- Tags must come from the paper content. Do not invent methods, years, venues, datasets, or open-data status.
- `comparative_dimensions` is strongly recommended. Fill in every field you can extract from the paper. Use `"unknown"` for genuinely unavailable values — do not invent data. This structured field enables downstream automated comparison table generation.
- If a paper is too large to read fully, report `overflow` and explain what was read.
- The doctor subagent should save or return both JSON and Markdown summaries.

## Thinking subagent voting

Launch exactly three independent thinking subagents after all doctor outputs are collected. They read only:

- `framework.json`
- doctor output JSON/Markdown
- paper metadata

They do not read original papers. For each candidate `paper_id + H2`, vote `included` or `excluded`.

Inclusion priority:

1. `relevance_to_which_H2[H2]` is `high` or `medium`.
2. `support_level` is `direct` or `partial`.
3. Tags match the H2 writing notes.

Use two-out-of-three voting:

- At least two included votes -> include.
- At least two excluded votes -> exclude.

Write `paper_heading_assignment.csv` with:

`paper_id,heading,vote_result,vote_reason_summary`

## Expert merge

After voting, merge included evidence by H2:

- Deduplicate near-identical `claim_supported` items.
- Sort `direct` before `partial`; within each level sort `strong`, `moderate`, `weak`.
- Preserve negative or contradictory evidence in `citation_audit.md`.
- Populate `comparative_dimensions` for every evidence item. If doctor agents omitted this field, extract structured dimensions from the evidence summary prose as a fallback.
- If a H2 has fewer than two local `direct + partial` items, call `nature-citation` or `nature-academic-search` for one to three external supplements and mark them `external: true`.

Write `local_evidence_map.json`.

## Table-First Synthesis (NEW — inserted between Expert Merge and Main Writer)

This phase addresses the "paper-by-paper laundry list" problem. After the expert merge produces `local_evidence_map.json`, launch one synthesizer subagent per H1 section that has ≥1 H2 child with evidence. Subject to the six-agent concurrency cap.

Each synthesizer reads:

- `framework.json`
- `local_evidence_map.json`
- `paper_manifest.jsonl`
- `paper_heading_assignment.csv`
- All doctor outputs

Each synthesizer writes to `synthesis_grids/synthesis_{H1_id}.md` and must produce:

### Output 1: Comparison Table (mandatory)

At least one Markdown comparison table with these columns (fill "NR" for missing data — never invent):

| Study | Device | Modalities | N | Population | Classes | Label | Validation | Kappa | Acc | Model class | Notes |
|-------|--------|------------|---|------------|---------|-------|------------|-------|-----|-------------|-------|

- Span ALL papers with direct or partial evidence in this H1
- Sort by a meaningful dimension (e.g., population, then kappa descending)
- If papers split across very different tasks, create labeled sub-tables

### Output 2: Performance Range Summary (mandatory)

For each task type:
- Range: "kappa X–Y, median Z, N studies"
- Upper bound: which study, conditions
- Lower bound: which study, why low
- Main cluster: typical band
- Outliers: who falls outside and WHY

### Output 3: Incomparability Warnings (mandatory)

List paper pairs/groups whose numbers SHOULD NOT be directly compared, with reasons:
- Different label standards (AASM vs R&K)
- Different validation protocols (LOSO vs random k-fold)
- Different populations (healthy vs clinical)
- Different device types (finger-clip vs wrist PPG)
- Different class definitions (3-class vs 4-class vs 5-class)
- Small sample reliability concerns

### Output 4: Synthesis Patterns (mandatory)

3–5 cross-cutting patterns spanning ≥2 papers each:
"PATTERN: <one-sentence observation> (evidence: @paper1; @paper2; @paper3)"

These patterns are the primary input for the main writer's "SYNTHESIS FIRST" layer.

## Main drafting

Draft `literature_review.md`. The main writer prompt (generated by the prepare script) contains the complete mandatory writing order, table requirements, and forbidden patterns. Key principles:

### Writing order (mandatory, per H2)

1. **SYNTHESIS FIRST** (30-40%): Report RANGES not individual numbers. Reference synthesis grids.
2. **METHODOLOGICAL GROUPING** (40-50%): Group by shared approach. Compare/contrast within groups. Use explicit comparison language.
3. **INDIVIDUAL DEEP-DIVES** (10-20%): Only landmark papers. Justify with inline comment. Max 2 per H2.
4. **CRITICAL GAP** (10%): What dimensions are missing? Where do comparisons break?

### Table requirements (mandatory)

- Every H1 with ≥4 evidence items MUST have ≥1 Markdown comparison table
- Tables must span ≥3 papers and ≥3 comparison dimensions
- Place tables immediately after the H1 heading or at the densest H2
- Tables must use pipe syntax

### Cross-paper comparison target

- ≥0.30 cross-comparison sentences per single-paper sentence
- Cross-comparison = sentences using "while", "whereas", "in contrast", "similarly", "by comparison", "unlike"

### Forbidden patterns

- Consecutive paragraphs each starting with an author name
- Standalone "X achieved accuracy Y%" sentences without comparison
- More than two consecutive author-name-starting sentences
- Tables that only list paper titles and one metric (laundry list in table form)

### Citation format

- Use Pandoc-style citations: `[@citation_key]`
- Multi-citation for comparative claims: `[@paper_a; @paper_b]`
- Put all local and external entries in `references.bib`; external entries keep their external marker in audit artifacts.

## Validation

Run:

```bash
python scripts/validate_word_count.py --framework /path/to/local_framework.md --review /path/to/literature_review.md
python scripts/validate_citation_order.py --review /path/to/literature_review.md --bib /path/to/references.bib
```

Additional manual checks (document in `validation_report.txt`):

### Synthesis density check

Count per H2 section:
- Cross-comparison sentences (containing "while", "whereas", "in contrast", "similarly", "by comparison", "unlike")
- Single-paper sentences (author-name-first sentences reporting one finding)
- Ratio = cross_comparison / (cross_comparison + single_paper)
- Flag any H2 with ratio <0.25 for rewrite

### Table coverage check

- Count Markdown pipe tables
- Verify ≥1 table per H1 with ≥4 evidence items
- Verify each table spans ≥3 papers and ≥3 comparison dimensions
- Flag any table that is a "laundry list in table form" (only paper name + one metric)

### Incomparability check

- Verify that papers with fundamentally different label standards, validation protocols, or device types are NOT presented as directly comparable performance numbers in the prose
- Flag instances where "X achieved 90% while Y achieved 72%" appears without acknowledging the methodological difference

If validation fails, rewrite only the failing H2 sections. Limit automated rewrite loops to two passes.

## Final output files

- `literature_review.md`
- `references.bib`
- `citation_audit.md`
- `local_evidence_map.json`
- `paper_heading_assignment.csv`
- `synthesis_grids/` (one `.md` per H1 section)
- `validation_report.txt`
