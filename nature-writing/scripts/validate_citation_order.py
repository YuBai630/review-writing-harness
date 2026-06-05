#!/usr/bin/env python3
"""Validate Pandoc citation keys against a BibTeX file and citation order."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


CITATION_BRACKET_RE = re.compile(r"\[([^\]]*@[^]]+)\]")
CITATION_KEY_RE = re.compile(r"@([A-Za-z0-9_:\-]+)")
BIB_ENTRY_RE = re.compile(r"@\w+\s*\{\s*([^,\s]+)\s*,", re.I)


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace").lstrip("\ufeff")


def citation_order(markdown: str) -> list[str]:
    seen: set[str] = set()
    order: list[str] = []
    for bracket in CITATION_BRACKET_RE.findall(markdown):
        for key in CITATION_KEY_RE.findall(bracket):
            if key not in seen:
                seen.add(key)
                order.append(key)
    return order


def bib_order(bibtex: str) -> list[str]:
    return BIB_ENTRY_RE.findall(bibtex)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--review", required=True, help="Path to literature_review.md")
    parser.add_argument("--bib", required=True, help="Path to references.bib")
    parser.add_argument("--report", help="Optional report path")
    args = parser.parse_args(argv)

    review_path = Path(args.review).expanduser().resolve()
    bib_path = Path(args.bib).expanduser().resolve()
    report_path = Path(args.report).expanduser().resolve() if args.report else review_path.with_name("validation_report.txt")

    cited = citation_order(read_text(review_path))
    bib_keys = bib_order(read_text(bib_path))
    bib_set = set(bib_keys)

    lines = ["Citation-order validation report", ""]
    ok = True

    if not cited:
        ok = False
        lines.append("FAIL citations: no Pandoc citations found in review.")
    if not bib_keys:
        ok = False
        lines.append("FAIL bib: no BibTeX entries found.")

    missing = [key for key in cited if key not in bib_set]
    if missing:
        ok = False
        lines.append("FAIL missing BibTeX entries: " + ", ".join(missing))
    else:
        lines.append("PASS missing BibTeX entries: none")

    bib_cited_order = [key for key in bib_keys if key in set(cited)]
    if cited and bib_cited_order != cited:
        ok = False
        lines.append("FAIL order: references.bib cited-entry order does not match first citation order.")
        lines.append("First citation order: " + ", ".join(cited))
        lines.append("BibTeX cited order: " + ", ".join(bib_cited_order))
    elif cited:
        lines.append("PASS order: references.bib follows first citation order.")

    extra = [key for key in bib_keys if key not in set(cited)]
    if extra:
        lines.append("WARN uncited BibTeX entries: " + ", ".join(extra))

    prior = report_path.read_text(encoding="utf-8", errors="replace") if report_path.exists() else ""
    if prior and not prior.endswith("\n"):
        prior += "\n"
    report_path.write_text(prior + "\n".join(lines) + "\n", encoding="utf-8")
    print(report_path)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
