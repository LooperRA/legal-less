from pathlib import Path

from legalless.cfa import analyze_cfa_document, analyze_cfa_file, render_cfa_markdown

FIXTURE = Path(__file__).parent / "fixtures" / "synthetic_hkcfa.txt"


def test_extracts_hkcfa_metadata_and_five_questions() -> None:
    analysis = analyze_cfa_file(FIXTURE, source_url="https://example.test/judgment")

    assert analysis.verified_hkcfa is True
    assert analysis.neutral_citation == "[2025] HKCFA 99"
    assert analysis.action_numbers == ["FACV9/2025"]
    assert analysis.case_name == "ALPHA PROPERTY LIMITED v. BETA OWNERS CORPORATION"
    assert analysis.paragraphs_indexed == 5
    assert analysis.questions["1_where_heard"]["answer"] == "Hong Kong Court of Final Appeal"
    assert "whether a registered owner" in analysis.questions["3_dispute"]["answer"]
    assert "shall pay the costs" in analysis.questions["4_costs"]["answer"]


def test_equation_requires_position_and_reasoning() -> None:
    analysis = analyze_cfa_file(FIXTURE)

    assert analysis.ratio_candidates
    top = analysis.ratio_candidates[0]
    assert top.position_score > 0
    assert top.reasoning_score > 0
    assert top.total_score > 0
    assert top.court_position.reference in {"3", "4", "5"}
    assert top.legal_reasoning.reference in {"3", "4", "5"}


def test_submissions_and_lower_court_language_are_penalized() -> None:
    analysis = analyze_cfa_file(FIXTURE)
    paragraph_two_candidates = [
        candidate
        for candidate in analysis.ratio_candidates
        if candidate.court_position.reference == "2" or candidate.legal_reasoning.reference == "2"
    ]

    assert not paragraph_two_candidates or all(
        candidate.penalty > 0 for candidate in paragraph_two_candidates
    )


def test_markdown_report_is_traceable() -> None:
    analysis = analyze_cfa_file(FIXTURE, source_url="https://example.test/judgment")
    report = render_cfa_markdown(analysis)

    assert "# HKCFA Ratio Decidendi Locator Report" in report
    assert "Court position + legal reasoning" in report
    assert "https://example.test/judgment" in report
    assert "SHA-256" in report
    assert "Five Required Questions" in report


def test_out_of_scope_document_is_not_verified() -> None:
    analysis = analyze_cfa_document(
        "IN THE DISTRICT COURT\n[2025] HKDC 12\n1. This case concerns a contract."
    )

    assert analysis.verified_hkcfa is False
    assert analysis.questions["1_where_heard"]["answer"] == "Not verified"
    assert any("out of scope" in warning for warning in analysis.warnings)
