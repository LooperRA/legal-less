from pathlib import Path

from legalless.cli import main

FIXTURE = Path(__file__).parent / "fixtures" / "synthetic_hkcfa.txt"


def test_cfa_cli_writes_json_and_markdown(tmp_path: Path) -> None:
    json_output = tmp_path / "analysis.json"
    markdown_output = tmp_path / "analysis.md"

    result = main(
        [
            "cfa",
            "analyze",
            str(FIXTURE),
            "--source-url",
            "https://example.test/judgment",
            "--json-output",
            str(json_output),
            "--markdown-output",
            str(markdown_output),
        ]
    )

    assert result == 0
    assert '"verified_hkcfa": true' in json_output.read_text(encoding="utf-8")
    assert "Five Required Questions" in markdown_output.read_text(encoding="utf-8")


def test_cfa_cli_returns_two_for_unverified_input(tmp_path: Path) -> None:
    source = tmp_path / "district-court.txt"
    source.write_text("IN THE DISTRICT COURT\n[2025] HKDC 12\n1. Reasons.", encoding="utf-8")

    assert main(["cfa", "analyze", str(source)]) == 2


def test_representation_compare_cli_writes_reports(tmp_path: Path) -> None:
    json_output = tmp_path / "representation.json"
    markdown_output = tmp_path / "representation.md"
    fixtures = Path(__file__).parent / "fixtures"

    result = main(
        [
            "representation",
            "compare",
            str(fixtures / "cause_list.csv"),
            str(fixtures / "judgment_representations.csv"),
            "--minimum-case-count",
            "3",
            "--json-output",
            str(json_output),
            "--markdown-output",
            str(markdown_output),
        ]
    )

    assert result == 0
    assert '"minimum_case_count": 3' in json_output.read_text(encoding="utf-8")
    assert "Legal Representation Evidence Map" in markdown_output.read_text(encoding="utf-8")
