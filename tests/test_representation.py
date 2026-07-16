from pathlib import Path

import pytest

from legalless.representation import (
    InputValidationError,
    canonical_case_number,
    canonical_firm_name,
    compare_csv_files,
    extract_judgment_representations,
    load_judgment_csv,
    render_representation_markdown,
)

FIXTURES = Path(__file__).parent / "fixtures"


def test_normalizes_hong_kong_case_numbers() -> None:
    assert canonical_case_number("FACV No. 12 of 2025") == "FACV12/2025"
    assert canonical_case_number(" hca 9 / 24 ") == "HCA9/24"


def test_anonymized_firm_keys_are_case_scoped() -> None:
    first_key, first_anonymized = canonical_firm_name("A Firm", case_number="FACV1/2025")
    second_key, second_anonymized = canonical_firm_name("A Firm", case_number="FACV2/2025")

    assert first_anonymized is True
    assert second_anonymized is True
    assert first_key != second_key


def test_compares_exact_links_and_suppresses_small_or_anonymous_rates() -> None:
    analysis = compare_csv_files(
        FIXTURES / "cause_list.csv",
        FIXTURES / "judgment_representations.csv",
        minimum_case_count=3,
    )

    harbor = next(item for item in analysis.metrics if item.display_name == "Harbor & Co.")
    assert harbor.unique_cause_list_cases == 3
    assert harbor.suspended_events == 1
    assert harbor.non_substantive_events == 2
    assert harbor.final_judgment_links == 2
    assert harbor.named_as_party_cases == 1
    assert harbor.verified_client_origin_claims == 1
    assert harbor.rate_eligible is True
    assert harbor.suspended_event_rate == 0.25

    anonymous = [item for item in analysis.metrics if item.display_name == "A Firm"]
    assert len(anonymous) == 2
    assert all(item.rate_eligible is False for item in anonymous)
    assert all(item.suspended_event_rate is None for item in anonymous)
    assert all(item.is_anonymized_firm is True for item in anonymous)


def test_report_carries_evidence_and_non_causal_warning() -> None:
    analysis = compare_csv_files(
        FIXTURES / "cause_list.csv",
        FIXTURES / "judgment_representations.csv",
        minimum_case_count=3,
    )
    report = render_representation_markdown(analysis)

    assert "Legal Representation Evidence Map" in report
    assert "does not allege or infer fault" in report
    assert "exact canonical case number + exact canonical firm name" in report
    assert "https://example.test/judgment/1" in report
    assert "SHA-256" in report


def test_client_relationship_requires_explicit_evidence() -> None:
    raw = (FIXTURES / "judgment_representations.csv").read_text(encoding="utf-8")
    invalid = raw.replace(
        "Paragraph 4 expressly identifies Gamma as the firm's former client",
        "",
    )

    with pytest.raises(InputValidationError, match="requires relationship_evidence"):
        load_judgment_csv(invalid)


def test_extracts_representative_from_local_judgment() -> None:
    raw = """
    IN THE COURT OF FINAL APPEAL
    FACV 7/2025
    [2025] HKCFA 93
    Omega v Sigma
    Ms Example SC, instructed by Harbor & Co., for the Appellant.
    """
    records = extract_judgment_representations(
        raw,
        judgment_date="2025-06-10",
        source_url="https://example.test/judgment/7",
        retrieved_at="2025-06-10T10:00:00Z",
        case_name="Omega v Sigma",
        outcome="Appeal allowed",
    )

    assert len(records) == 1
    assert records[0].case_number == "FACV7/2025"
    assert records[0].firm_name == "Harbor & Co"
    assert records[0].represented_side == "the Appellant"
    assert records[0].firm_role == "representative"
    assert records[0].relationship_to_firm == "not_applicable"
