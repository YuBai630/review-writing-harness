[![中文](https://img.shields.io/badge/语言-中文-red)](README.md) [![English](https://img.shields.io/badge/Language-English-blue)](README_EN.md)

# Review Writing Harness

A synthesis-first multi-agent workflow for writing literature reviews from local Markdown paper corpora.

This project is a deep enhancement of the [`nature-writing`](https://github.com/Yuan1z0825/nature-skills) skill from [nature-skills](https://github.com/Yuan1z0825/nature-skills). It adds a Table-First synthesis stage, 12-dimension structured comparative dimensions, a synthesis-first writing protocol, cross-platform portable paths, and other key improvements on top of the original design.

## The Problem

Traditional literature review workflows produce **paper-by-paper laundry lists**: "Smith et al. proposed X and achieved 92%. Jones et al. proposed Y and achieved 88%. Lee et al. proposed Z..." — each paragraph is a single-paper summary, with no cross-paper comparison, no performance range synthesis, no incomparability warnings, and no structured comparison tables.

More critically, asking a large language model (LLM) to "write a literature review" produces severe **hallucination problems**: the model invents non-existent paper titles, fabricates author names, and conjures up experimental data and performance metrics — these fabricated elements, once mixed into academic writing, are extremely difficult to detect and can lead to serious academic misconduct. `review-writing-harness` eliminates hallucinations at the source through two hard constraints: **(1) Framework constraint** — all claims must strictly correspond to the predefined H1/H2 heading structure in `local_framework.md`; the model cannot expand or deviate on its own. **(2) Local paper reading** — all cited evidence must come from the user-provided local Markdown paper corpus; doctor subagents read each paper and extract structured evidence with precise page/paragraph anchors, and are forbidden from citing any "memorized knowledge" from training data. The framework is the skeleton, the local papers are the flesh — together they form a closed evidence system that blocks hallucinations at the source.

```
                          ┌──────────────────────────┐
                          │   local_framework.md     │
                          │  (user-defined H1/H2)    │
                          └────────────┬─────────────┘
                                       │ hard constraint: all claims must fit
                                       ▼
┌─────────────────────────────────────────────────────────────┐
│                  review-writing-harness                      │
│                                                             │
│  Prepare ──▶ Doctors ──▶ Voters ──▶ Expert ──▶ Synthesizers│
│     │            │           │          │            │       │
│     │       read each    2-of-3    dedup+sort  per-H1 table │
│     │       paper+extract majority  +map       +range+      │
│     │       evidence                                   │    │
│     ▼            ▼           ▼          ▼       patterns▼    │
│  ┌──────────────────────────────────────────────────────┐    │
│  │            Closed Evidence System (zero hallucination)│    │
│  │  • All citations from local MD papers + exact anchors │    │
│  │  • "Memorized knowledge" from training data forbidden │    │
│  │  • Each evidence item has 12-dim comparative_dimensions│   │
│  └──────────────────────────────────────────────────────┘    │
│                                                             │
│  Main Writer ──▶ Validate                                   │
│       │               │                                     │
│   synthesis-first  word count/table coverage/                │
│   4-layer protocol  synthesis density/incomparability        │
└─────────────────────────────────────────────────────────────┘
                                       │
                                       ▼
                          ┌──────────────────────────┐
                          │   literature_review.md   │
                          │  (tables + perf ranges   │
                          │   + incomparability      │
                          │   warnings + references) │
                          └──────────────────────────┘
```

## Our Solution

`review-writing-harness` adds three key innovations to the local-MD review pipeline:

### 1. Synthesis-First Writing Protocol

Every H2 section is written in a mandatory 4-layer order:
- **Layer 1 (30-40%)**: Synthesis first — open with the *range* of observed results, not individual numbers
- **Layer 2 (40-50%)**: Methodological grouping — cluster papers by shared approach and compare/contrast *within* each group
- **Layer 3 (10-20%)**: Individual deep-dives — only for ≤2 landmark papers per section, with explicit justification
- **Layer 4 (10%)**: Critical gap / incomparability analysis — what dimensions are missing? Where do comparisons break?

### 2. Table-First Synthesis Phase

A new synthesizer subagent stage inserted between evidence collection and drafting. Every H1 section gets a dedicated synthesizer that produces:
- **Comparison table** spanning all papers with 12 structured dimensions (device type, modalities, sample size, population, n_classes, label standard, validation protocol, kappa, accuracy, model class, parameter count)
- **Performance range summary** (upper bound, lower bound, main cluster, outliers with causal explanation)
- **Incomparability warnings** (paper pairs whose numbers should NOT be compared, with reasons)
- **Cross-paper synthesis patterns** (3-5 patterns spanning ≥2 papers each)

### 3. Structured Comparative Dimensions

The evidence schema is extended with a `comparative_dimensions` field that doctors must populate: `device_type`, `modalities`, `sample_size`, `population`, `n_classes`, `label_standard`, `validation`, `primary_metric`, `model_class`, `parameter_count`. This enables automated comparison table generation and systematic cross-study analysis.

## Workflow Architecture

```
Prepare → Doctors(×N) → Voters(×3) → Expert Merge → Synthesizers(×M) → Main Writer → Validate
```

| Phase | Agents | Function |
|-------|--------|----------|
| Prepare | 1 script | Parse framework, batch papers, generate all prompts |
| Doctors | ≤6 concurrent | Read papers, extract evidence with comparative_dimensions |
| Voters | 3 (2-of-3 majority) | Vote on paper-H2 inclusion |
| Expert Merge | 1 | Deduplicate, sort, build evidence map |
| **Synthesizers** | **Per H1 section** | **Generate comparison tables, ranges, patterns, warnings** |
| Main Writer | 1 | Draft review following synthesis-first protocol |
| Validate | 1 script | Check word count, table coverage, synthesis density |

## Forbidden Patterns (auto-rejected)

- Consecutive paragraphs each starting with an author name
- Standalone "X achieved accuracy Y%" sentences without comparison to another paper
- More than two consecutive sentences beginning with an author name
- Tables that only list paper titles and one metric (laundry list in table form)

## File Structure

```
review-writing-harness/
├── README.md                              # Chinese readme (default)
├── README_EN.md                           # English readme
├── pdf_to_md/                             # PDF → Markdown conversion tool
│   ├── batch_convert.py                   # Batch conversion script
│   ├── requirements.txt                   # Python dependencies
│   └── README.md                          # Detailed usage guide
└── nature-writing/                        # Literature review skill
    ├── SKILL.md                           # Skill router
    ├── manifest.yaml                      # Axis detection manifest
    ├── scripts/
    │   ├── prepare_local_md_review.py     # Preparation + all prompt generation
    │   ├── validate_word_count.py         # Word count validation
    │   └── validate_citation_order.py     # Citation coherence validation
    ├── references/
    │   ├── local-md-review.md             # Complete workflow specification
    │   └── ...                            # Section drafting references
    ├── static/                            # Versioned content fragments
    │   ├── core/                          # Stance, workflow, output format
    │   └── fragments/                     # Per-axis fragments
    └── agents/                            # Agent configuration
```

## Quick Start

### Prerequisite: Convert Papers to Markdown

The **zero-hallucination guarantee** of this workflow depends on local paper reading — all cited evidence must come from your provided local Markdown files, not from the LLM's training data "memory." Therefore, you must batch-convert your PDF papers into well-structured Markdown files before starting the workflow.

#### Option 1: Built-in pdf_to_md tool (based on marker)

The repo includes `pdf_to_md/` (built on [marker](https://github.com/VikParuchuri/marker)) for this step:

```bash
# 1. Install PDF conversion dependencies
pip install -r pdf_to_md/requirements.txt

# 2. Batch convert PDF → Markdown (models ~3-5GB auto-downloaded on first run)
python pdf_to_md/batch_convert.py --input /path/to/pdfs --output /path/to/markdown
```

The output Markdown files preserve the original heading hierarchy, paragraph structure, tables, and key numerical values. Place all `.md` files in a single directory (the path you will pass to `--corpus`). See [pdf_to_md/README.md](pdf_to_md/README.md) for details.

#### Option 2: scansci-pdf MCP (Recommended)

[scansci-pdf](https://pypi.org/project/scansci-pdf/) is an academic PDF download MCP server with support for Sci-Hub, open-access sources, university WebVPN, and Tor. Once integrated with Claude Code, you can **download papers directly by DOI or arXiv ID** without manually searching for PDFs:

```bash
# Install
pip install scansci-pdf

# Configure as Claude Code MCP server (add to settings.json)
# "mcpServers": {
#   "scansci-pdf": {
#     "command": "scansci-pdf", "args": ["run"]
#   }
# }

# Download a paper directly in Claude Code
scansci-pdf get 10.1038/s41586-024-xxxxx --output ./papers
```

Once configured, you can simply say "download this paper" in your Claude Code session — Claude will automatically call scansci-pdf to fetch the PDF, then convert it to Markdown via pdf_to_md before entering the workflow.

> **Note**: Reading PDFs directly consumes excessive context windows and cannot precisely locate paragraphs. Always convert PDFs to Markdown first before launching the workflow.

### Launch the Workflow

Prepare your files, then type a prompt in Claude Code:

```bash
# 1. Organize your framework and papers
your_project/
├── local_framework.md    # H1/H2 structure + word target (see format below)
└── papers/               # Converted Markdown papers (from previous step)
```

In your Claude Code session, simply type:

> Based on the papers in ./papers and the ./local_framework.md framework, invoke the nature-writing local workflow to complete the literature review.

Claude Code will automatically execute the full pipeline:

```
Prepare → Doctors(×N) → Voters(×3) → Expert Merge → Synthesizers(×M) → Main Writer → Validate
```

All intermediate artifacts (evidence JSON, voting results, synthesis grids, validation report) and the final `literature_review.md` are written to `papers/nature_local_review_YYYYMMDD_HHMMSS/`.

### Framework Format

```markdown
# 1 Introduction
## 1.1 Background and motivation
## 1.2 Scope and organization

# 2 Core Methods
## 2.1 Method category A
## 2.2 Method category B

# 3 Challenges and Future Directions

# 4 Conclusion

Total word target: 6000
```

## Validation Gates

| Gate | Check | Threshold |
|------|-------|-----------|
| Word count | Chinese characters within target | ±10% |
| Table coverage | ≥1 table per H1 with ≥4 evidence items | Span ≥3 papers × ≥3 dimensions |
| Synthesis density | Cross-comparison sentences / total sentences | ≥0.25 |
| Incomparability | No direct comparison of papers with different label standards or validation protocols | Zero violations |
| Forbidden patterns | No author-name laundry lists | Zero violations |

## Key Changes from Original nature-writing

> This project is a deep enhancement of [`nature-skills/nature-writing`](https://github.com/Yuan1z0825/nature-skills). Below is a comparison with the original `nature-writing` skill:

| Original nature-writing | This Enhanced Version |
|----------|----------|
| Paper-by-paper citation writing | Synthesis-first 4-layer protocol |
| No comparison tables required | Mandatory 12-dimension comparison tables |
| No structured comparative dimensions | `comparative_dimensions` field in every evidence item |
| No synthesis phase | Table-first synthesizer stage (per H1) |
| Basic validation (word count only) | Table coverage, synthesis density, incomparability checks |
| "Cite every claim" | "Group, compare, then cite" with multi-citation syntax `[@a; @b]` |

## Design Philosophy

The core design principle: **The atomic unit of evidence should be transformed from `(paper, section, claim)` to `(section, comparison_dimension, range)`, completing this "transposition" before the agent writes a single word.** This is the fundamental difference between genuine synthesis and an advanced laundry list.

## Acknowledgements

- [nature-skills](https://github.com/Yuan1z0825/nature-skills) — The upstream foundation of this project, providing the original `nature-writing` skill architecture, agent prompt templates, and workflow design
- [marker](https://github.com/VikParuchuri/marker) — The core PDF-to-Markdown conversion engine
- [scansci-pdf](https://pypi.org/project/scansci-pdf/) — Academic paper download MCP server

## License

MIT

## Citation

If you use this workflow in your research, please cite:

```bibtex
@software{review_writing_harness,
  author = {Yu Bai and Anthropic},
  title = {Review Writing Harness: Synthesis-First Multi-Agent Literature Review},
  year = {2026},
  url = {https://github.com/YuBai630/review-writing-harness}
}
```
