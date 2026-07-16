"""Hong Kong Court of Final Appeal ratio decidendi locator.

The module implements the repository's equation as transparent features:

    court position + legal reasoning = ratio decidendi candidate

Candidates are ranked, not declared authoritative.  Every answer carries source text
and a paragraph reference so a lawyer or researcher can review the result.
"""

from __future__ import annotations

import html
import json
import re
from collections.abc import Iterable
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup

from .provenance import Provenance, build_provenance

NEUTRAL_CITATION_RE = re.compile(r"\[(?P<year>\d{4})\]\s*HKCFA\s*(?P<number>\d+)", re.I)
ACTION_NUMBER_RE = re.compile(
    r"\b(?P<code>FACV|FACC|FAMV|FAMC)\s*(?:NO\.?\s*)?(?P<number>\d{1,6})"
    r"\s*(?:/|OF\s+)(?P<year>\d{4})\b",
    re.I,
)
FINAL_APPEAL_HEADING_RE = re.compile(
    r"\bFINAL\s+APPEAL\s+(?:NO\.?\s*)?(?P<number>\d{1,6})\s+OF\s+"
    r"(?P<year>\d{4})\s*\((?P<division>CIVIL|CRIMINAL)\)",
    re.I,
)
PARAGRAPH_RE = re.compile(
    r"^\s*(?:\[(?P<bracket>\d{1,4})\]|(?P<plain>\d{1,4})\s*(?:\\?\.|\.))\s*(?P<body>.*)$"
)
STANDALONE_PARAGRAPH_RE = re.compile(r"^\s*\[?(?P<number>\d{1,4})\]?\s*$")
JUDGMENT_BOUNDARY_RE = re.compile(r"(?im)^\s*(?:JUDGMENT|J\s+U\s+D\s+G\s+M\s+E\s+N\s+T)\s*$")
SIGNATURE_RE = re.compile(r"^\([A-Z][A-Za-z .'-]{1,80}\)$")
PARTY_WITH_CAPACITY_RE = re.compile(
    r"^(?P<name>.+?)\s+(?P<capacity>(?:\d+\s*(?:st|nd|rd|th)\s+)?"
    r"(?:Plaintiff|Defendant|Applicant|Appellant|Respondent|Petitioner|Prosecution))$",
    re.I,
)
PARENTHETICAL_ROLE_RE = re.compile(
    r"^\((?P<role>(?:\d+\s*(?:st|nd|rd|th)\s+)?"
    r"(?:Appellant|Respondent|Applicant|Plaintiff|Defendant|Petitioner)[^)]*)\)$",
    re.I,
)
SAME_LINE_PARTY_RE = re.compile(
    r"^(?P<name>.+?)\s*\((?P<role>(?:\d+\s*(?:st|nd|rd|th)\s+)?"
    r"(?:Appellant|Respondent|Applicant|Plaintiff|Defendant|Petitioner)[^)]*)\)$",
    re.I,
)

ISSUE_PATTERNS = (
    (re.compile(r"\bthis appeal (?:raises|concerns|involves)\b", re.I), 5),
    (re.compile(r"\bat issue\b", re.I), 5),
    (re.compile(r"\bquestion(?:s)? of law\b", re.I), 4),
    (
        re.compile(
            r"\bthe (?:central|principal|main|first|second|third) (?:issue|question)\b", re.I
        ),
        4,
    ),
    (re.compile(r"\bthe issues?\b", re.I), 2),
    (re.compile(r"\bwhether\b", re.I), 1),
)

POSITION_PATTERNS = (
    (
        re.compile(
            r"\bwe (?:hold|conclude|consider|find|accept|reject|agree|do not accept)\b", re.I
        ),
        5,
    ),
    (re.compile(r"\bthe court (?:holds|concludes|finds|therefore|unanimously)\b", re.I), 5),
    (re.compile(r"\b(?:i|we) would (?:allow|dismiss|answer|hold|conclude|order)\b", re.I), 4),
    (re.compile(r"\bshould be (?:allowed|dismissed|answered|varied|set aside)\b", re.I), 4),
    (re.compile(r"\bthe proper (?:approach|construction|test|principle)\b", re.I), 4),
    (re.compile(r"\bwe are not satisfied\b", re.I), 4),
    (re.compile(r"\bit is (?:clear|necessary|established|not open) that\b", re.I), 2),
)

SUBSTANTIVE_REASONING_PATTERNS = (
    (re.compile(r"\bfor (?:these|those|the following) reasons\b", re.I), 1),
    (re.compile(r"\b(?:because|since|the reason is)\b", re.I), 1),
    (
        re.compile(
            r"\b(?:principle|authority|statutory|common law|ordinance|section|construction)\b",
            re.I,
        ),
        1,
    ),
)

REASONING_PATTERNS = (
    (re.compile(r"\bfor (?:these|those|the following) reasons\b", re.I), 4),
    (re.compile(r"\b(?:because|since)\b", re.I), 3),
    (re.compile(r"\b(?:therefore|accordingly|consequently|it follows that)\b", re.I), 3),
    (re.compile(r"\bthe reason is\b", re.I), 3),
    (re.compile(r"\bin (?:applying|construing|interpreting)\b", re.I), 2),
    (re.compile(r"\b(?:principle|authority|statutory|common law|ordinance|section)\b", re.I), 1),
)

NECESSITY_PATTERNS = (
    (re.compile(r"\b(?:dispositive|determinative|necessary to decide)\b", re.I), 3),
    (re.compile(r"\b(?:allow|dismiss|set aside|vary|answer) the appeal\b", re.I), 3),
    (re.compile(r"\b(?:order|relief|remedy|liability|jurisdiction)\b", re.I), 1),
)

APPLICATION_PATTERNS = (
    (re.compile(r"\bin (?:this|the present) case\b", re.I), 3),
    (re.compile(r"\bon the (?:facts|evidence)\b", re.I), 3),
    (re.compile(r"\bappl(?:y|ied|ies|ying)\b", re.I), 2),
    (re.compile(r"\btherefore|accordingly|it follows\b", re.I), 2),
)

ARGUMENT_PATTERNS = (
    (
        re.compile(
            r"\b(?:appellant|respondent|applicant|plaintiff|defendant)s? (?:submits?|contends?|argues?)\b",
            re.I,
        ),
        5,
    ),
    (re.compile(r"\bit is (?:submitted|contended|argued)\b", re.I), 4),
    (re.compile(r"\bcounsel (?:submits?|contends?|argues?)\b", re.I), 4),
)

LOWER_COURT_PATTERNS = (
    (re.compile(r"\bthe court of appeal (?:held|concluded|found|rejected|accepted)\b", re.I), 4),
    (
        re.compile(
            r"\bthe (?:judge|master|magistrate|tribunal) (?:held|concluded|found|rejected)\b", re.I
        ),
        3,
    ),
)

OBITER_PATTERNS = (
    (re.compile(r"\b(?:obiter|not necessary to decide|leave open|express no view)\b", re.I), 6),
    (re.compile(r"\b(?:dissent|dissenting)\b", re.I), 5),
    (re.compile(r"\b(?:hypothetically|assuming without deciding)\b", re.I), 3),
)

COST_ORDER_PATTERNS = (
    re.compile(r"\bshall pay (?:the )?costs\b", re.I),
    re.compile(r"\bcosts? (?:of|in) .{0,80}\b(?:paid|borne|taxed|assessed)\b", re.I),
    re.compile(r"\border nisi .{0,100}\bcosts\b", re.I),
    re.compile(r"\bno order (?:for|as to) costs\b", re.I),
    re.compile(r"\bcosts in the cause\b", re.I),
)


@dataclass(slots=True)
class Paragraph:
    reference: str
    text: str
    order: int


@dataclass(slots=True)
class Evidence:
    reference: str
    text: str
    score: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class RatioCandidate:
    court_position: Evidence
    legal_reasoning: Evidence
    application: Evidence | None
    position_score: float
    reasoning_score: float
    necessity_score: float
    penalty: float
    total_score: float
    confidence: float
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "court_position": self.court_position.to_dict(),
            "legal_reasoning": self.legal_reasoning.to_dict(),
            "application": self.application.to_dict() if self.application else None,
            "position_score": self.position_score,
            "reasoning_score": self.reasoning_score,
            "necessity_score": self.necessity_score,
            "penalty": self.penalty,
            "total_score": self.total_score,
            "confidence": self.confidence,
            "warnings": self.warnings,
        }


@dataclass(slots=True)
class CFAAnalysis:
    provenance: Provenance
    verified_hkcfa: bool
    neutral_citation: str | None
    action_numbers: list[str]
    case_name: str | None
    court: str
    judges: list[str]
    parties: list[dict[str, str]]
    questions: dict[str, Any]
    ratio_candidates: list[RatioCandidate]
    paragraphs_indexed: int
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "provenance": self.provenance.to_dict(),
            "verified_hkcfa": self.verified_hkcfa,
            "neutral_citation": self.neutral_citation,
            "action_numbers": self.action_numbers,
            "case_name": self.case_name,
            "court": self.court,
            "judges": self.judges,
            "parties": self.parties,
            "questions": self.questions,
            "ratio_candidates": [candidate.to_dict() for candidate in self.ratio_candidates],
            "paragraphs_indexed": self.paragraphs_indexed,
            "warnings": self.warnings,
        }

    def to_json(self, *, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)


def _clean_inline_markup(value: str) -> str:
    value = html.unescape(value)
    value = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", value)
    value = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", value)
    value = value.replace("**", "").replace("__", "").replace("`", "")
    value = re.sub(r"<[^>]+>", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def text_from_document(raw: str) -> str:
    """Convert HTML, Markdown-like, or plain text input into normalized lines."""

    if re.search(r"<(?:html|body|div|p|table|br)\b", raw, re.I):
        soup = BeautifulSoup(raw, "html.parser")
        for node in soup(["script", "style", "noscript"]):
            node.decompose()
        raw = soup.get_text("\n")
    raw = html.unescape(raw).replace("\r\n", "\n").replace("\r", "\n")
    cleaned_lines: list[str] = []
    blank = False
    for line in raw.splitlines():
        cleaned = _clean_inline_markup(line)
        if cleaned:
            cleaned_lines.append(cleaned)
            blank = False
        elif not blank:
            cleaned_lines.append("")
            blank = True
    return "\n".join(cleaned_lines).strip()


def _judgment_boundary(text: str) -> re.Match[str] | None:
    """Locate the operative judgment heading rather than a navigation/download label."""

    boundaries = list(JUDGMENT_BOUNDARY_RE.finditer(text))
    if not boundaries:
        return None
    between = re.search(r"(?im)^\s*BETWEEN\s*$", text)
    if between:
        return next(
            (boundary for boundary in boundaries if boundary.start() > between.end()),
            boundaries[-1],
        )
    court_heading = re.search(r"\bCOURT OF FINAL APPEAL\b", text, re.I)
    if court_heading:
        return next(
            (boundary for boundary in boundaries if boundary.start() > court_heading.end()),
            boundaries[-1],
        )
    return boundaries[-1]


def _front_matter_text(text: str) -> str:
    """Return the judgment heading and BETWEEN block, excluding substantive reasons."""

    boundary = _judgment_boundary(text)
    if boundary:
        return text[: boundary.start()]
    first_paragraph = re.search(r"(?m)^\s*(?:\[?1\]?|1\.)\s+", text)
    if first_paragraph:
        return text[: first_paragraph.start()]
    return text[:12000]


def _judgment_body_text(text: str) -> str:
    boundary = _judgment_boundary(text)
    return text[boundary.end() :] if boundary else text


def segment_paragraphs(text: str) -> list[Paragraph]:
    """Segment numbered judgment paragraphs while tolerating Markdown and HTML layouts."""

    lines = _judgment_body_text(text).splitlines()
    paragraphs: list[Paragraph] = []
    current_number: str | None = None
    current_lines: list[str] = []

    def flush() -> None:
        nonlocal current_number, current_lines
        if current_number is None:
            current_lines = []
            return
        body = _clean_inline_markup(" ".join(current_lines))
        if body:
            paragraphs.append(Paragraph(reference=current_number, text=body, order=len(paragraphs)))
        current_number = None
        current_lines = []

    index = 0
    while index < len(lines):
        line = lines[index].strip()
        if current_number is not None and SIGNATURE_RE.match(line):
            flush()
            break
        match = PARAGRAPH_RE.match(line)
        if match:
            body = match.group("body").strip()
            if match.group("bracket") and re.match(r"(?:HKCFA|HKCA|HKCFI|HKDC)\b", body, re.I):
                index += 1
                continue
            candidate_number = match.group("bracket") or match.group("plain")
            previous_number = (
                int(current_number)
                if current_number is not None
                else int(paragraphs[-1].reference)
                if paragraphs
                else 0
            )
            if int(candidate_number) <= previous_number:
                if current_number is not None and body:
                    current_lines.append(line)
                index += 1
                continue
            flush()
            current_number = candidate_number
            current_lines = [body] if body else []
            index += 1
            continue

        standalone = STANDALONE_PARAGRAPH_RE.match(line)
        if standalone and index + 1 < len(lines):
            next_line = lines[index + 1].strip()
            previous_number = (
                int(current_number)
                if current_number is not None
                else int(paragraphs[-1].reference)
                if paragraphs
                else 0
            )
            if (
                int(standalone.group("number")) > previous_number
                and next_line
                and not STANDALONE_PARAGRAPH_RE.match(next_line)
            ):
                flush()
                current_number = standalone.group("number")
                current_lines = []
                index += 1
                continue

        if current_number is not None and line:
            current_lines.append(line)
        index += 1

    flush()
    return paragraphs


def _score_patterns(text: str, patterns: Iterable[tuple[re.Pattern[str], int]]) -> float:
    return float(sum(weight for pattern, weight in patterns if pattern.search(text)))


def _extract_neutral_citation(text: str) -> str | None:
    match = NEUTRAL_CITATION_RE.search(_front_matter_text(text))
    if not match:
        return None
    return f"[{match.group('year')}] HKCFA {int(match.group('number'))}"


def _extract_action_numbers(text: str) -> list[str]:
    front_matter = _front_matter_text(text)
    found: list[str] = []
    for match in ACTION_NUMBER_RE.finditer(front_matter):
        canonical = (
            f"{match.group('code').upper()}{int(match.group('number'))}/{match.group('year')}"
        )
        if canonical not in found:
            found.append(canonical)
    for match in FINAL_APPEAL_HEADING_RE.finditer(front_matter):
        code = "FACV" if match.group("division").upper() == "CIVIL" else "FACC"
        canonical = f"{code}{int(match.group('number'))}/{match.group('year')}"
        if canonical not in found:
            found.append(canonical)
    return found


def _front_matter_parties(text: str) -> list[dict[str, str]]:
    lines = [line.strip(" \t|") for line in _front_matter_text(text).splitlines()]
    try:
        start = next(
            index for index, line in enumerate(lines) if line.strip(" :|").upper() == "BETWEEN"
        )
    except StopIteration:
        return []

    block: list[str] = []
    for line in lines[start + 1 :]:
        if re.match(r"^(?:Coram|Before|Date of)", line, re.I):
            break
        if line and not re.fullmatch(r"_+", line):
            block.append(line)

    parties: list[dict[str, str]] = []
    index = 0
    while index < len(block):
        line = block[index]
        if line.lower() == "and":
            index += 1
            continue
        same_line = SAME_LINE_PARTY_RE.match(line)
        if same_line:
            parties.append(
                {
                    "name": _clean_inline_markup(same_line.group("name")),
                    "role": _clean_inline_markup(same_line.group("role")),
                }
            )
            index += 1
            continue

        capacity = PARTY_WITH_CAPACITY_RE.match(line)
        next_role = (
            PARENTHETICAL_ROLE_RE.match(block[index + 1]) if index + 1 < len(block) else None
        )
        if capacity:
            role = _clean_inline_markup(capacity.group("capacity"))
            if next_role:
                role = f"{role}; {_clean_inline_markup(next_role.group('role'))}"
                index += 1
            parties.append({"name": _clean_inline_markup(capacity.group("name")), "role": role})
            index += 1
            continue
        if next_role and len(line) <= 240:
            parties.append(
                {
                    "name": _clean_inline_markup(line),
                    "role": _clean_inline_markup(next_role.group("role")),
                }
            )
            index += 2
            continue
        index += 1

    unique: list[dict[str, str]] = []
    for party in parties:
        if party["name"] and party not in unique:
            unique.append(party)
    return unique[:20]


def _case_name_from_parties(parties: list[dict[str, str]]) -> str | None:
    if not parties:
        return None
    claimants = [
        party["name"]
        for party in parties
        if re.search(
            r"\b(?:Plaintiff|Applicant|Appellant|Petitioner|Prosecution)\b", party["role"], re.I
        )
        and not re.search(r"\bDefendant\b", party["role"], re.I)
    ]
    defendants = [
        party["name"]
        for party in parties
        if re.search(r"\b(?:Defendant|Respondent)\b", party["role"], re.I)
        and not re.search(r"\bPlaintiff\b", party["role"], re.I)
    ]
    if claimants and defendants:
        return f"{' and '.join(claimants)} v. {' and '.join(defendants)}"
    if len(parties) >= 2:
        return f"{parties[0]['name']} v. {parties[1]['name']}"
    return parties[0]["name"]


def _extract_case_name(text: str, parties: list[dict[str, str]]) -> str | None:
    lines = [line.strip() for line in _front_matter_text(text).splitlines() if line.strip()]
    for line in lines:
        if len(line) > 500:
            continue
        if re.search(r"\s+v(?:\.|ersus)?\s+", line, re.I):
            cleaned = re.sub(r"\s+", " ", line).strip(" -|")
            if not re.search(r"\b(?:URL|cited|referred|followed|on appeal from)\b", cleaned, re.I):
                return cleaned
    return _case_name_from_parties(parties)


def _extract_parties(case_name: str | None, text: str) -> list[dict[str, str]]:
    parties = _front_matter_parties(text)
    if parties or not case_name:
        return parties
    split = re.split(r"\s+v(?:\.|ersus)?\s+", case_name, maxsplit=1, flags=re.I)
    if len(split) == 2:
        return [
            {"name": split[0].strip(), "role": "Appellant / Applicant / Plaintiff"},
            {"name": split[1].strip(), "role": "Respondent / Defendant"},
        ]
    return [{"name": case_name, "role": "Role not parsed"}]


def _extract_judges(text: str) -> list[str]:
    judges: list[str] = []
    patterns = (
        re.compile(r"\bCoram\s*:?\s*(.{10,600})", re.I),
        re.compile(r"\bBefore\s*:?\s*(.{10,600})", re.I),
    )
    block = ""
    for pattern in patterns:
        match = pattern.search(text[:10000])
        if match:
            block = match.group(1).split("Date of", 1)[0]
            break
    if not block:
        block = " ".join(text.splitlines()[:120])
    judge_pattern = re.compile(
        r"(?:Chief Justice\s+[A-Z][A-Za-z'-]+|"
        r"(?:Mr|Madam) Justice\s+[A-Z][A-Za-z'-]+(?:\s+(?:PJ|NPJ|CFA))?|"
        r"Lord\s+[A-Z][A-Za-z' -]+?\s+NPJ)",
        re.I,
    )
    for match in judge_pattern.finditer(block):
        judge = re.sub(r"\s+", " ", match.group(0)).strip(" ,;")
        if judge not in judges:
            judges.append(judge)
    return judges


def _best_evidence(
    paragraphs: list[Paragraph], patterns: Iterable[tuple[re.Pattern[str], int]]
) -> Evidence | None:
    ranked: list[Evidence] = []
    for paragraph in paragraphs:
        score = _score_patterns(paragraph.text, patterns)
        if score:
            ranked.append(Evidence(paragraph.reference, paragraph.text, score))
    if not ranked:
        return None
    ranked.sort(key=lambda evidence: (-evidence.score, int(evidence.reference)))
    return ranked[0]


def _costs_evidence(paragraphs: list[Paragraph]) -> Evidence | None:
    ranked: list[Evidence] = []
    total = max(len(paragraphs), 1)
    for paragraph in paragraphs:
        hits = sum(1 for pattern in COST_ORDER_PATTERNS if pattern.search(paragraph.text))
        if not hits:
            continue
        order_words = len(
            re.findall(r"\b(?:order|shall|paid|pay|taxed|agreed|nisi)\b", paragraph.text, re.I)
        )
        recency = paragraph.order / total
        score = hits * 5 + min(order_words, 5) + recency
        ranked.append(Evidence(paragraph.reference, paragraph.text, round(score, 3)))
    if not ranked:
        return None
    ranked.sort(key=lambda evidence: -evidence.score)
    return ranked[0]


def _ratio_candidates(paragraphs: list[Paragraph]) -> list[RatioCandidate]:
    candidates: list[RatioCandidate] = []
    for index, paragraph in enumerate(paragraphs):
        neighbours = [paragraph]
        if index > 0:
            neighbours.insert(0, paragraphs[index - 1])
        if index + 1 < len(paragraphs):
            neighbours.append(paragraphs[index + 1])

        position_options: list[tuple[Paragraph, float]] = []
        reasoning_options: list[tuple[Paragraph, float]] = []
        for neighbour in neighbours:
            position = _score_patterns(neighbour.text, POSITION_PATTERNS)
            reasoning = _score_patterns(neighbour.text, REASONING_PATTERNS)
            if position:
                position_options.append((neighbour, position))
            if reasoning:
                reasoning_options.append((neighbour, reasoning))
        if not position_options or not reasoning_options:
            continue

        position_paragraph, position_score = max(position_options, key=lambda item: item[1])
        reasoning_paragraph, reasoning_score = max(reasoning_options, key=lambda item: item[1])
        combined = f"{position_paragraph.text} {reasoning_paragraph.text}"
        necessity_score = _score_patterns(combined, NECESSITY_PATTERNS)
        application_score = _score_patterns(combined, APPLICATION_PATTERNS)
        penalty = (
            _score_patterns(position_paragraph.text, ARGUMENT_PATTERNS)
            + _score_patterns(position_paragraph.text, LOWER_COURT_PATTERNS)
            + _score_patterns(combined, OBITER_PATTERNS)
        )
        costs_only_disposition = bool(
            any(pattern.search(combined) for pattern in COST_ORDER_PATTERNS)
            and not _score_patterns(combined, SUBSTANTIVE_REASONING_PATTERNS)
        )
        if costs_only_disposition:
            penalty += 8
        total_score = (
            position_score + reasoning_score + necessity_score + application_score - penalty
        )
        if total_score <= 0:
            continue

        warnings: list[str] = []
        if penalty:
            warnings.append(
                "Candidate includes language that may describe submissions, a lower court, non-ratio observations, or a costs-only disposition."
            )
        if position_paragraph.reference != reasoning_paragraph.reference:
            warnings.append(
                "Equation components are drawn from adjacent paragraphs and must be read together."
            )
        confidence = max(0.0, min(1.0, round(total_score / 18, 3)))
        application_evidence = None
        application_ranked = [
            (neighbour, _score_patterns(neighbour.text, APPLICATION_PATTERNS))
            for neighbour in neighbours
        ]
        application_ranked = [item for item in application_ranked if item[1] > 0]
        if application_ranked:
            application_paragraph, application_value = max(
                application_ranked, key=lambda item: item[1]
            )
            application_evidence = Evidence(
                application_paragraph.reference,
                application_paragraph.text,
                application_value,
            )

        candidate = RatioCandidate(
            court_position=Evidence(
                position_paragraph.reference, position_paragraph.text, position_score
            ),
            legal_reasoning=Evidence(
                reasoning_paragraph.reference, reasoning_paragraph.text, reasoning_score
            ),
            application=application_evidence,
            position_score=position_score,
            reasoning_score=reasoning_score,
            necessity_score=necessity_score,
            penalty=penalty,
            total_score=round(total_score, 3),
            confidence=confidence,
            warnings=warnings,
        )
        key = (
            candidate.court_position.reference,
            candidate.legal_reasoning.reference,
            candidate.total_score,
        )
        if not any(
            (
                existing.court_position.reference,
                existing.legal_reasoning.reference,
                existing.total_score,
            )
            == key
            for existing in candidates
        ):
            candidates.append(candidate)

    candidates.sort(key=lambda candidate: (-candidate.total_score, -candidate.confidence))
    return candidates[:10]


def analyze_cfa_document(
    raw: str,
    *,
    source_description: str = "operator-provided document",
    source_url: str | None = None,
    retrieved_at: str | None = None,
) -> CFAAnalysis:
    """Analyze one operator-provided judgment and answer the five required questions."""

    text = text_from_document(raw)
    paragraphs = segment_paragraphs(text)
    neutral_citation = _extract_neutral_citation(text)
    action_numbers = _extract_action_numbers(text)
    heading_window = " ".join(text.splitlines()[:220])
    verified_hkcfa = bool(
        re.search(r"\b(?:in the )?court of final appeal\b", heading_window, re.I)
        and (neutral_citation or action_numbers)
    )
    warnings: list[str] = []
    if not verified_hkcfa:
        warnings.append(
            "Court identity could not be verified from the heading plus an HKCFA citation or action number; treat the analysis as out of scope."
        )
    if not paragraphs:
        warnings.append("No numbered judgment paragraphs were detected.")

    front_matter_parties = _front_matter_parties(text)
    case_name = _extract_case_name(text, front_matter_parties)
    parties = front_matter_parties or _extract_parties(case_name, text)
    judges = _extract_judges(text)
    issue = _best_evidence(paragraphs, ISSUE_PATTERNS)
    costs = _costs_evidence(paragraphs)
    candidates = _ratio_candidates(paragraphs)

    if not issue:
        warnings.append(
            "No express issue formulation was located; manual issue reconstruction is required."
        )
    if not costs:
        warnings.append("No operative costs passage was located; costs must be checked manually.")
    if not candidates:
        warnings.append(
            "No paragraph pair satisfied both equation components with a positive score."
        )

    question_1 = {
        "question": "Where was the case heard?",
        "answer": "Hong Kong Court of Final Appeal" if verified_hkcfa else "Not verified",
        "evidence": {
            "reference": "heading",
            "text": "Court of Final Appeal heading and HKCFA citation/action-number check",
        },
        "limitation": "A physical courtroom or building is not inferred unless expressly stated.",
    }
    question_2 = {
        "question": "Who were the parties?",
        "answer": parties,
        "evidence": {"reference": "front matter / case title", "text": case_name or "Not found"},
        "limitation": "Court-ordered anonymity and party capacities are preserved.",
    }
    question_3 = {
        "question": "What was disputed?",
        "answer": issue.text if issue else "Not found",
        "evidence": issue.to_dict() if issue else None,
        "limitation": "An express issue passage is preferred to a generated narrative.",
    }
    question_4 = {
        "question": "Which party follows the costs in the cause?",
        "answer": costs.text if costs else "Not found",
        "evidence": costs.to_dict() if costs else None,
        "limitation": "The tool reports the operative wording and does not infer a costs order from outcome alone.",
    }
    top = candidates[0] if candidates else None
    question_5 = {
        "question": "How did the court apply the ratio decidendi?",
        "answer": (
            {
                "court_position": top.court_position.text,
                "legal_reasoning": top.legal_reasoning.text,
                "application": top.application.text
                if top.application
                else "No separate application passage located",
                "equation_score": top.total_score,
                "confidence": top.confidence,
            }
            if top
            else "Not found"
        ),
        "evidence": top.to_dict() if top else None,
        "limitation": "This is a ranked candidate under the proprietary equation, not a substitute for legal review.",
    }

    provenance = build_provenance(
        raw,
        source_description=source_description,
        source_url=source_url,
        retrieved_at=retrieved_at,
        warnings=warnings,
    )
    return CFAAnalysis(
        provenance=provenance,
        verified_hkcfa=verified_hkcfa,
        neutral_citation=neutral_citation,
        action_numbers=action_numbers,
        case_name=case_name,
        court="Hong Kong Court of Final Appeal" if verified_hkcfa else "Unverified court",
        judges=judges,
        parties=parties,
        questions={
            "1_where_heard": question_1,
            "2_parties": question_2,
            "3_dispute": question_3,
            "4_costs": question_4,
            "5_ratio_application": question_5,
        },
        ratio_candidates=candidates,
        paragraphs_indexed=len(paragraphs),
        warnings=warnings,
    )


def render_cfa_markdown(analysis: CFAAnalysis) -> str:
    """Render a human-reviewable report with evidence references."""

    lines = [
        "# HKCFA Ratio Decidendi Locator Report",
        "",
        "> **Equation:** Court position + legal reasoning = ratio decidendi candidate.",
        "",
        "This report ranks traceable candidates. It does not replace reading the judgment or professional legal analysis.",
        "",
        "## Case Metadata",
        "",
        "| Field | Value |",
        "|---|---|",
        f"| Court verified | {'Yes' if analysis.verified_hkcfa else 'No'} |",
        f"| Neutral citation | {analysis.neutral_citation or 'Not found'} |",
        f"| Action number(s) | {', '.join(analysis.action_numbers) or 'Not found'} |",
        f"| Case name | {analysis.case_name or 'Not found'} |",
        f"| Judges | {', '.join(analysis.judges) or 'Not found'} |",
        f"| Paragraphs indexed | {analysis.paragraphs_indexed} |",
        f"| Source | {analysis.provenance.source_url or analysis.provenance.source_description} |",
        f"| SHA-256 | `{analysis.provenance.sha256}` |",
        "",
        "## Five Required Questions",
        "",
    ]
    for key in (
        "1_where_heard",
        "2_parties",
        "3_dispute",
        "4_costs",
        "5_ratio_application",
    ):
        item = analysis.questions[key]
        lines.extend([f"### {item['question']}", ""])
        answer = item["answer"]
        if isinstance(answer, (dict, list)):
            lines.extend(["```json", json.dumps(answer, ensure_ascii=False, indent=2), "```"])
        else:
            lines.append(str(answer))
        lines.extend(["", f"**Limitation:** {item['limitation']}", ""])

    lines.extend(["## Ranked Ratio Candidates", ""])
    if not analysis.ratio_candidates:
        lines.append("No candidate satisfied both equation components.")
    for index, candidate in enumerate(analysis.ratio_candidates, start=1):
        lines.extend(
            [
                f"### Candidate {index} — score {candidate.total_score:.3f}, confidence {candidate.confidence:.3f}",
                "",
                f"**Court position [{candidate.court_position.reference}]:** {candidate.court_position.text}",
                "",
                f"**Legal reasoning [{candidate.legal_reasoning.reference}]:** {candidate.legal_reasoning.text}",
                "",
            ]
        )
        if candidate.application:
            lines.extend(
                [
                    f"**Application [{candidate.application.reference}]:** {candidate.application.text}",
                    "",
                ]
            )
        if candidate.warnings:
            lines.append("**Warnings:** " + " ".join(candidate.warnings))
            lines.append("")

    if analysis.warnings:
        lines.extend(["## Review Warnings", ""])
        lines.extend(f"- {warning}" for warning in analysis.warnings)
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def analyze_cfa_file(
    input_path: str | Path,
    *,
    source_url: str | None = None,
    retrieved_at: str | None = None,
) -> CFAAnalysis:
    """Analyze a local file and record its path as the source description."""

    path = Path(input_path)
    raw = path.read_text(encoding="utf-8")
    return analyze_cfa_document(
        raw,
        source_description=str(path),
        source_url=source_url,
        retrieved_at=retrieved_at,
    )
