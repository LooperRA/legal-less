"""Evidence mapper for cause-list appearances and final-judgment representation data.

The module intentionally contains no web crawler.  It consumes operator-provided CSV
exports or individual judgment files, preserves provenance, and reports descriptive
patterns without inferring negligence, misconduct, causation, or case quality.
"""

from __future__ import annotations

import csv
import io
import json
import re
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import asdict, dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from .cfa import text_from_document
from .provenance import Provenance, build_provenance, digest_text

GENERIC_CASE_NUMBER_RE = re.compile(
    r"\b(?P<code>[A-Z]{2,6})\s*(?:NO\.?\s*)?(?P<number>\d{1,7})\s*"
    r"(?:/|OF\s+)(?P<year>\d{2,4})\b",
    re.I,
)
GENERIC_NEUTRAL_CITATION_RE = re.compile(
    r"\[(?P<year>\d{4})\]\s*(?P<court>HK[A-Z]{2,8})\s*(?P<number>\d+)",
    re.I,
)
REPRESENTATION_PATTERNS = (
    re.compile(
        r"instructed\s+by\s+(?P<firm>[^,;\n]{2,160}?),?\s+for\s+(?P<side>[^.;\n]{2,180})",
        re.I,
    ),
    re.compile(
        r"(?P<firm>[^,;\n]{2,160}?(?:Solicitors|Law Offices|Law Firm|Legal|LLP|&\s*Co\.?|and\s+Co\.?))"
        r",?\s+for\s+(?P<side>[^.;\n]{2,180})",
        re.I,
    ),
)
PLACEHOLDER_FIRM_RE = re.compile(
    r"^(?:A\s+Firm|Firm\s+[A-Z]|An?\s+Firm|Solicitors?\s+[A-Z]|[A-Z]\s*&\s*[A-Z])$",
    re.I,
)
STATUS_RULES = (
    ("suspended", re.compile(r"\bsuspend(?:ed|ed by order|ed until)?\b", re.I)),
    ("stayed", re.compile(r"\bstay(?:ed)?\b", re.I)),
    ("adjourned", re.compile(r"\badjourn(?:ed|ment)?\b", re.I)),
    ("vacated", re.compile(r"\bvacat(?:ed|ion)\b", re.I)),
    ("rescheduled", re.compile(r"\b(?:reschedul(?:ed|ing)|relisted)\b", re.I)),
    ("withdrawn", re.compile(r"\bwithdrawn?\b", re.I)),
    ("heard", re.compile(r"\b(?:heard|hearing completed)\b", re.I)),
    ("listed", re.compile(r"\b(?:listed|scheduled|fixed)\b", re.I)),
)
NON_SUBSTANTIVE_EVENT_STATUSES = {
    "suspended",
    "stayed",
    "adjourned",
    "vacated",
    "rescheduled",
    "withdrawn",
}
RELATIONSHIP_VALUES = {"not_applicable", "former_client", "current_client", "unknown"}
FIRM_ROLE_VALUES = {"representative", "party"}


class InputValidationError(ValueError):
    """Raised when an operator-provided import lacks required evidence fields."""


@dataclass(slots=True)
class CauseListRecord:
    hearing_date: str
    court: str
    case_number: str
    case_name: str
    hearing_type: str
    event_status: str
    firm_name: str
    firm_key: str
    represented_side: str
    source_url: str
    retrieved_at: str
    notes: str = ""
    is_anonymized_firm: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class JudgmentRepresentation:
    judgment_date: str
    court: str
    case_number: str
    neutral_citation: str
    case_name: str
    outcome: str
    firm_name: str
    firm_key: str
    represented_side: str
    firm_role: str
    relationship_to_firm: str
    relationship_evidence: str
    source_url: str
    retrieved_at: str
    source_reference: str
    is_anonymized_firm: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class FirmMetrics:
    firm_key: str
    display_name: str
    is_anonymized_firm: bool
    cause_list_appearances: int
    unique_cause_list_cases: int
    suspended_events: int
    non_substantive_events: int
    final_judgment_links: int
    matched_cases: int
    unmatched_cause_list_cases: int
    named_as_party_cases: int
    verified_client_origin_claims: int
    rate_eligible: bool
    suspended_event_rate: float | None
    evidence_case_numbers: list[str]
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class RepresentationAnalysis:
    cause_list_provenance: Provenance
    judgment_provenance: Provenance
    metrics: list[FirmMetrics]
    exact_matches: list[dict[str, Any]]
    unmatched_records: list[dict[str, Any]]
    warnings: list[str]
    minimum_case_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "cause_list_provenance": self.cause_list_provenance.to_dict(),
            "judgment_provenance": self.judgment_provenance.to_dict(),
            "minimum_case_count": self.minimum_case_count,
            "metrics": [item.to_dict() for item in self.metrics],
            "exact_matches": self.exact_matches,
            "unmatched_records": self.unmatched_records,
            "warnings": self.warnings,
        }

    def to_json(self, *, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)


def canonical_case_number(value: str) -> str:
    """Normalize one Hong Kong case number without guessing a missing court or year."""

    match = GENERIC_CASE_NUMBER_RE.search(value.upper())
    if not match:
        return re.sub(r"[^A-Z0-9/]", "", value.upper())
    return f"{match.group('code').upper()}{int(match.group('number'))}/{match.group('year')}"


def canonical_firm_name(value: str, *, case_number: str = "") -> tuple[str, bool]:
    """Normalize a firm name and isolate court-anonymized placeholders by case."""

    cleaned = re.sub(r"\s+", " ", value).strip(" ,.;:|")
    cleaned = re.sub(r"^(?:Messrs?\.?|Solicitors?:)\s+", "", cleaned, flags=re.I)
    cleaned = re.sub(r"\s*\((?:a firm|solicitors?)\)\s*$", "", cleaned, flags=re.I)
    anonymized = bool(PLACEHOLDER_FIRM_RE.fullmatch(cleaned))
    normalized = re.sub(r"[^A-Z0-9&]", "", cleaned.upper())
    if anonymized:
        scope = canonical_case_number(case_number) or digest_text(cleaned)[:12]
        return f"ANON:{normalized}:{scope}", True
    return normalized, False


def canonical_status(value: str) -> str:
    """Map descriptive event text to a non-causal status label."""

    for status, pattern in STATUS_RULES:
        if pattern.search(value):
            return status
    return "unknown"


def _required(row: dict[str, str], field_name: str, row_number: int) -> str:
    value = (row.get(field_name) or "").strip()
    if not value:
        raise InputValidationError(f"Row {row_number}: required field '{field_name}' is empty")
    return value


def _validate_iso_date(value: str, field_name: str, row_number: int) -> str:
    try:
        date.fromisoformat(value)
    except ValueError as exc:
        raise InputValidationError(
            f"Row {row_number}: field '{field_name}' must use YYYY-MM-DD"
        ) from exc
    return value


def load_cause_list_csv(raw: str) -> list[CauseListRecord]:
    """Load an operator-provided, one-firm-per-row cause-list CSV."""

    reader = csv.DictReader(io.StringIO(raw))
    required_headers = {
        "hearing_date",
        "court",
        "case_number",
        "case_name",
        "hearing_type",
        "event_status",
        "firm_name",
        "represented_side",
        "source_url",
        "retrieved_at",
    }
    missing = required_headers - set(reader.fieldnames or [])
    if missing:
        raise InputValidationError(f"Cause-list CSV missing headers: {', '.join(sorted(missing))}")

    records: list[CauseListRecord] = []
    for row_number, row in enumerate(reader, start=2):
        hearing_date = _validate_iso_date(
            _required(row, "hearing_date", row_number), "hearing_date", row_number
        )
        case_number = canonical_case_number(_required(row, "case_number", row_number))
        if not case_number:
            raise InputValidationError(f"Row {row_number}: case_number could not be normalized")
        firm_name = _required(row, "firm_name", row_number)
        firm_key, anonymized = canonical_firm_name(firm_name, case_number=case_number)
        status_text = _required(row, "event_status", row_number)
        records.append(
            CauseListRecord(
                hearing_date=hearing_date,
                court=_required(row, "court", row_number),
                case_number=case_number,
                case_name=_required(row, "case_name", row_number),
                hearing_type=_required(row, "hearing_type", row_number),
                event_status=canonical_status(status_text),
                firm_name=firm_name,
                firm_key=firm_key,
                represented_side=_required(row, "represented_side", row_number),
                source_url=_required(row, "source_url", row_number),
                retrieved_at=_required(row, "retrieved_at", row_number),
                notes=(row.get("notes") or "").strip(),
                is_anonymized_firm=anonymized,
            )
        )
    return records


def load_judgment_csv(raw: str) -> list[JudgmentRepresentation]:
    """Load verified judgment representations and optional firm-as-party evidence."""

    reader = csv.DictReader(io.StringIO(raw))
    required_headers = {
        "judgment_date",
        "court",
        "case_number",
        "neutral_citation",
        "case_name",
        "outcome",
        "firm_name",
        "represented_side",
        "firm_role",
        "relationship_to_firm",
        "relationship_evidence",
        "source_url",
        "retrieved_at",
        "source_reference",
    }
    missing = required_headers - set(reader.fieldnames or [])
    if missing:
        raise InputValidationError(f"Judgment CSV missing headers: {', '.join(sorted(missing))}")

    records: list[JudgmentRepresentation] = []
    for row_number, row in enumerate(reader, start=2):
        judgment_date = _validate_iso_date(
            _required(row, "judgment_date", row_number), "judgment_date", row_number
        )
        case_number = canonical_case_number(_required(row, "case_number", row_number))
        firm_name = _required(row, "firm_name", row_number)
        firm_key, anonymized = canonical_firm_name(firm_name, case_number=case_number)
        firm_role = _required(row, "firm_role", row_number).lower()
        relationship = _required(row, "relationship_to_firm", row_number).lower()
        if firm_role not in FIRM_ROLE_VALUES:
            raise InputValidationError(
                f"Row {row_number}: firm_role must be one of {sorted(FIRM_ROLE_VALUES)}"
            )
        if relationship not in RELATIONSHIP_VALUES:
            raise InputValidationError(
                f"Row {row_number}: relationship_to_firm must be one of {sorted(RELATIONSHIP_VALUES)}"
            )
        relationship_evidence = (row.get("relationship_evidence") or "").strip()
        if relationship in {"former_client", "current_client"} and not relationship_evidence:
            raise InputValidationError(
                f"Row {row_number}: verified client relationship requires relationship_evidence"
            )
        records.append(
            JudgmentRepresentation(
                judgment_date=judgment_date,
                court=_required(row, "court", row_number),
                case_number=case_number,
                neutral_citation=_required(row, "neutral_citation", row_number),
                case_name=_required(row, "case_name", row_number),
                outcome=_required(row, "outcome", row_number),
                firm_name=firm_name,
                firm_key=firm_key,
                represented_side=_required(row, "represented_side", row_number),
                firm_role=firm_role,
                relationship_to_firm=relationship,
                relationship_evidence=relationship_evidence,
                source_url=_required(row, "source_url", row_number),
                retrieved_at=_required(row, "retrieved_at", row_number),
                source_reference=_required(row, "source_reference", row_number),
                is_anonymized_firm=anonymized,
            )
        )
    return records


def _generic_judgment_metadata(text: str) -> tuple[list[str], str, str]:
    case_numbers: list[str] = []
    for match in GENERIC_CASE_NUMBER_RE.finditer(text[:16000]):
        value = canonical_case_number(match.group(0))
        if value and value not in case_numbers:
            case_numbers.append(value)
    citation_match = GENERIC_NEUTRAL_CITATION_RE.search(text[:16000])
    citation = ""
    court = "Unverified court"
    if citation_match:
        citation = (
            f"[{citation_match.group('year')}] {citation_match.group('court').upper()} "
            f"{int(citation_match.group('number'))}"
        )
        court = citation_match.group("court").upper()
    return case_numbers, citation, court


def extract_judgment_representations(
    raw: str,
    *,
    judgment_date: str,
    source_url: str,
    retrieved_at: str,
    case_name: str = "",
    outcome: str = "Not supplied",
) -> list[JudgmentRepresentation]:
    """Extract firm/side lines from one locally supplied final judgment.

    The extractor creates representative records only.  It never infers that a firm is
    a party or that a litigant is a current or former client; those fields require a
    reviewed CSV record with explicit evidence.
    """

    _validate_iso_date(judgment_date, "judgment_date", 1)
    text = text_from_document(raw)
    case_numbers, citation, court = _generic_judgment_metadata(text)
    if not case_numbers:
        raise InputValidationError("No case number was found in the judgment front matter")
    if not citation:
        raise InputValidationError("No Hong Kong neutral citation was found in the judgment")

    records: list[JudgmentRepresentation] = []
    lines = text.splitlines()
    for line_number, line in enumerate(lines, start=1):
        for pattern in REPRESENTATION_PATTERNS:
            match = pattern.search(line)
            if not match:
                continue
            firm_name = re.sub(r"\s+", " ", match.group("firm")).strip(" ,.;")
            represented_side = re.sub(r"\s+", " ", match.group("side")).strip(" ,.;")
            if len(firm_name) < 2 or len(represented_side) < 2:
                continue
            for case_number in case_numbers:
                firm_key, anonymized = canonical_firm_name(firm_name, case_number=case_number)
                record = JudgmentRepresentation(
                    judgment_date=judgment_date,
                    court=court,
                    case_number=case_number,
                    neutral_citation=citation,
                    case_name=case_name or "Not supplied",
                    outcome=outcome,
                    firm_name=firm_name,
                    firm_key=firm_key,
                    represented_side=represented_side,
                    firm_role="representative",
                    relationship_to_firm="not_applicable",
                    relationship_evidence="",
                    source_url=source_url,
                    retrieved_at=retrieved_at,
                    source_reference=f"line {line_number}",
                    is_anonymized_firm=anonymized,
                )
                if not any(
                    existing.case_number == record.case_number
                    and existing.firm_key == record.firm_key
                    and existing.represented_side == record.represented_side
                    for existing in records
                ):
                    records.append(record)
            break
    return records


def judgment_records_to_csv(records: Iterable[JudgmentRepresentation]) -> str:
    """Serialize extracted records in the reviewed-import schema."""

    fields = [
        "judgment_date",
        "court",
        "case_number",
        "neutral_citation",
        "case_name",
        "outcome",
        "firm_name",
        "represented_side",
        "firm_role",
        "relationship_to_firm",
        "relationship_evidence",
        "source_url",
        "retrieved_at",
        "source_reference",
    ]
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for record in records:
        data = record.to_dict()
        writer.writerow({field_name: data[field_name] for field_name in fields})
    return output.getvalue()


def compare_representation_records(
    cause_records: list[CauseListRecord],
    judgment_records: list[JudgmentRepresentation],
    *,
    cause_raw: str,
    judgment_raw: str,
    cause_source_description: str,
    judgment_source_description: str,
    minimum_case_count: int = 5,
) -> RepresentationAnalysis:
    """Compare exact case-number and firm matches, then calculate descriptive metrics."""

    if minimum_case_count < 2:
        raise InputValidationError("minimum_case_count must be at least 2")

    judgment_index: dict[tuple[str, str], list[JudgmentRepresentation]] = defaultdict(list)
    case_judgment_index: dict[str, list[JudgmentRepresentation]] = defaultdict(list)
    for record in judgment_records:
        judgment_index[(record.case_number, record.firm_key)].append(record)
        case_judgment_index[record.case_number].append(record)

    cause_by_firm: dict[str, list[CauseListRecord]] = defaultdict(list)
    judgments_by_firm: dict[str, list[JudgmentRepresentation]] = defaultdict(list)
    exact_matches: list[dict[str, Any]] = []
    unmatched_records: list[dict[str, Any]] = []
    for record in cause_records:
        cause_by_firm[record.firm_key].append(record)
        matched = judgment_index.get((record.case_number, record.firm_key), [])
        if matched:
            for judgment in matched:
                exact_matches.append(
                    {
                        "case_number": record.case_number,
                        "firm_key": record.firm_key,
                        "firm_name": record.firm_name,
                        "cause_source_url": record.source_url,
                        "judgment_source_url": judgment.source_url,
                        "judgment_reference": judgment.source_reference,
                        "match_basis": "exact canonical case number + exact canonical firm name",
                    }
                )
        else:
            reason = (
                "case found but firm not confirmed in final judgment"
                if case_judgment_index.get(record.case_number)
                else "no final-judgment record for exact case number"
            )
            unmatched_records.append(
                {
                    "case_number": record.case_number,
                    "firm_key": record.firm_key,
                    "firm_name": record.firm_name,
                    "reason": reason,
                    "source_url": record.source_url,
                }
            )

    for record in judgment_records:
        judgments_by_firm[record.firm_key].append(record)

    metrics: list[FirmMetrics] = []
    all_firm_keys = sorted(set(cause_by_firm) | set(judgments_by_firm))
    for firm_key in all_firm_keys:
        cause_rows = cause_by_firm.get(firm_key, [])
        judgment_rows = judgments_by_firm.get(firm_key, [])
        display_name = cause_rows[0].firm_name if cause_rows else judgment_rows[0].firm_name
        anonymized = bool(
            (cause_rows and cause_rows[0].is_anonymized_firm)
            or (judgment_rows and judgment_rows[0].is_anonymized_firm)
        )
        unique_cases = sorted({record.case_number for record in cause_rows})
        matched_cases = sorted(
            {
                record.case_number
                for record in cause_rows
                if judgment_index.get((record.case_number, firm_key))
            }
        )
        suspended_events = sum(record.event_status == "suspended" for record in cause_rows)
        non_substantive_events = sum(
            record.event_status in NON_SUBSTANTIVE_EVENT_STATUSES for record in cause_rows
        )
        named_as_party_cases = len(
            {record.case_number for record in judgment_rows if record.firm_role == "party"}
        )
        verified_client_origin_claims = len(
            {
                record.case_number
                for record in judgment_rows
                if record.firm_role == "party"
                and record.relationship_to_firm in {"former_client", "current_client"}
                and record.relationship_evidence
            }
        )
        rate_eligible = len(unique_cases) >= minimum_case_count and not anonymized
        warnings: list[str] = []
        if not rate_eligible:
            warnings.append(
                "Rate suppressed because the minimum distinct-case threshold was not met or the firm name is anonymized."
            )
        if anonymized:
            warnings.append(
                "Court placeholder is isolated to its case and must not be resolved or aggregated across cases."
            )
        metrics.append(
            FirmMetrics(
                firm_key=firm_key,
                display_name=display_name,
                is_anonymized_firm=anonymized,
                cause_list_appearances=len(cause_rows),
                unique_cause_list_cases=len(unique_cases),
                suspended_events=suspended_events,
                non_substantive_events=non_substantive_events,
                final_judgment_links=len(
                    {
                        (match["case_number"], match["firm_key"])
                        for match in exact_matches
                        if match["firm_key"] == firm_key
                    }
                ),
                matched_cases=len(matched_cases),
                unmatched_cause_list_cases=len(set(unique_cases) - set(matched_cases)),
                named_as_party_cases=named_as_party_cases,
                verified_client_origin_claims=verified_client_origin_claims,
                rate_eligible=rate_eligible,
                suspended_event_rate=(
                    round(suspended_events / len(cause_rows), 4)
                    if rate_eligible and cause_rows
                    else None
                ),
                evidence_case_numbers=sorted(
                    set(unique_cases) | {record.case_number for record in judgment_rows}
                ),
                warnings=warnings,
            )
        )

    metrics.sort(
        key=lambda item: (
            item.is_anonymized_firm,
            -item.unique_cause_list_cases,
            -item.final_judgment_links,
            item.display_name.casefold(),
        )
    )
    warnings = [
        "Descriptive event counts do not establish causation, fault, misconduct, or service quality.",
        "Cause-list status is not a final case outcome; final judgments are linked only by exact case number and firm name.",
        "Client-origin claims are counted only when an operator records the relationship and cites explicit evidence.",
        "Names of individual practitioners are outside the aggregation model.",
    ]
    cause_provenance = build_provenance(
        cause_raw,
        source_description=cause_source_description,
        warnings=warnings,
    )
    judgment_provenance = build_provenance(
        judgment_raw,
        source_description=judgment_source_description,
        warnings=warnings,
    )
    return RepresentationAnalysis(
        cause_list_provenance=cause_provenance,
        judgment_provenance=judgment_provenance,
        metrics=metrics,
        exact_matches=exact_matches,
        unmatched_records=unmatched_records,
        warnings=warnings,
        minimum_case_count=minimum_case_count,
    )


def render_representation_markdown(analysis: RepresentationAnalysis) -> str:
    """Render a non-causal, evidence-linked comparison report."""

    lines = [
        "# Legal Representation Evidence Map",
        "",
        "> This report describes public-record event patterns. It does not allege or infer fault, misconduct, competence, causation, or case quality.",
        "",
        "## Method",
        "",
        f"Rates require at least **{analysis.minimum_case_count} distinct cause-list cases** and are suppressed for anonymized firm placeholders. Cause-list and judgment records are confirmed only by an exact canonical case-number and firm-name match.",
        "",
        "## Firm-Level Descriptive Metrics",
        "",
        "| Firm | Distinct listed cases | Suspended events | Other non-substantive events | Final-judgment links | Firm named as party | Verified client-origin claims | Suspended-event rate |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for item in analysis.metrics:
        rate = (
            f"{item.suspended_event_rate:.1%}"
            if item.suspended_event_rate is not None
            else "Suppressed"
        )
        name = (
            f"{item.display_name} (anonymized placeholder)"
            if item.is_anonymized_firm
            else item.display_name
        )
        lines.append(
            f"| {name} | {item.unique_cause_list_cases} | {item.suspended_events} | "
            f"{item.non_substantive_events - item.suspended_events} | {item.final_judgment_links} | "
            f"{item.named_as_party_cases} | {item.verified_client_origin_claims} | {rate} |"
        )

    lines.extend(["", "## Exact Evidence Links", ""])
    if not analysis.exact_matches:
        lines.append("No exact case-number and firm-name links were confirmed.")
    else:
        lines.extend(
            [
                "| Case number | Firm | Match basis | Cause-list source | Judgment source |",
                "|---|---|---|---|---|",
            ]
        )
        for match in analysis.exact_matches:
            lines.append(
                f"| {match['case_number']} | {match['firm_name']} | {match['match_basis']} | "
                f"{match['cause_source_url']} | {match['judgment_source_url']} |"
            )

    lines.extend(["", "## Mandatory Interpretation Warnings", ""])
    lines.extend(f"- {warning}" for warning in analysis.warnings)
    lines.extend(
        [
            "",
            "## Provenance",
            "",
            "| Input | SHA-256 | Description |",
            "|---|---|---|",
            f"| Cause-list import | `{analysis.cause_list_provenance.sha256}` | {analysis.cause_list_provenance.source_description} |",
            f"| Judgment import | `{analysis.judgment_provenance.sha256}` | {analysis.judgment_provenance.source_description} |",
            "",
        ]
    )
    return "\n".join(lines)


def compare_csv_files(
    cause_csv_path: str | Path,
    judgment_csv_path: str | Path,
    *,
    minimum_case_count: int = 5,
) -> RepresentationAnalysis:
    cause_path = Path(cause_csv_path)
    judgment_path = Path(judgment_csv_path)
    cause_raw = cause_path.read_text(encoding="utf-8-sig")
    judgment_raw = judgment_path.read_text(encoding="utf-8-sig")
    return compare_representation_records(
        load_cause_list_csv(cause_raw),
        load_judgment_csv(judgment_raw),
        cause_raw=cause_raw,
        judgment_raw=judgment_raw,
        cause_source_description=str(cause_path),
        judgment_source_description=str(judgment_path),
        minimum_case_count=minimum_case_count,
    )
