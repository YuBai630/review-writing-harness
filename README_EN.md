[![中文](https://img.shields.io/badge/语言-中文-red)](README.md) [![English](https://img.shields.io/badge/Language-English-blue)](README_EN.md)

# Review Writing Harness

A synthesis-first multi-agent workflow for writing literature reviews from local Markdown paper corpora. Built as an extension to the `nature-writing` skill in Claude Code.

## The Problem

Traditional literature review workflows produce **paper-by-paper laundry lists**: "Smith et al. proposed X and achieved 92%. Jones et al. proposed Y and achieved 88%. Lee et al. proposed Z..." — each paragraph is a single-paper summary, with no cross-paper comparison, no performance range synthesis, no incomparability warnings, and no structured comparison tables.

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
nature-writing/
├── SKILL.md                          # Skill router
├── manifest.yaml                     # Axis detection manifest
├── scripts/
│   ├── prepare_local_md_review.py    # Preparation + all prompt generation
│   ├── validate_word_count.py        # Word count validation
│   └── validate_citation_order.py    # Citation coherence validation
├── references/
│   ├── local-md-review.md            # Complete workflow specification
│   └── ...                           # Section drafting references
├── static/                           # Versioned content fragments
│   ├── core/                         # Stance, workflow, output format
│   └── fragments/                    # Per-axis fragments (paper_type, section, language, journal)
└── agents/                           # Agent configuration
```

## Quick Start

```bash
# 1. Place your framework as local_framework.md in your paper directory
# 2. Run the preparation script
python scripts/prepare_local_md_review.py \
  --framework /path/to/local_framework.md \
  --corpus /path/to/markdown/papers

# 3. Follow the generated prompts through the workflow:
#    Doctor → Voter → Expert → Synthesizer → Main Writer → Validate
```

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

| Original | Enhanced |
|----------|----------|
| Paper-by-paper citation writing | Synthesis-first 4-layer protocol |
| No comparison tables required | Mandatory 12-dimension comparison tables |
| No structured comparative dimensions | `comparative_dimensions` field in every evidence item |
| No synthesis phase | Table-first synthesizer stage (per H1) |
| Basic validation (word count only) | Table coverage, synthesis density, incomparability checks |
| "Cite every claim" | "Group, compare, then cite" with multi-citation syntax `[@a; @b]` |

## Design Philosophy

The core design principle: **The atomic unit of evidence should be transformed from `(paper, section, claim)` to `(section, comparison_dimension, range)`, completing this "transposition" before the agent writes a single word.** This is the fundamental difference between genuine synthesis and an advanced laundry list.

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
