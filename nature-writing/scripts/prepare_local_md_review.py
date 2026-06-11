#!/usr/bin/env python3
"""Prepare a local Markdown review run for the nature-writing skill."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path


TOTAL_TARGET_PATTERNS = [
    re.compile(r"(?im)^\s*total_word_target\s*:\s*(\d+)\s*$"),
    re.compile(r"<!--\s*total_word_target\s*:\s*(\d+)\s*-->", re.I),
    re.compile(r"(?im)^\s*(?:总体字数|总字数)\s*[:：]\s*(\d+)\s*$"),
    re.compile(r"(?im)^\s*Total word target\s*[:：]\s*(\d+)\s*$"),
]
H2_WORD_TARGET_RE = re.compile(r"<!--\s*word_target\s*:\s*(\d+)\s*-->", re.I)


def read_text(path: Path, limit: int | None = None) -> str:
    data = path.read_text(encoding="utf-8", errors="replace")
    data = data.lstrip("﻿")
    if limit is not None:
        return data[:limit]
    return data


def slugify(value: str, fallback: str = "item") -> str:
    value = value.lower()
    value = re.sub(r"[^a-z0-9]+", "_", value)
    value = re.sub(r"_+", "_", value).strip("_")
    return value or fallback


def parse_total_word_target(text: str) -> int | None:
    for pattern in TOTAL_TARGET_PATTERNS:
        match = pattern.search(text)
        if match:
            return int(match.group(1))
    return None


def clean_heading(raw: str) -> str:
    return raw.strip().strip("#").strip()


def portable_path(abs_path: Path, run_root: Path) -> str:
    """Return POSIX-style path relative to run_root.  Falls back to absolute."""
    try:
        return abs_path.relative_to(run_root).as_posix()
    except ValueError:
        return abs_path.as_posix()


def parse_framework(path: Path, run_root: Path) -> dict:
    text = read_text(path)
    total_word_target = parse_total_word_target(text)
    headings: list[dict] = []
    current_h1: dict | None = None
    current_h2: dict | None = None

    for line_no, line in enumerate(text.splitlines(), start=1):
        if line.startswith("# ") and not line.startswith("## "):
            current_h1 = {
                "id": f"H1_{len([h for h in headings if h['level'] == 1]) + 1:02d}",
                "level": 1,
                "title": clean_heading(line[2:]),
                "line": line_no,
                "notes": [],
            }
            headings.append(current_h1)
            current_h2 = None
            continue
        if line.startswith("## "):
            if current_h1 is None:
                raise ValueError(f"H2 found before any H1 at line {line_no}: {line}")
            current_h2 = {
                "id": f"{current_h1['id']}_H2_{len([h for h in headings if h.get('parent_id') == current_h1['id']]) + 1:02d}",
                "level": 2,
                "title": clean_heading(line[3:]),
                "line": line_no,
                "parent_id": current_h1["id"],
                "parent_title": current_h1["title"],
                "notes": [],
                "word_target": None,
            }
            headings.append(current_h2)
            continue
        target = current_h2 or current_h1
        if target is not None:
            word_target = H2_WORD_TARGET_RE.search(line)
            if word_target and target["level"] == 2:
                target["word_target"] = int(word_target.group(1))
            elif line.strip():
                target["notes"].append(line.rstrip())

    h1_count = len([h for h in headings if h["level"] == 1])
    h2_count = len([h for h in headings if h["level"] == 2])
    if h1_count == 0:
        raise ValueError("local_framework.md must contain at least one '# ' H1 heading.")
    if h2_count == 0:
        raise ValueError("local_framework.md must contain at least one '## ' H2 heading.")
    if total_word_target is None:
        raise ValueError(
            "local_framework.md must contain total_word_target, an HTML total_word_target comment, "
            "'总体字数：N', or 'Total word target: N'."
        )

    return {
        "framework_path": portable_path(path, run_root),
        "framework_path_current_platform": str(path),
        "total_word_target": total_word_target,
        "total_word_tolerance": 0.10,
        "h2_word_tolerance": 0.20,
        "headings": headings,
    }


def parse_metadata(path: Path, existing_keys: set[str], run_root: Path) -> dict:
    sample = read_text(path, limit=50000)
    title = None
    author = None
    year = None
    venue = None
    doi = None

    for pattern in [
        re.compile(r"(?im)^\s*title\s*:\s*[\"']?(.+?)[\"']?\s*$"),
        re.compile(r"(?m)^#\s+(.+?)\s*$"),
    ]:
        match = pattern.search(sample)
        if match:
            title = match.group(1).strip()
            break

    for pattern in [
        re.compile(r"(?im)^\s*authors?\s*:\s*[\"']?(.+?)[\"']?\s*$"),
        re.compile(r"(?im)^\s*by\s+(.+?)\s*$"),
    ]:
        match = pattern.search(sample)
        if match:
            author = match.group(1).strip()
            break

    year_match = re.search(r"\b(19|20)\d{2}\b", sample)
    if year_match:
        year = year_match.group(0)

    venue_match = re.search(r"(?im)^\s*(?:journal|venue|booktitle)\s*:\s*[\"']?(.+?)[\"']?\s*$", sample)
    if venue_match:
        venue = venue_match.group(1).strip()

    doi_match = re.search(r"\b10\.\d{4,9}/[-._;()/:A-Z0-9]+\b", sample, flags=re.I)
    if doi_match:
        doi = doi_match.group(0)

    first_author = "unknown"
    if author:
        first_author = re.split(r"\s+and\s+|,|;", author)[0].strip().split()[-1]
    keyword = path.stem
    if title:
        words = [w for w in re.findall(r"[A-Za-z0-9]+", title) if len(w) > 3]
        if words:
            keyword = words[0]
    base_key = slugify(f"{first_author}_{year or 'unknown'}_{keyword}", path.stem)
    citation_key = base_key
    suffix = 2
    while citation_key in existing_keys:
        citation_key = f"{base_key}_{suffix}"
        suffix += 1
    existing_keys.add(citation_key)

    return {
        "paper_id": slugify(path.stem, path.stem),
        "path": portable_path(path, run_root),
        "path_current_platform": str(path),
        "title": title or "Unknown",
        "authors": author or "Unknown",
        "year": year or "Unknown",
        "venue": venue or "Unknown",
        "doi": doi or "Unknown",
        "citation_key": citation_key,
        "byte_size": path.stat().st_size,
    }


def is_relative_to(child: Path, parent: Path) -> bool:
    try:
        child.relative_to(parent)
        return True
    except ValueError:
        return False


def collect_papers(corpus: Path, framework: Path, outdir: Path) -> list[Path]:
    papers = []
    framework = framework.resolve()
    outdir = outdir.resolve()
    for path in sorted(corpus.rglob("*.md"), key=lambda p: str(p).lower()):
        resolved = path.resolve()
        if resolved == framework:
            continue
        if path.name.lower() == "local_framework.md":
            continue
        if is_relative_to(resolved, outdir):
            continue
        # Exclude historical nature_local_review_* run directories
        if any(part.startswith("nature_local_review_") for part in path.parts):
            continue
        papers.append(resolved)
    return papers


def make_outdir(corpus: Path, outdir: str | None) -> Path:
    if outdir:
        target = Path(outdir).expanduser().resolve()
    else:
        stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
        target = (corpus / f"nature_local_review_{stamp}").resolve()
        counter = 2
        while target.exists():
            target = (corpus / f"nature_local_review_{stamp}_{counter:02d}").resolve()
            counter += 1
    target.mkdir(parents=True, exist_ok=False)
    for subdir in ["agent_prompts", "doctor_outputs", "voter_output", "expert_outputs", "synthesis_grids"]:
        (target / subdir).mkdir(parents=True, exist_ok=True)
    return target


def batch_papers(papers: list[dict], batch_size: int, max_batch_bytes: int) -> list[list[dict]]:
    batches: list[list[dict]] = []
    current: list[dict] = []
    current_bytes = 0
    for paper in papers:
        size = int(paper["byte_size"])
        would_exceed_count = len(current) >= batch_size
        would_exceed_bytes = current and current_bytes + size > max_batch_bytes
        if would_exceed_count or would_exceed_bytes:
            batches.append(current)
            current = []
            current_bytes = 0
        item = dict(paper)
        item["overflow_risk"] = size > max_batch_bytes
        current.append(item)
        current_bytes += size
    if current:
        batches.append(current)
    return batches


def write_json(path: Path, data: object) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def framework_markdown(framework: dict) -> str:
    lines = [f"Total word target: {framework['total_word_target']}"]
    for heading in framework["headings"]:
        prefix = "#" if heading["level"] == 1 else "##"
        lines.append(f"{prefix} {heading['title']}")
        if heading.get("word_target"):
            lines.append(f"word_target: {heading['word_target']}")
        for note in heading.get("notes", []):
            lines.append(note)
    return "\n".join(lines)


def doctor_prompt(batch_index: int, batch: list[dict], framework: dict, outdir: Path, max_agents: int, run_root: Path) -> str:
    schema = {
        "paper_id": "filename_without_ext",
        "citation_key": "author_year_keyword",
        "target_heading": "Exact H2 title",
        "support_level": "direct | partial | negative | irrelevant",
        "claim_supported": "One sentence claim",
        "evidence_summary": "1-2 sentences",
        "source_anchor": "Markdown heading/section/paragraph/table/page marker",
        "short_quote": "Source wording, <=200 chars",
        "limitations": "Boundary or caveat",
        "tags": {
            "methodology": [],
            "topic": [],
            "evidence_strength": "strong | moderate | weak",
            "year": "Unknown",
            "venue": "Unknown",
            "has_open_data": False,
            "relevance_to_which_H2": {"Exact H2 title": "high | medium | low | none"},
        },
        "comparative_dimensions": {
            "device_type": "finger_PPG | wrist_PPG | ring_PPG | chest_ECG | dry_EEG | nasal_pressure | ...",
            "modalities": ["PPG", "ACC"],
            "sample_size": "integer, e.g., 394",
            "population": "healthy | OSA | insomnia | pediatric | elderly | mixed_clinical",
            "n_classes": "2 | 3 | 4 | 5",
            "label_standard": "AASM | R&K | other",
            "validation": "LOSO | k_fold | hold_out | external | multi_source",
            "primary_metric": {"name": "kappa | accuracy | F1 | AUROC", "value": 0.0},
            "model_class": "CNN | RNN | Transformer | GNN | hybrid | classical_ML",
            "parameter_count": "190K | 5M | unknown",
        },
    }
    paper_lines = "\n".join(
        f"- {paper['paper_id']} | {paper['citation_key']} | {paper['path']} | overflow_risk={paper['overflow_risk']}"
        for paper in batch
    )
    rel_doctor_json = portable_path(outdir / "doctor_outputs" / f"doctor_batch_{batch_index:03d}.json", run_root)
    rel_doctor_md = portable_path(outdir / "doctor_outputs" / f"doctor_batch_{batch_index:03d}.md", run_root)
    return f"""You are a doctor subagent for the nature-writing local-md-review workflow.

Concurrency rule for the parent workflow: at most {max_agents} subagents may be active at once. You only handle this assigned batch.

Read every assigned Markdown paper as fully as context allows. If a paper is too large to read fully, report overflow and list which sections you read. Map only relevant or possibly relevant evidence to exact H2 titles.

Output JSON evidence items and a concise Markdown summary. If you can write files, write:
- {rel_doctor_json}
- {rel_doctor_md}

Evidence schema:
```json
{json.dumps(schema, ensure_ascii=False, indent=2)}
```

Rules:
- support_level must be direct, partial, negative, or irrelevant.
- relevance_to_which_H2 must use exact H2 titles as keys and high, medium, low, or none as values.
- comparative_dimensions is STRONGLY RECOMMENDED for every evidence item. Fill every field you can extract from the paper (device type, modalities, sample size, population, n_classes, label standard, validation protocol, primary metric with value, model class, parameter count). Use "unknown" for genuinely unavailable fields — do not invent data. This structured field is critical for downstream automated comparison table generation. If you skip it, the synthesis phase will need to re-extract these dimensions from your prose, which is error-prone.
- Tags and metadata must come from paper content; do not invent missing fields.
- short_quote must be <=200 characters.

Framework:
{framework_markdown(framework)}

Assigned papers:
{paper_lines}
"""


def voter_prompt(outdir: Path, run_root: Path) -> str:
    rel_framework = portable_path(outdir / "framework.json", run_root)
    rel_manifest = portable_path(outdir / "paper_manifest.jsonl", run_root)
    rel_doctor = portable_path(outdir / "doctor_outputs", run_root)
    return f"""You are one of exactly three independent thinking subagents for local-md-review voting.

Read only:
- {rel_framework}
- {rel_manifest}
- all files under {rel_doctor}

Do not read original papers. For each candidate paper_id + H2, vote included or excluded.

Include when relevance_to_which_H2[H2] is high or medium, support_level is direct or partial, and tags match the H2 notes. Exclude negative or irrelevant evidence unless it should be retained as a contradiction note.

Return rows with:
paper_id,heading,vote_result,vote_reason_summary
"""


def expert_prompt(outdir: Path, run_root: Path) -> str:
    rel_framework = portable_path(outdir / "framework.json", run_root)
    rel_manifest = portable_path(outdir / "paper_manifest.jsonl", run_root)
    rel_csv = portable_path(outdir / "paper_heading_assignment.csv", run_root)
    rel_doctor = portable_path(outdir / "doctor_outputs", run_root)
    rel_evidence = portable_path(outdir / "local_evidence_map.json", run_root)
    rel_audit = portable_path(outdir / "citation_audit.md", run_root)
    return f"""You are the domain expert merger for local-md-review.

Inputs:
- {rel_framework}
- {rel_manifest}
- {rel_csv}
- all doctor outputs under {rel_doctor}

Merge evidence by exact H2. Deduplicate near-identical claims. Sort direct before partial, then strong, moderate, weak. Preserve negative or contradictory evidence in citation_audit.md.

If an H2 has fewer than two local direct + partial evidence items, mark external_needed=true and draft 1-3 precise external search queries. Do not fabricate external citations.

Write or return:
- {rel_evidence}
- {rel_audit}
"""


def synthesizer_prompt(outdir: Path, h1_title: str, h1_id: str, run_root: Path) -> str:
    """Generate a table-first synthesis prompt for one H1 section."""
    rel_framework = portable_path(outdir / "framework.json", run_root)
    rel_evidence = portable_path(outdir / "local_evidence_map.json", run_root)
    rel_manifest = portable_path(outdir / "paper_manifest.jsonl", run_root)
    rel_csv = portable_path(outdir / "paper_heading_assignment.csv", run_root)
    rel_doctor = portable_path(outdir / "doctor_outputs", run_root)
    rel_synthesis = portable_path(outdir / "synthesis_grids" / f"synthesis_{h1_id}.md", run_root)
    # Derive H2 children for this H1 and their comparison dimensions
    return f"""You are a table-first synthesizer for the nature-writing local-md-review workflow.

Your sole job: read the evidence collected for H1 section "{h1_title}" and produce
a structured synthesis grid. Do NOT write narrative prose — the main writer will
do that based on your output.

Inputs:
- {rel_framework}
- {rel_evidence}
- {rel_manifest}
- {rel_csv}
- {rel_doctor}/ (all doctor batch outputs)

===========================================================================
OUTPUT 1 — COMPARISON TABLE (MANDATORY)
===========================================================================

Generate at least one Markdown comparison table for the evidence in this H1 section.

Table rules:
- Use Markdown pipe syntax
- Span ALL papers assigned to this H1 (at minimum, all direct+partial evidence)
- Include these dimensions as columns (adapt based on what data is actually available):
  1. Study (citation_key)
  2. Sensor/Device type (finger_PPG | wrist_PPG | ring_PPG | chest_ECG | dry_EEG | ...)
  3. Signal modalities (e.g., "PPG", "PPG+ACC", "EEG+EOG+EMG")
  4. Sample size (N)
  5. Population (healthy | OSA | insomnia | pediatric | elderly | mixed_clinical)
  6. Task / N classes (2-class | 3-class | 4-class | 5-class)
  7. Label standard (AASM | R&K | other)
  8. Validation protocol (LOSO | k-fold | hold-out | external | multi-source)
  9. Key metric 1 — Cohen's kappa (if reported)
  10. Key metric 2 — Accuracy (if reported)
  11. Model architecture class (CNN | RNN | Transformer | GNN | hybrid | classical_ML)
  12. Parameter count or computational notes (if reported)
- Fill in "NR" (not reported) for missing cells — never invent data
- Sort rows by a meaningful dimension (e.g., by population, then by kappa descending)

If a single table cannot fit all papers (e.g., very different tasks), create
separate sub-tables grouped by task type. Label each sub-table clearly.

===========================================================================
OUTPUT 2 — PERFORMANCE RANGE SUMMARY (MANDATORY)
===========================================================================

For each task type in this H1 (e.g., "4-class PPG sleep staging", "3-class wearable staging"):

- Range: "kappa X–Y, median Z, N studies"
- Upper bound: which study, under what conditions?
- Lower bound: which study, what explains the low performance?
- Main cluster: what is the typical performance band most studies fall into?
- Outliers: which studies fall outside the main cluster and WHY?
  (different population? different device? different validation? fewer modalities?)

===========================================================================
OUTPUT 3 — INCOMPARABILITY WARNINGS (MANDATORY)
===========================================================================

List paper pairs or groups whose performance numbers SHOULD NOT be directly
compared, and explain why for each case:

Example reasons:
- Different label standards (AASM vs R&K — R&K tends to give higher agreement)
- Different validation protocols (LOSO is stricter than random k-fold)
- Different populations (healthy vs clinical — clinical always harder)
- Different device types (finger-clip PPG has much higher SNR than wrist PPG)
- Different class definitions (3-class vs 4-class vs 5-class)
- Small sample size makes a study's numbers unreliable for comparison

Format:
| Paper A | Paper B | Why not comparable |
|---------|---------|-------------------|
| ... | ... | ... |

===========================================================================
OUTPUT 4 — SYNTHESIS PATTERNS (MANDATORY)
===========================================================================

Extract 3–5 synthesis insights that span ≥2 papers each. These are NOT paper
summaries — they are cross-cutting patterns observed across the evidence.

Format each as: "PATTERN: <one-sentence observation> (evidence: @paper1; @paper2; @paper3)"

Example patterns:
- "PATTERN: Multi-source domain training consistently improves cross-domain kappa
   by 15–21% compared to single-source training (evidence: @a; @b)"
- "PATTERN: Models trained exclusively on healthy populations show kappa drops
   of 0.10–0.20 when tested on sleep disorder patients (evidence: @c; @d; @e)"

Write your output to:
- {rel_synthesis}
"""


def main_writer_prompt(outdir: Path, run_root: Path) -> str:
    rel_framework = portable_path(outdir / "framework.json", run_root)
    rel_evidence = portable_path(outdir / "local_evidence_map.json", run_root)
    rel_synthesis = portable_path(outdir / "synthesis_grids", run_root)
    rel_bib_in = portable_path(outdir / "references.bib", run_root)
    rel_review = portable_path(outdir / "literature_review.md", run_root)
    rel_bib_out = portable_path(outdir / "references.bib", run_root)
    return f"""You are the main writer for local-md-review.

Inputs:
- {rel_framework}
- {rel_evidence}
- {rel_synthesis}/ (table-first synthesis outputs, one per H1 section)
- {rel_bib_in} if it already exists

Draft review prose. Preserve exact H1/H2 title text, levels, and order. Keep total word count within total_word_target +/- 10%; keep H2 word_target sections within +/- 20%.

===========================================================================
MANDATORY WRITING ORDER (per H2 section)
===========================================================================

For every H2 section, write in this EXACT order. Do not skip any layer.

LAYER 1 — SYNTHESIS FIRST (30-40% of H2 word budget):
  - Open with the RANGE of observed performance/metrics/findings across all cited papers, NOT individual numbers.
    BAD:  "Fonseca et al. achieved kappa 0.638... Chih et al. reported kappa 0.643..."
    GOOD: "End-to-end deep learning methods on PPG-derived heart rate achieve kappa values
           ranging from 0.49 to 0.75 for four-class sleep staging, with a median around 0.66."
  - Describe the dominant approaches and what they SHARE (architectural commonalities, shared inputs).
  - Identify clear OUTLIERS and explain WHY they differ (different population? different device?
    different label standard?).
  - Reference the synthesis grid table for the full comparison — do not repeat it in prose.

LAYER 2 — METHODOLOGICAL GROUPING (40-50% of H2 word budget):
  - Group papers by shared methodological approach, NOT by publication date or author name.
  - Examples of valid groupings: "CNN-based methods", "Transformer-based methods",
    "multi-modal fusion methods", "handcrafted-feature methods".
  - Within each group, COMPARE AND CONTRAST. Never list papers sequentially.
    BAD:  "A proposed X. B proposed Y. C proposed Z."
    GOOD: "While A and B both employed CNN encoders on raw PPG, A achieved higher kappa (0.75 vs 0.66)
           due to its multi-source domain training strategy, whereas B's single-domain training limited
           generalization. In contrast, C replaced the CNN with a Transformer and gained... "
  - Use explicit comparison language: "while", "whereas", "in contrast", "similarly",
    "by comparison", "unlike X which..., Y...".

LAYER 3 — INDIVIDUAL DEEP-DIVES (10-20% of H2 word budget):
  - Reserve this layer ONLY for landmark papers that genuinely need detailed exposition
    (foundation models, first-of-its-kind architectures, large-scale clinical validations).
  - You MUST justify in a brief inline comment (<!-- deep-dive: reason -->) why this paper
    warrants individual treatment beyond the grouped comparison.
  - At most 2 deep-dives per H2 section.

LAYER 4 — CRITICAL GAP / INCOMPARABILITY NOTE (10% of H2 word budget):
  - What comparison dimensions are MISSING from the literature?
  - Where do comparisons BREAK because of incompatible methodologies?
  - Example: "Direct cross-method performance comparison is hindered by the fact that
    studies use different PPG sensor types (finger-clip vs. wrist-worn), label standards
    (AASM vs. R&K), and validation protocols (LOSO vs. hold-out)."

===========================================================================
MANDATORY TABLE REQUIREMENTS
===========================================================================

Every H1 section that has ≥4 evidence items across its H2 children MUST contain
at least one Markdown comparison table. The table(s) must:

- Use Markdown pipe syntax (| col1 | col2 | ... |)
- Span ≥3 papers and ≥3 comparison dimensions
- Be placed IMMEDIATELY after the H1 heading (before any H2), or
  at the start of the H2 that has the densest evidence
- Comparison dimensions should include (where applicable):
  * Device/sensor type
  * Signal modalities used
  * Sample size (N)
  * Population (healthy/clinical/pediatric/elderly)
  * Number of sleep stage classes
  * Validation protocol (LOSO/k-fold/hold-out/external)
  * Key performance metric (kappa/accuracy/F1)
  * Model parameter count or computational cost (if reported)

Example format:
| Study | Modality | N | Population | Classes | Validation | Kappa |
|-------|----------|---|------------|---------|------------|-------|
| ... | ... | ... | ... | ... | ... | ... |

Do NOT create a table that only lists paper titles and one metric — that is a
laundry list in table form, not a synthesis table.

===========================================================================
CROSS-PAPER COMPARISON REQUIREMENT
===========================================================================

Your prose must maintain a cross-comparison sentence ratio of at least 0.30:
  - Cross-comparison sentences: Those that compare ≥2 papers using words like
    "while", "whereas", "in contrast", "similarly", "by comparison", "unlike".
  - Single-paper sentences: Those that report a single paper's finding in isolation
    ("X proposed...", "Y achieved...", "Z reported...").
  - Aim for ≥1 cross-comparison sentence per 3 single-paper sentences.

FORBIDDEN PATTERNS — these will cause the draft to be rejected:
  - Consecutive paragraphs each starting with an author name
    ("Fonseca et al. proposed... Chih et al. proposed... Habib et al. used...")
  - A paragraph that reports only one paper's method and result without comparison
  - "X achieved accuracy Y%" or "X reported kappa Z" as a standalone sentence
    without comparison to another paper's performance on the same metric
  - More than two consecutive sentences beginning with an author name

===========================================================================
CITATION RULES
===========================================================================

- Every major claim needs a citation. Use local citations first.
- Use Pandoc citation keys: [@citation_key].
- Multi-citation syntax for comparative claims: [@paper_a; @paper_b].
- A comparative claim that says "A outperformed B" MUST cite both A and B.

Write:
- {rel_review}
- {rel_bib_out}
"""


def write_prompt_files(outdir: Path, framework: dict, batches: list[list[dict]], max_agents: int, run_root: Path) -> None:
    prompt_dir = outdir / "agent_prompts"
    for index, batch in enumerate(batches, start=1):
        (prompt_dir / f"doctor_batch_{index:03d}.md").write_text(
            doctor_prompt(index, batch, framework, outdir, max_agents, run_root),
            encoding="utf-8",
        )
    (prompt_dir / "thinking_voter_prompt.md").write_text(voter_prompt(outdir, run_root), encoding="utf-8")
    (prompt_dir / "expert_merge_prompt.md").write_text(expert_prompt(outdir, run_root), encoding="utf-8")
    # Generate one synthesizer prompt per H1 section that has H2 children with evidence potential
    h1_headings = [h for h in framework["headings"] if h["level"] == 1]
    for h1 in h1_headings:
        # Skip structural-only H1s (摘要, 关键词) that have no H2 children
        if h1["title"] in ("摘要", "关键词"):
            continue
        slug = h1["id"]
        (prompt_dir / f"synthesizer_{slug}.md").write_text(
            synthesizer_prompt(outdir, h1["title"], h1["id"], run_root),
            encoding="utf-8",
        )
    (prompt_dir / "main_writer_prompt.md").write_text(main_writer_prompt(outdir, run_root), encoding="utf-8")


def create_placeholders(outdir: Path, framework: dict) -> None:
    (outdir / "paper_heading_assignment.csv").write_text(
        "paper_id,heading,vote_result,vote_reason_summary\n",
        encoding="utf-8",
    )
    write_json(
        outdir / "local_evidence_map.json",
        {
            "framework_path": framework["framework_path"],
            "total_word_target": framework["total_word_target"],
            "evidence_by_h2": [],
            "external_supplements": [],
        },
    )
    (outdir / "citation_audit.md").write_text("# Citation Audit\n\n", encoding="utf-8")
    (outdir / "validation_report.txt").write_text("Validation has not been run yet.\n", encoding="utf-8")
    write_json(
        outdir / "evidence_item_schema.json",
        {
            "paper_id": "string",
            "citation_key": "string",
            "target_heading": "exact H2 title",
            "support_level": ["direct", "partial", "negative", "irrelevant"],
            "claim_supported": "string",
            "evidence_summary": "string",
            "source_anchor": "string",
            "short_quote": "string <= 200 chars",
            "limitations": "string",
            "tags": {
                "methodology": ["string"],
                "topic": ["string"],
                "evidence_strength": ["strong", "moderate", "weak"],
                "year": "int or Unknown",
                "venue": "string or Unknown",
                "has_open_data": "bool",
                "relevance_to_which_H2": {"exact H2 title": ["high", "medium", "low", "none"]},
            },
            "comparative_dimensions": {
                "device_type": "finger_PPG | wrist_PPG | ring_PPG | chest_ECG | dry_EEG | nasal_pressure | ...",
                "modalities": ["PPG", "ACC", "..."],
                "sample_size": "integer or unknown",
                "population": "healthy | OSA | insomnia | pediatric | elderly | mixed_clinical",
                "n_classes": "2 | 3 | 4 | 5",
                "label_standard": "AASM | R&K | other",
                "validation": "LOSO | k_fold | hold_out | external | multi_source",
                "primary_metric": {"name": "kappa | accuracy | F1 | AUROC", "value": "float"},
                "model_class": "CNN | RNN | Transformer | GNN | hybrid | classical_ML",
                "parameter_count": "string (e.g., 190K, 5M, unknown)",
            },
        },
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--framework", required=True, help="Path to local_framework.md")
    parser.add_argument("--corpus", required=True, help="Directory containing local Markdown papers")
    parser.add_argument("--outdir", help="Optional output directory")
    parser.add_argument("--run-root", help="Project root for portable relative paths (inferred if omitted)")
    parser.add_argument("--batch-size", type=int, default=20, help="Maximum papers per doctor subagent")
    parser.add_argument("--max-concurrent-agents", type=int, default=6, help="Workflow concurrency cap")
    parser.add_argument("--max-batch-bytes", type=int, default=1_800_000, help="Soft byte cap per doctor batch")
    args = parser.parse_args(argv)

    framework_path = Path(args.framework).expanduser().resolve()
    corpus = Path(args.corpus).expanduser().resolve()
    if framework_path.name != "local_framework.md":
        raise SystemExit("The local-md-review workflow requires a framework file named local_framework.md.")
    if not framework_path.exists():
        raise SystemExit(f"Framework not found: {framework_path}")
    if not corpus.is_dir():
        raise SystemExit(f"Corpus directory not found: {corpus}")
    if args.batch_size < 1 or args.batch_size > 20:
        raise SystemExit("--batch-size must be between 1 and 20.")
    if args.max_concurrent_agents != 6:
        raise SystemExit("--max-concurrent-agents must remain 6 for this workflow.")

    # Determine run_root for portable relative paths
    if args.run_root:
        run_root = Path(args.run_root).expanduser().resolve()
    else:
        # Infer: use framework parent if corpus is underneath, else corpus parent
        run_root = framework_path.parent
        try:
            corpus.relative_to(run_root)
        except ValueError:
            run_root = corpus.parent
    if not run_root.is_dir():
        raise SystemExit(f"run-root is not a directory: {run_root}")

    framework = parse_framework(framework_path, run_root)
    outdir = make_outdir(corpus, args.outdir)
    papers = collect_papers(corpus, framework_path, outdir)
    if not papers:
        raise SystemExit("No Markdown papers found after excluding local_framework.md and the output directory.")

    keys: set[str] = set()
    manifest = [parse_metadata(path, keys, run_root) for path in papers]
    batches = batch_papers(manifest, args.batch_size, args.max_batch_bytes)
    for index, batch in enumerate(batches, start=1):
        for paper in batch:
            paper["doctor_batch"] = index

    framework["output_dir"] = portable_path(outdir, run_root)
    framework["output_dir_current_platform"] = str(outdir)
    framework["doctor_batch_count"] = len(batches)
    framework["max_concurrent_subagents"] = args.max_concurrent_agents
    framework["doctor_batch_size_limit"] = args.batch_size

    write_json(outdir / "framework.json", framework)
    write_jsonl(outdir / "paper_manifest.jsonl", manifest)
    write_json(
        outdir / "run_config.json",
        {
            "framework": portable_path(framework_path, run_root),
            "framework_current_platform": str(framework_path),
            "corpus": portable_path(corpus, run_root),
            "corpus_current_platform": str(corpus),
            "outdir": portable_path(outdir, run_root),
            "outdir_current_platform": str(outdir),
            "run_root": str(run_root),
            "batch_size": args.batch_size,
            "max_concurrent_subagents": args.max_concurrent_agents,
            "max_batch_bytes": args.max_batch_bytes,
            "paper_count": len(manifest),
            "doctor_batch_count": len(batches),
            "doctor_wave_count": (len(batches) + args.max_concurrent_agents - 1) // args.max_concurrent_agents,
        },
    )
    write_prompt_files(outdir, framework, batches, args.max_concurrent_agents, run_root)
    create_placeholders(outdir, framework)

    print(f"Prepared local-md-review run: {outdir}")
    print(f"Papers: {len(manifest)}")
    print(f"Doctor batches: {len(batches)}")
    print(f"Max active subagents: {args.max_concurrent_agents}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
