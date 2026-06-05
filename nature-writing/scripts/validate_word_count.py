#!/usr/bin/env python3
"""Validate total and H2-level word counts for a local-md-review draft."""

from __future__ import annotations

import argparse
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
WORD_RE = re.compile(r"[A-Za-z0-9]+(?:[-'][A-Za-z0-9]+)?")


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace").lstrip("\ufeff")


def parse_total_word_target(text: str) -> int | None:
    for pattern in TOTAL_TARGET_PATTERNS:
        match = pattern.search(text)
        if match:
            return int(match.group(1))
    return None


def clean_heading(raw: str) -> str:
    return raw.strip().strip("#").strip()


def parse_framework_targets(framework_text: str) -> tuple[int | None, dict[str, int]]:
    total = parse_total_word_target(framework_text)
    current_h2: str | None = None
    h2_targets: dict[str, int] = {}
    for line in framework_text.splitlines():
        if line.startswith("## "):
            current_h2 = clean_heading(line[3:])
            continue
        if current_h2:
            match = H2_WORD_TARGET_RE.search(line)
            if match:
                h2_targets[current_h2] = int(match.group(1))
    return total, h2_targets


def count_words(text: str) -> int:
    text = re.sub(r"```.*?```", " ", text, flags=re.S)
    text = re.sub(r"`[^`]+`", " ", text)
    text = re.sub(r"\[@[^\]]+\]", " ", text)
    text = re.sub(r"(?m)^#{1,6}\s+.*$", " ", text)
    return len(WORD_RE.findall(text))


def split_review_h2(review_text: str) -> dict[str, str]:
    sections: dict[str, list[str]] = {}
    current_h2: str | None = None
    for line in review_text.splitlines():
        if line.startswith("# "):
            current_h2 = None
            continue
        if line.startswith("## "):
            current_h2 = clean_heading(line[3:])
            sections.setdefault(current_h2, [])
            continue
        if current_h2:
            sections[current_h2].append(line)
    return {title: "\n".join(lines) for title, lines in sections.items()}


def in_range(value: int, target: int, tolerance: float) -> bool:
    low = target * (1 - tolerance)
    high = target * (1 + tolerance)
    return low <= value <= high


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--framework", required=True, help="Path to local_framework.md")
    parser.add_argument("--review", required=True, help="Path to literature_review.md")
    parser.add_argument("--report", help="Optional report path")
    parser.add_argument("--total-tolerance", type=float, default=0.10)
    parser.add_argument("--h2-tolerance", type=float, default=0.20)
    args = parser.parse_args(argv)

    framework_path = Path(args.framework).expanduser().resolve()
    review_path = Path(args.review).expanduser().resolve()
    report_path = Path(args.report).expanduser().resolve() if args.report else review_path.with_name("validation_report.txt")

    framework_text = read_text(framework_path)
    review_text = read_text(review_path)
    total_target, h2_targets = parse_framework_targets(framework_text)

    lines = ["Word-count validation report", ""]
    ok = True

    if total_target is None:
        ok = False
        lines.append("FAIL total: no total_word_target found in framework.")
    else:
        actual_total = count_words(review_text)
        result = "PASS" if in_range(actual_total, total_target, args.total_tolerance) else "FAIL"
        ok = ok and result == "PASS"
        lines.append(
            f"{result} total: actual={actual_total}, target={total_target}, tolerance=+/-{args.total_tolerance:.0%}"
        )

    review_h2 = split_review_h2(review_text)
    for heading, target in h2_targets.items():
        if heading not in review_h2:
            ok = False
            lines.append(f"FAIL H2 '{heading}': heading missing from review.")
            continue
        actual = count_words(review_h2[heading])
        result = "PASS" if in_range(actual, target, args.h2_tolerance) else "FAIL"
        ok = ok and result == "PASS"
        lines.append(f"{result} H2 '{heading}': actual={actual}, target={target}, tolerance=+/-{args.h2_tolerance:.0%}")

    if not h2_targets:
        lines.append("INFO H2: no H2 word_target comments found; only total word count was validated.")

    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(report_path)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
