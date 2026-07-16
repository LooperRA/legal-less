"""Command-line interface for legal-less."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from . import __version__
from .cfa import analyze_cfa_file, render_cfa_markdown
from .representation import (
    compare_csv_files,
    extract_judgment_representations,
    judgment_records_to_csv,
    render_representation_markdown,
)


def _write_output(path: str | None, content: str) -> None:
    if path:
        output = Path(path)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(content, encoding="utf-8")
    else:
        sys.stdout.write(content)


def _run_cfa_analyze(args: argparse.Namespace) -> int:
    analysis = analyze_cfa_file(
        args.input,
        source_url=args.source_url,
        retrieved_at=args.retrieved_at,
    )
    markdown = render_cfa_markdown(analysis)
    if args.json_output:
        _write_output(args.json_output, analysis.to_json() + "\n")
    if args.markdown_output:
        _write_output(args.markdown_output, markdown)
    if not args.json_output and not args.markdown_output:
        _write_output(None, markdown)
    return 0 if analysis.verified_hkcfa else 2


def _run_representation_extract(args: argparse.Namespace) -> int:
    raw = Path(args.input).read_text(encoding="utf-8")
    records = extract_judgment_representations(
        raw,
        judgment_date=args.judgment_date,
        source_url=args.source_url,
        retrieved_at=args.retrieved_at,
        case_name=args.case_name or "",
        outcome=args.outcome or "Not supplied",
    )
    _write_output(args.csv_output, judgment_records_to_csv(records))
    return 0 if records else 3


def _run_representation_compare(args: argparse.Namespace) -> int:
    analysis = compare_csv_files(
        args.cause_csv,
        args.judgment_csv,
        minimum_case_count=args.minimum_case_count,
    )
    markdown = render_representation_markdown(analysis)
    if args.json_output:
        _write_output(args.json_output, analysis.to_json() + "\n")
    if args.markdown_output:
        _write_output(args.markdown_output, markdown)
    if not args.json_output and not args.markdown_output:
        _write_output(None, markdown)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="legal-less",
        description="Auditable Hong Kong court-research tools.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    commands = parser.add_subparsers(dest="command", required=True)

    cfa = commands.add_parser("cfa", help="Analyze an operator-provided HKCFA judgment")
    cfa_commands = cfa.add_subparsers(dest="cfa_command", required=True)
    analyze = cfa_commands.add_parser(
        "analyze",
        help="Apply the five-question framework and rank ratio candidates",
    )
    analyze.add_argument("input", help="UTF-8 text, Markdown, or HTML judgment file")
    analyze.add_argument(
        "--source-url",
        help="Human-verifiable source URL recorded as provenance; no network request is made",
    )
    analyze.add_argument(
        "--retrieved-at",
        help="Optional ISO-8601 retrieval timestamp; defaults to the current UTC time",
    )
    analyze.add_argument("--json-output", help="Path for the machine-readable report")
    analyze.add_argument("--markdown-output", help="Path for the human-review report")
    analyze.set_defaults(handler=_run_cfa_analyze)

    representation = commands.add_parser(
        "representation",
        help="Map operator-provided cause-list records to final-judgment evidence",
    )
    representation_commands = representation.add_subparsers(
        dest="representation_command",
        required=True,
    )

    extract = representation_commands.add_parser(
        "extract-judgment",
        help="Extract firm and represented-side lines from a local judgment",
    )
    extract.add_argument("input", help="UTF-8 text, Markdown, or HTML judgment file")
    extract.add_argument("--judgment-date", required=True, help="Judgment date in YYYY-MM-DD")
    extract.add_argument(
        "--source-url", required=True, help="Public source URL recorded as evidence"
    )
    extract.add_argument("--retrieved-at", required=True, help="ISO-8601 retrieval timestamp")
    extract.add_argument("--case-name", help="Reviewed case name; no name inference is required")
    extract.add_argument("--outcome", help="Reviewed final outcome; defaults to Not supplied")
    extract.add_argument(
        "--csv-output",
        help="Path for review-ready judgment records; defaults to standard output",
    )
    extract.set_defaults(handler=_run_representation_extract)

    compare = representation_commands.add_parser(
        "compare",
        help="Compare reviewed cause-list and judgment CSV records",
    )
    compare.add_argument("cause_csv", help="Cause-list import using the documented schema")
    compare.add_argument("judgment_csv", help="Final-judgment import using the documented schema")
    compare.add_argument(
        "--minimum-case-count",
        type=int,
        default=5,
        help="Distinct listed cases required before a firm-level rate is shown (default: 5)",
    )
    compare.add_argument("--json-output", help="Path for the machine-readable evidence map")
    compare.add_argument("--markdown-output", help="Path for the human-review report")
    compare.set_defaults(handler=_run_representation_compare)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.handler(args))


if __name__ == "__main__":
    raise SystemExit(main())
