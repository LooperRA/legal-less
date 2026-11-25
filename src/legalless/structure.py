"""Structural parsing of HKCFA judgments: front matter, headings, paragraphs and judge zones.

This module is deterministic.  It never paraphrases.  It turns a judgment (HKLII Markdown,
HKLII API JSON/HTML, or plain text) into a :class:`CaseDocument` in which every numbered
paragraph carries

* the heading path (lettered headings and subtitles) under which it sits, and
* the *zone* (the judge, or group of judges, speaking) to which it belongs.

Zones are the unit that prevents contradictory extraction: a proposition in a dissent is
never merged with a proposition in the lead judgment, and an "I agree" concurrence is
recorded as support for the zone it agrees with rather than as an independent source.
"""
from __future__ import annotations

import html as html_lib
import json
import re
from dataclasses import asdict, dataclass, field
from typing import Any

from bs4 import BeautifulSoup

# ---------------------------------------------------------------------------
# Patterns
# ---------------------------------------------------------------------------

_TITLE = r"(?:PJ|NPJ|PJJ|NPJJ|CJ|JA|J|CFA)"
_NAME = r"[A-Z][A-Za-z'’\-]+(?:\s+[A-Z][A-Za-z'’\-]+){0,3}"
JUDGE_NAME_RE = re.compile(
    rf"(?:The\s+)?Chief\s+Justice(?:\s+(?!and\b){_NAME})?"
    rf"|(?:Mr|Madam|Mrs|Ms)\s+Justice\s+{_NAME}(?:\s+{_TITLE})?"
    rf"|(?:Lord|Lady|Baroness|Sir|Dame)\s+{_NAME}(?:\s+{_TITLE})?",
)
# A zone header is a short standalone line consisting only of judge names ending with ':'.
ZONE_HEADER_RE = re.compile(
    rf"^(?P<who>(?:(?:{JUDGE_NAME_RE.pattern})(?:\s*,\s*|\s+and\s+|\s*&\s*)?)+)"
    r"(?:\s*\((?P<note>[^)]{0,120})\))?\s*[:：]\s*$"
)
APPEAL_COMMITTEE_HEADER_RE = re.compile(
    r"^(?:The\s+)?(?:Appeal\s+Committee|Court)(?:\s*\((?P<note>[^)]{0,120})\))?\s*[:：]\s*$", re.I
)
CHINESE_ZONE_HEADER_RE = re.compile(r"^(?P<who>[^\s，。]{0,40}法官(?:[^\s，。]{0,30}法官)*)\s*[:：]\s*$")
PARA_RE = re.compile(r"^(?P<num>\d{1,4})\s*\\?\.\s+(?P<body>\S.*)$")
BRACKET_PARA_RE = re.compile(r"^\[(?P<num>\d{1,4})\]\s+(?P<body>\S.*)$")
LETTER_HEADING_RE = re.compile(
    r"^(?P<label>(?:[A-Z]\d{0,2}[a-z]?|[IVX]{1,5})(?:\.\d+[a-z]?)*(?:\.\d+)?\.?|\([a-z]{1,3}\)|\([ivx]{1,5}\))\s+(?P<text>\S.{1,180})$"
)
CITATION_RE = re.compile(r"\[(?P<year>(?:19|20)\d{2})\]\s+HKCFA\s+(?P<num>\d+)")
ACTION_RE = re.compile(
    r"\b(?P<code>FAC[VCP]|FAM[VCP]|FAMV|FAMC|FAMP)\s*(?:No\.?\s*)?(?P<num>\d+)\s*(?:of|/)\s*(?P<year>(?:19|20)\d{2})",
    re.I,
)
DATE_LABEL_RE = re.compile(
    r"Date\s+of\s+(?P<label>Hearing\s+and\s+(?:Determination|Judgment)|Hearing|Judgment|"
    r"Reasons\s+for\s+(?:Judgment|Determination|Decision)|Determination|Decision|Handing\s+Down|"
    r"Reasons)\s*[:：]\s*(?P<value>[^|\n]{4,80})",
    re.I,
)
DATE_VALUE_RE = re.compile(
    r"(\d{1,2})(?:\s*(?:and|&|-|–)\s*\d{1,2})?\s+(January|February|March|April|May|June|July|"
    r"August|September|October|November|December)\s+((?:19|20)\d{2})",
    re.I,
)
AGREE_RE = re.compile(
    r"\bI\s+(?:also\s+)?(?:entirely\s+|respectfully\s+|fully\s+)?(?:agree|concur)\b(?P<rest>[^.]{0,260})",
    re.I,
)
DELIVERING_RE = re.compile(r"deliver(?:ing|ed)\s+the\s+(?:judgment|reasons|determination)\s+of\s+the\s+(?:Court|Committee)", re.I)
DISSENT_IN_ORDER_RE = re.compile(
    rf"(?P<who>(?:{JUDGE_NAME_RE.pattern})(?:\s+and\s+(?:{JUDGE_NAME_RE.pattern}))?)\s+dissent(?:ing|ed)?",
)
MAJORITY_RE = re.compile(r"\bby\s+a\s+majority\b|\bmajority\s+of\s+the\s+Court\b", re.I)
UNANIMOUS_RE = re.compile(r"\bunanimous(?:ly)?\b", re.I)
LEAVE_RE = re.compile(r"\bleave\s+to\s+appeal\b|\bAppeal\s+Committee\b|\bFAM[VCP]\b", re.I)
ORDERISH_RE = re.compile(
    r"\b(?:allowed|dismissed|dismisses|allows|quash(?:ed|es)?|set\s+aside|order\s+nisi|costs\s+(?:of|be)|"
    r"leave\s+(?:to\s+appeal\s+)?(?:is\s+)?(?:granted|refused)|grant\s+leave|refuse\s+leave|answer(?:ed)?\s+(?:to\s+)?the\s+question)\b",
    re.I,
)
SEPARATOR_RE = re.compile(r"^[\\_\-=\s*]{5,}$")


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class Heading:
    label: str
    text: str
    level: int
    line_index: int
    zone_id: str | None = None

    @property
    def title(self) -> str:
        return f"{self.label} {self.text}".strip()


@dataclass(slots=True)
class Para:
    number: int
    text: str
    zone_id: str
    heading_path: list[str] = field(default_factory=list)

    def ref(self) -> str:
        return f"[{self.number}]"


@dataclass(slots=True)
class Zone:
    zone_id: str
    judges: list[str]
    header: str
    role: str = "unclassified"  # lead | joint_lead | concurring_agree | concurring_separate | dissent | order | committee
    agrees_with: list[str] = field(default_factory=list)  # zone_ids this zone expressly agrees with
    supported_by: list[str] = field(default_factory=list)  # judges who agree with this zone
    paragraph_numbers: list[int] = field(default_factory=list)
    note: str | None = None

    @property
    def span(self) -> str:
        if not self.paragraph_numbers:
            return ""
        return f"[{self.paragraph_numbers[0]}]–[{self.paragraph_numbers[-1]}]"


@dataclass(slots=True)
class CaseDocument:
    neutral_citation: str | None
    action_numbers: list[str]
    case_title: str | None
    coram: list[str]
    court_level: str
    proceeding_type: str  # substantive_appeal | leave_application | other
    dates: dict[str, str]
    headings: list[Heading]
    paragraphs: list[Para]
    zones: list[Zone]
    bench_outcome: str  # unanimous | majority | unknown
    dissenting_judges: list[str]
    warnings: list[str] = field(default_factory=list)

    # convenience -------------------------------------------------------
    def para(self, number: int) -> Para | None:
        for p in self.paragraphs:
            if p.number == number:
                return p
        return None

    def zone(self, zone_id: str) -> Zone | None:
        return next((z for z in self.zones if z.zone_id == zone_id), None)

    def zone_paragraphs(self, zone_id: str) -> list[Para]:
        return [p for p in self.paragraphs if p.zone_id == zone_id]

    @property
    def lead_zones(self) -> list[Zone]:
        return [z for z in self.zones if z.role in {"lead", "joint_lead", "committee"}]

    @property
    def primary_date(self) -> str | None:
        for key in ("reasons_for_judgment", "judgment", "hearing_and_determination", "determination",
                    "reasons_for_determination", "handing_down", "decision", "reasons"):
            if self.dates.get(key):
                return self.dates[key]
        return None

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["primary_date"] = self.primary_date
        return data

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# Normalisation
# ---------------------------------------------------------------------------


def _html_to_lines(raw: str) -> str:
    soup = BeautifulSoup(raw, "html.parser")
    for node in soup(["script", "style", "noscript"]):
        node.decompose()
    for tag in soup.find_all(["b", "strong"]):
        txt = tag.get_text(" ", strip=True)
        tag.replace_with(f"**{txt}**" if txt else "")
    for tag in soup.find_all(["br"]):
        tag.replace_with("\n")
    for tag in soup.find_all(["p", "div", "tr", "li", "h1", "h2", "h3", "h4", "h5", "h6", "blockquote"]):
        tag.insert_before("\n")
        tag.insert_after("\n")
    return soup.get_text("")


def load_raw(raw: str) -> str:
    """Accept HKLII API JSON, HTML or Markdown/plain text and return Markdown-like text."""
    stripped = raw.lstrip()
    if stripped.startswith("{"):
        try:
            obj = json.loads(raw)
            content = obj.get("content") or obj.get("html") or ""
            if content:
                header = f"{obj.get('neutral', '')}\n" if obj.get("neutral") else ""
                return header + _html_to_lines(content)
        except json.JSONDecodeError:
            pass
    if re.search(r"<(?:html|body|div|p|table|br)\b", raw, re.I):
        return _html_to_lines(raw)
    return raw


def _clean(line: str) -> str:
    line = html_lib.unescape(line)
    line = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", line)
    line = re.sub(r"\[\[(\d+)\]\]\(\)", r"[fn\1]", line)  # HKLII footnote markers
    line = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", line)
    line = line.replace("\\_", "_").replace("\\.", ".").replace("\\*", "*").replace("\\(", "(").replace("\\)", ")")
    line = line.replace("\u00a0", " ")
    return re.sub(r"[ \t]+", " ", line).strip()


def _is_bold_line(line: str) -> bool:
    s = line.strip()
    return bool(re.fullmatch(r"(?:\*\*_?|_\*\*|__)\s*.+?\s*(?:_?\*\*|\*\*_|__)", s)) or (
        s.startswith("**") and s.endswith("**") and len(s) > 4
    )


def _strip_marks(line: str) -> str:
    s = line.replace("**", "").replace("__", "")
    s = re.sub(r"(?<!\w)_(.+?)_(?!\w)", r"\1", s)
    return re.sub(r"\s+", " ", s).strip(" |")


def normalise_text(raw: str) -> str:
    """Public helper: plain text used for verbatim quote validation."""
    return re.sub(r"\s+", " ", _strip_marks(_clean(raw))).strip()


# ---------------------------------------------------------------------------
# Front matter
# ---------------------------------------------------------------------------


def _parse_date(value: str) -> str | None:
    m = DATE_VALUE_RE.search(value)
    if not m:
        return None
    months = ["january", "february", "march", "april", "may", "june", "july", "august",
              "september", "october", "november", "december"]
    month = months.index(m.group(2).lower()) + 1
    return f"{m.group(3)}-{month:02d}-{int(m.group(1)):02d}"


def _date_key(label: str) -> str:
    label = re.sub(r"\s+", " ", label.lower())
    mapping = {
        "hearing and determination": "hearing_and_determination",
        "hearing and judgment": "hearing_and_judgment",
        "hearing": "hearing",
        "judgment": "judgment",
        "reasons for judgment": "reasons_for_judgment",
        "reasons for determination": "reasons_for_determination",
        "reasons for decision": "reasons_for_decision",
        "determination": "determination",
        "decision": "decision",
        "handing down": "handing_down",
        "reasons": "reasons",
    }
    return mapping.get(label, label.replace(" ", "_"))


def _extract_coram(front: str) -> list[str]:
    m = re.search(r"(?:Before|Coram|Appeal\s+Committee)\s*[:：]\s*(?P<b>[^|\n]{5,600})", front, re.I)
    if not m:
        return []
    block = re.split(r"\bDate\s+of\b", m.group("b"))[0]
    judges: list[str] = []
    for jm in JUDGE_NAME_RE.finditer(block):
        name = re.sub(r"\s+", " ", jm.group(0)).strip(" ,;")
        if name not in judges:
            judges.append(name)
    return judges


def _surname(judge: str) -> str:
    """Return a comparable key: 'Mr Justice Fok PJ' -> 'fok'; 'Chief Justice Ma' -> 'ma'."""
    s = re.sub(r"^(?:The\s+)?(?:Chief\s+Justice|(?:Mr|Madam|Mrs|Ms)\s+Justice|Lord|Lady|Baroness|Sir|Dame)\s+", "", judge.strip())
    s = re.sub(rf"\s+{_TITLE}$", "", s)
    return s.strip().lower() or judge.strip().lower()


def _split_judges(who: str) -> list[str]:
    names = [re.sub(r"\s+", " ", m.group(0)).strip() for m in JUDGE_NAME_RE.finditer(who)]
    # "Mr Justice Ribeiro and Mr Justice Fok PJJ" -> carry the plural title to both names
    if names and re.search(r"\bPJJ\b", who):
        names = [re.sub(r"\s+PJJ$", "", n) + " PJ" for n in names]
    if names and re.search(r"\bNPJJ\b", who):
        names = [re.sub(r"\s+NPJJ$", "", n) + " NPJ" for n in names]
    return names


# ---------------------------------------------------------------------------
# Main parser
# ---------------------------------------------------------------------------


def parse_judgment(raw: str, *, case_title: str | None = None) -> CaseDocument:
    text = load_raw(raw)
    raw_lines = [_clean(line) for line in text.replace("\r\n", "\n").split("\n")]
    warnings: list[str] = []

    flat = "\n".join(_strip_marks(line) for line in raw_lines)
    cit = CITATION_RE.search(flat)
    neutral = f"[{cit.group('year')}] HKCFA {int(cit.group('num'))}" if cit else None

    # Locate the first zone header or first numbered paragraph: everything before is front matter.
    body_start = None
    for i, line in enumerate(raw_lines):
        s = _strip_marks(line)
        if (ZONE_HEADER_RE.match(s) or APPEAL_COMMITTEE_HEADER_RE.match(s) or CHINESE_ZONE_HEADER_RE.match(s)
                or PARA_RE.match(s)) and i > 5:
            body_start = i
            break
    if body_start is None:
        body_start = 0
        warnings.append("Could not locate the start of the reasons; whole document treated as body.")
    front = "\n".join(re.sub(r"\s*\|\s*", " ", _strip_marks(line)) for line in raw_lines[:body_start])

    actions: list[str] = []
    for m in ACTION_RE.finditer(front):
        a = f"{m.group('code').upper()} {int(m.group('num'))}/{m.group('year')}"
        if a not in actions:
            actions.append(a)
    for m in re.finditer(r"FINAL APPEAL NO\.\s*(\d+)\s+OF\s+((?:19|20)\d{2})\s*\((CIVIL|CRIMINAL)\)", front, re.I):
        a = f"{'FACV' if m.group(3).upper() == 'CIVIL' else 'FACC'} {int(m.group(1))}/{m.group(2)}"
        if a not in actions:
            actions.append(a)
    for m in re.finditer(r"MISCELLANEOUS PROCEEDINGS NO\.\s*(\d+)\s+OF\s+((?:19|20)\d{2})\s*\((CIVIL|CRIMINAL)\)", front, re.I):
        a = f"{'FAMV' if m.group(3).upper() == 'CIVIL' else 'FAMC'} {int(m.group(1))}/{m.group(2)}"
        if a not in actions:
            actions.append(a)

    dates: dict[str, str] = {}
    for m in DATE_LABEL_RE.finditer(front):
        iso = _parse_date(m.group("value"))
        if iso:
            dates.setdefault(_date_key(m.group("label")), iso)

    coram = _extract_coram(front)
    if not coram:
        warnings.append("Coram not parsed from front matter.")

    if case_title is None:
        for line in front.splitlines():
            line = re.sub(r'^.*?html PUBLIC "[^"]*" "[^"]*"\s*', "", line)
            line = re.sub(r"\s*Press Summary.*$", "", line)
            line = re.sub(r"^FA[CM][VCP]\s*\d+/\d{4}\s+", "", line)
            if re.search(r"\S\s+[Vv]\.?\s+\S", line) and len(line) < 300 and not re.search(r"HKCFAR|HKC\b|LawCite|http", line):
                case_title = re.sub(r"\s+FA[CM][VCP]\s*\d+/\d{4}.*$", "", line).strip(" *")
                break

    is_leave = any(a.startswith("FAM") for a in actions) or bool(
        re.search(r"\bAppeal\s+Committee\s*[:：]|DETERMINATION|application\s+for\s+leave\s+to\s+appeal", front, re.I)
    )
    proceeding_type = "leave_application" if is_leave and not any(a.startswith("FAC") for a in actions) else "substantive_appeal"
    court_level = (
        "Court of Final Appeal – Appeal Committee (leave stage)" if proceeding_type == "leave_application"
        else "Court of Final Appeal – Full Court (final appeal)"
    )

    # ---------------------------------------------------------------- body walk
    zones: list[Zone] = []
    headings: list[Heading] = []
    paragraphs: list[Para] = []
    heading_stack: list[Heading] = []
    current_zone: Zone | None = None
    current_para: Para | None = None
    expected_next = 1

    def new_zone(judges: list[str], header: str, note: str | None = None) -> Zone:
        z = Zone(zone_id=f"Z{len(zones) + 1}", judges=judges, header=header, note=note)
        zones.append(z)
        return z

    for idx in range(body_start, len(raw_lines)):
        line = raw_lines[idx]
        if not line:
            continue
        s = _strip_marks(line)
        if not s or SEPARATOR_RE.match(line):
            continue
        if re.match(r"^\[fn\d+\]", s) and current_para is not None and current_para.number > 0 and idx > len(raw_lines) * 0.5:
            # footnote apparatus after the reasons — stop attaching to paragraphs
            current_para = None
            continue

        zh = ZONE_HEADER_RE.match(s)
        ac = APPEAL_COMMITTEE_HEADER_RE.match(s)
        cz = CHINESE_ZONE_HEADER_RE.match(s)
        if zh or ac or cz:
            if zh:
                judges = _split_judges(zh.group("who"))
                note = zh.group("note")
            elif ac:
                judges = ["Appeal Committee" if "committee" in s.lower() else "The Court"]
                note = ac.group("note")
            else:
                judges = [cz.group("who")]
                note = None
            current_zone = new_zone(judges, s, note)
            heading_stack = []
            current_para = None
            continue

        pm = PARA_RE.match(s) or BRACKET_PARA_RE.match(s)
        if pm:
            num = int(pm.group("num"))
            # accept the expected sequence, or a small jump (missing paragraph in source)
            if expected_next <= num <= expected_next + 3:
                if num != expected_next:
                    warnings.append(f"Paragraph numbering jumps from {expected_next - 1} to {num}.")
                if current_zone is None:
                    current_zone = new_zone(["(unattributed)"], "(no zone header)")
                    warnings.append("Paragraphs found before any judge header; placed in an unattributed zone.")
                current_para = Para(num, pm.group("body"), current_zone.zone_id, [h.title for h in heading_stack])
                paragraphs.append(current_para)
                current_zone.paragraph_numbers.append(num)
                expected_next = num + 1
                continue

        hm = LETTER_HEADING_RE.match(s)
        bold = _is_bold_line(line)
        looks_heading = (hm and len(s) <= 190 and not s.endswith((",", ";"))) or (
            bold and len(s) <= 160 and not re.match(r"^(?:\d+\.|\(\d+\))", s)
        )
        if looks_heading and current_zone is not None and not s.startswith(">"):
            label = hm.group("label").rstrip(".") if hm else ""
            title = hm.group("text") if hm else s
            level = label.count(".") + 1 if label else 1
            if re.match(r"^\([a-z]{1,3}\)$|^\([ivx]+\)$", label or ""):
                level = 3
            h = Heading(label=label, text=title.strip(), level=level, line_index=idx, zone_id=current_zone.zone_id)
            headings.append(h)
            heading_stack = [x for x in heading_stack if x.level < level] + [h]
            current_para = None
            continue

        if current_para is not None:
            current_para.text = f"{current_para.text}\n{s.lstrip('> ').strip()}"

    for p in paragraphs:
        p.text = re.sub(r"[ \t]+", " ", p.text).strip()

    _classify_zones(zones, paragraphs, coram)
    bench_outcome, dissenters = _bench_outcome(zones, paragraphs, coram)
    for z in zones:
        if z.role not in {"order"} and any(_surname(j) in {_surname(d) for d in dissenters} for j in z.judges):
            z.role = "dissent"

    if not paragraphs:
        warnings.append("No numbered paragraphs were segmented.")
    if not dates:
        warnings.append("No judgment/determination date parsed from front matter.")

    return CaseDocument(
        neutral_citation=neutral,
        action_numbers=actions,
        case_title=case_title,
        coram=coram,
        court_level=court_level,
        proceeding_type=proceeding_type,
        dates=dates,
        headings=headings,
        paragraphs=paragraphs,
        zones=zones,
        bench_outcome=bench_outcome,
        dissenting_judges=dissenters,
        warnings=warnings,
    )


# ---------------------------------------------------------------------------
# Zone classification
# ---------------------------------------------------------------------------


def _resolve_target(rest: str, zones: list[Zone], self_zone: Zone) -> list[str]:
    """Find which zone an 'I agree with the judgment of X (and Y)' sentence refers to."""
    named = {_surname(m.group(0)) for m in JUDGE_NAME_RE.finditer(rest)}
    if re.search(r"\bChief Justice\b", rest) and not named:
        named = {"chief justice"}
    targets: list[str] = []
    big = [z for z in zones if len(z.paragraph_numbers) > 3] or zones
    for z in big:
        if z is self_zone:
            continue
        zs = {_surname(j) for j in z.judges}
        if named and (named & zs or (named == {"chief justice"} and any("chief justice" in j.lower() for j in z.judges))):
            targets.append(z.zone_id)
    return targets


def _classify_zones(zones: list[Zone], paragraphs: list[Para], coram: list[str]) -> None:
    by_zone = {z.zone_id: [p for p in paragraphs if p.zone_id == z.zone_id] for z in zones}
    for z in zones:
        paras = by_zone[z.zone_id]
        joined = " ".join(p.text for p in paras)
        if z.judges in (["Appeal Committee"], ["The Court"]) or (z.note and DELIVERING_RE.search(z.note)):
            z.role = "committee"
            z.supported_by = list(coram)
            continue
        if paras and len(paras) <= 3:
            m = AGREE_RE.search(paras[0].text) or (AGREE_RE.search(paras[-1].text) if len(paras) > 1 else None)
            orderish = ORDERISH_RE.search(joined)
            if m:
                z.agrees_with = _resolve_target(m.group("rest"), zones, z) or _resolve_target(joined, zones, z)
                z.role = "order" if orderish else "concurring_agree"
                continue
            if orderish:
                z.role = "order"
                continue
        z.role = "substantive"

    # supported_by: judges agreeing with each substantive zone (directly or via order zones)
    for z in zones:
        z.supported_by = list(coram) if z.role == "committee" else list(z.judges)
    for z in zones:
        for target in z.agrees_with:
            t = next(x for x in zones if x.zone_id == target)
            for j in z.judges:
                if j not in t.supported_by:
                    t.supported_by.append(j)

    substantive = [z for z in zones if z.role == "substantive"]
    if not substantive:
        # Short determinations (e.g. Appeal Committee leave rulings) may consist of one short zone.
        pool = [z for z in zones if z.role != "concurring_agree" and z.paragraph_numbers]
        if not pool:
            return
        only = max(pool, key=lambda z: len(z.paragraph_numbers))
        only.role = "committee"
        for j in coram:
            if j not in only.supported_by:
                only.supported_by.append(j)
        return
    # lead = substantive zone with most support; ties -> the longer zone
    lead = max(substantive, key=lambda z: (len(z.supported_by), len(z.paragraph_numbers)))
    lead.role = "joint_lead" if len(lead.judges) > 1 else "lead"
    for z in substantive:
        if z is lead:
            continue
        z.role = "concurring_separate"  # may be overridden as dissent later


def _bench_outcome(zones: list[Zone], paragraphs: list[Para], coram: list[str]) -> tuple[str, list[str]]:
    dissenters: list[str] = []
    announcing = {"order", "committee", "concurring_agree", "lead", "joint_lead"}
    for z in zones:
        if z.role not in announcing:
            continue
        for p in (p for p in paragraphs if p.zone_id == z.zone_id):
            for m in DISSENT_IN_ORDER_RE.finditer(p.text):
                for j in _split_judges(m.group("who")):
                    if j not in dissenters:
                        dissenters.append(j)
    joined = " ".join(p.text for z in zones if z.role == "order" for p in paragraphs if p.zone_id == z.zone_id)
    if dissenters or MAJORITY_RE.search(joined):
        return "majority", dissenters
    if UNANIMOUS_RE.search(joined) or all(z.role != "concurring_separate" for z in zones):
        return "unanimous", dissenters
    return "unknown", dissenters


def zone_label(doc: CaseDocument, zone_id: str) -> str:
    z = doc.zone(zone_id)
    if not z:
        return zone_id
    return f"{zone_id} {' & '.join(z.judges)} ({z.role}) {z.span}"
