"""Ratio decidendi pipeline (v0.2): LEGAL PRINCIPLE + COURT POSITION = RATIO DECIDENDI.

Stages (one judgment at a time):

1. **Structure** – :func:`legalless.structure.parse_judgment` builds headings, numbered
   paragraphs and judge *zones* (lead / joint lead / committee / concurring / dissent / order).
2. **Inventory** – every zone that speaks for itself is read paragraph by paragraph and every
   legal principle (LP) and court position (CP) is recorded with a verbatim quote.  Quotes are
   validated programmatically against the source paragraph; unverifiable quotes are dropped.
3. **Combination** – LPs and CPs are matched into combos by issue *within the same zone*.
4. **Trial test & verification** – each combo is applied to the case's own material facts:
   does it produce the actual outcome; would inverting it change the outcome; would applying it
   produce a logically intolerable result?  A deterministic authority gate then requires the
   combo's zone to carry a majority of the bench (or to be the Appeal Committee's ruling).
   Only combos that survive every test are labelled ``TRUE_RATIO``.
5. **Case summary** – who made the ratio, date, court level, core issue, result, obiter and
   dissenting comments (English and Traditional Chinese).

Leave determinations (FAMV/FAMC/FAMP) are analysed like any other decision: the Appeal
Committee states legal principles (e.g. the s.32 HKCFAO thresholds) and takes court positions
on them, so they are capable of yielding a ratio.
"""
from __future__ import annotations

import json
import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from hashlib import sha256
from typing import Any

from .llm import JSONModel
from .structure import CaseDocument, Para, Zone, parse_judgment

PIPELINE_VERSION = "0.2.0"

# ---------------------------------------------------------------------------
# Verbatim quote validation and pinpoints
# ---------------------------------------------------------------------------

_QUOTE_MAP = str.maketrans({"’": "'", "‘": "'", "“": '"', "”": '"', "–": "-", "—": "-", "\u00a0": " "})


def _norm(text: str) -> str:
    text = re.sub(r"\[fn\d+\]", " ", text)
    text = text.translate(_QUOTE_MAP).replace("**", "").replace("`", "")
    text = re.sub(r"(?<!\w)_(.+?)_(?!\w)", r"\1", text)
    return re.sub(r"\s+", " ", text).strip()


def _norm_cmp(text: str) -> str:
    return re.sub(r"[^\w]+", " ", _norm(text).lower()).strip()


def _sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.;:?!])\s+(?=[\"'(\[A-Z0-9])", _norm(text))
    return [p for p in parts if p.strip()]


@dataclass(slots=True)
class Pinpoint:
    paragraph: int
    sentence_from: int
    sentence_to: int
    verified: bool
    method: str  # exact | ellipsis | none

    def label(self, citation: str | None) -> str:
        s = (f"s.{self.sentence_from}" if self.sentence_from == self.sentence_to
             else f"ss.{self.sentence_from}-{self.sentence_to}")
        base = f"at [{self.paragraph}]"
        return f"{citation + ' ' if citation else ''}{base} ({s})"


def verify_quote(para: Para, quote: str) -> Pinpoint:
    """Confirm that ``quote`` appears verbatim (modulo whitespace/quote glyphs) in ``para``."""
    hay = _norm_cmp(para.text)
    segments = [seg for seg in re.split(r"\s*(?:\.\.\.|…)\s*", quote) if _norm_cmp(seg)]
    if not segments:
        return Pinpoint(para.number, 0, 0, False, "none")
    pos = 0
    first_hit = last_hit = -1
    for seg in segments:
        needle = _norm_cmp(seg)
        hit = hay.find(needle, pos)
        if hit < 0:
            return Pinpoint(para.number, 0, 0, False, "none")
        if first_hit < 0:
            first_hit = hit
        last_hit = hit + len(needle)
        pos = last_hit
    # sentence pinpoint
    sents = _sentences(para.text)
    offsets, cursor = [], 0
    for s in sents:
        n = _norm_cmp(s)
        idx = hay.find(n, cursor)
        idx = cursor if idx < 0 else idx
        offsets.append((idx, idx + len(n)))
        cursor = idx + len(n)
    s_from = next((i + 1 for i, (a, b) in enumerate(offsets) if a <= first_hit < b + 1), 1)
    s_to = next((i + 1 for i, (a, b) in enumerate(offsets) if a < last_hit <= b + 1), s_from)
    return Pinpoint(para.number, s_from, max(s_from, s_to), True, "exact" if len(segments) == 1 else "ellipsis")


# ---------------------------------------------------------------------------
# Result data model
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class Item:
    item_id: str
    kind: str  # legal_principle | court_position
    zone_id: str
    zone_judges: list[str]
    zone_role: str
    paragraph: int
    heading_path: list[str]
    quote: str
    statement: str
    issue: str
    status: str
    pinpoint: str
    quote_verified: bool


@dataclass(slots=True)
class Combo:
    combo_id: str
    issue_id: str
    zone_id: str
    principle_ids: list[str]
    position_ids: list[str]
    ratio_statement: str
    classification: str
    reasoning: str
    paragraphs: list[int] = field(default_factory=list)
    ratio_zh: str = ""
    # trial test
    material_facts_applied: str = ""
    predicted_outcome: str = ""
    actual_outcome: str = ""
    consistent_with_outcome: bool | None = None
    inversion_changes_outcome: bool | None = None
    logically_intolerable: bool | None = None
    intolerability_reason: str = ""
    authority_gate: str = ""
    verdict: str = "UNTESTED"
    confidence: float = 0.0
    test_explanation: str = ""


@dataclass(slots=True)
class CaseResult:
    neutral_citation: str | None
    case_title: str | None
    action_numbers: list[str]
    court_level: str
    proceeding_type: str
    dates: dict[str, str]
    primary_date: str | None
    coram: list[str]
    bench_outcome: str
    dissenting_judges: list[str]
    zones: list[dict[str, Any]]
    headings: list[str]
    issues: list[dict[str, Any]]
    items: list[Item]
    combos: list[Combo]
    summary: dict[str, Any]
    warnings: list[str]
    provenance: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    @property
    def true_ratios(self) -> list[Combo]:
        return [c for c in self.combos if c.verdict == "TRUE_RATIO"]


# ---------------------------------------------------------------------------
# Prompts and schemas
# ---------------------------------------------------------------------------

FORMULA = (
    "Method: LEGAL PRINCIPLE + COURT POSITION = RATIO DECIDENDI.\n"
    "LEGAL PRINCIPLE (LP): a general proposition of law - rule, test, standard, statutory or "
    "constitutional construction, doctrine, or a threshold such as the leave criteria - that the "
    "speaking judge(s) state, adopt or endorse as the law, capable of application beyond these parties. "
    "Restating an authority counts only if the speaking judge(s) adopt it.\n"
    "COURT POSITION (CP): the speaking judge(s)' own determination of a disputed point in THIS case - "
    "accepting or rejecting an argument, applying a principle to these facts, answering a certified "
    "question, granting or refusing leave on a criterion, overruling or approving a decision, or a "
    "dispositive conclusion.\n"
    "Leave-stage rulings by the Appeal Committee contain LPs and CPs and are analysed in the same way.\n"
)

INVENTORY_SYSTEM = (
    "You are a meticulous Hong Kong appellate-law analyst. " + FORMULA +
    "Task: read ONLY the paragraphs supplied (all belong to one judge zone) and list every LP and every CP "
    "they contain. Exclude counsel's submissions, lower-court reasoning and narrative facts unless the "
    "speaking judge(s) adopt or decide them. Each item MUST carry a verbatim quote copied exactly from the "
    "stated paragraph (contiguous words; 8-70 words; use '...' only to omit words). Never paraphrase inside "
    "the quote. 'statement' is your neutral one-sentence restatement. 'status' records how the zone treats "
    "the proposition. If a paragraph contains nothing relevant, skip it. Return at most 24 items."
)

INVENTORY_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["items"],
    "properties": {
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["kind", "paragraph", "quote", "statement", "issue", "status"],
                "properties": {
                    "kind": {"type": "string", "enum": ["legal_principle", "court_position"]},
                    "paragraph": {"type": "integer"},
                    "quote": {"type": "string"},
                    "statement": {"type": "string"},
                    "issue": {"type": "string", "description": "short label of the legal issue addressed"},
                    "status": {"type": "string", "enum": [
                        "stated_as_law", "applied_to_facts", "argument_rejected", "argument_accepted",
                        "authority_approved", "authority_overruled", "question_answered", "leave_criterion",
                        "dispositive", "left_open", "hypothetical_or_obiter"]},
                },
            },
        }
    },
}

COMBO_SYSTEM = (
    "You are a senior Hong Kong appellate-law analyst. " + FORMULA +
    "You receive the validated inventory of LPs and CPs of ONE judgment, tagged by judge zone, plus the zone "
    "map and the orders. (1) Identify the core legal issues the court had to decide. (2) For each issue and "
    "for each zone that addresses it, combine the LP(s) with the CP(s) that apply them into a combo, and state "
    "the resulting ratio candidate as one precise, general proposition of law (what the court held, at the level "
    "of generality the reasoning supports). Never combine items from different zones. Classify each combo: "
    "candidate_ratio (the zone's reasoning on an issue that the decision turned on), obiter (unnecessary to the "
    "decision, hypothetical, left open, or answered 'in any event'), concurring_view (separate concurrence not "
    "joined by the majority), dissenting_view (zone of a dissenting judge). Use only item ids supplied. "
    "Return at most 20 combos, most important first."
)

COMBO_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["core_issues", "combos"],
    "properties": {
        "core_issues": {
            "type": "array",
            "items": {
                "type": "object", "additionalProperties": False,
                "required": ["issue_id", "question", "answer"],
                "properties": {"issue_id": {"type": "string"}, "question": {"type": "string"},
                               "answer": {"type": "string"}},
            },
        },
        "combos": {
            "type": "array",
            "items": {
                "type": "object", "additionalProperties": False,
                "required": ["issue_id", "zone_id", "principle_ids", "position_ids", "ratio_statement",
                             "classification", "reasoning"],
                "properties": {
                    "issue_id": {"type": "string"},
                    "zone_id": {"type": "string"},
                    "principle_ids": {"type": "array", "items": {"type": "string"}},
                    "position_ids": {"type": "array", "items": {"type": "string"}},
                    "ratio_statement": {"type": "string"},
                    "classification": {"type": "string", "enum": [
                        "candidate_ratio", "obiter", "concurring_view", "dissenting_view"]},
                    "reasoning": {"type": "string"},
                },
            },
        },
    },
}

TRIAL_SYSTEM = (
    "You are a sceptical Hong Kong appellate judge testing proposed rationes decidendi. " + FORMULA +
    "For EACH combo: (a) take the material facts of this very case and apply the proposed ratio to them as if "
    "deciding the case afresh; (b) state the outcome the ratio produces on its issue and the outcome the court "
    "actually reached; (c) say whether they are consistent; (d) inversion test: if the proposition were "
    "reversed, would the court's actual outcome on that issue have had to change; (e) intolerability test: would "
    "applying the ratio as stated to these facts lead to a logically intolerable result - contradiction with "
    "the orders made, with another holding of the majority, with the statutory text relied on, internal "
    "self-contradiction, or an absurd or overbroad consequence. Then give a verdict: TRUE_RATIO only if "
    "consistent, necessary (inversion changes the outcome or it is a co-equal alternative ground expressly relied "
    "on) and tolerable; otherwise OBITER, NOT_NECESSARY, FAILED_INTOLERABLE or MINORITY_VIEW. If the statement is "
    "slightly overbroad but the core survives, give TRUE_RATIO and put a narrowed wording in 'refined_ratio'."
)

TRIAL_SCHEMA = {
    "type": "object", "additionalProperties": False, "required": ["tests"],
    "properties": {"tests": {"type": "array", "items": {
        "type": "object", "additionalProperties": False,
        "required": ["combo_id", "material_facts_applied", "predicted_outcome", "actual_outcome",
                     "consistent_with_outcome", "inversion_changes_outcome", "logically_intolerable",
                     "intolerability_reason", "verdict", "refined_ratio", "confidence", "explanation"],
        "properties": {
            "combo_id": {"type": "string"},
            "material_facts_applied": {"type": "string"},
            "predicted_outcome": {"type": "string"},
            "actual_outcome": {"type": "string"},
            "consistent_with_outcome": {"type": "boolean"},
            "inversion_changes_outcome": {"type": "boolean"},
            "logically_intolerable": {"type": "boolean"},
            "intolerability_reason": {"type": "string"},
            "verdict": {"type": "string", "enum": ["TRUE_RATIO", "OBITER", "NOT_NECESSARY",
                                                     "FAILED_INTOLERABLE", "MINORITY_VIEW"]},
            "refined_ratio": {"type": "string"},
            "confidence": {"type": "number"},
            "explanation": {"type": "string"},
        }}}},
}

SUMMARY_SYSTEM = (
    "You write concise, accurate case summaries of Hong Kong Court of Final Appeal decisions for lawyers and "
    "lay readers. Use only the material supplied. Write the English fields in English and the *_zh fields in "
    "Traditional Chinese using Hong Kong legal terminology consistent with the Department of Justice bilingual "
    "glossary (e.g. 終審法院, 上訴委員會, 判案書, 裁定理由, 附帶意見, 異議判詞, 上訴許可). Do not invent facts, "
    "dates or names. Keep each field under 120 words."
)

SUMMARY_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "required": ["core_issue_en", "core_issue_zh", "final_result_en", "final_result_zh", "summary_en",
                 "summary_zh", "obiter", "dissent", "ratio_zh"],
    "properties": {
        "core_issue_en": {"type": "string"}, "core_issue_zh": {"type": "string"},
        "final_result_en": {"type": "string"}, "final_result_zh": {"type": "string"},
        "summary_en": {"type": "string"}, "summary_zh": {"type": "string"},
        "obiter": {"type": "array", "items": {"type": "object", "additionalProperties": False,
                   "required": ["paragraphs", "note_en", "note_zh"],
                   "properties": {"paragraphs": {"type": "string"}, "note_en": {"type": "string"},
                                  "note_zh": {"type": "string"}}}},
        "dissent": {"type": "array", "items": {"type": "object", "additionalProperties": False,
                    "required": ["judge", "paragraphs", "note_en", "note_zh"],
                    "properties": {"judge": {"type": "string"}, "paragraphs": {"type": "string"},
                                   "note_en": {"type": "string"}, "note_zh": {"type": "string"}}}},
        "ratio_zh": {"type": "array", "items": {"type": "object", "additionalProperties": False,
                     "required": ["combo_id", "ratio_zh"],
                     "properties": {"combo_id": {"type": "string"}, "ratio_zh": {"type": "string"}}}},
    },
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fmt_para(p: Para, limit: int = 6000) -> str:
    path = " > ".join(p.heading_path) if p.heading_path else "-"
    text = _norm(p.text)
    if len(text) > limit:
        text = text[:limit] + " [...]"
    return f"[{p.number}] (heading: {path})\n{text}"


def _chunks(paras: list[Para], max_chars: int = 18000, max_paras: int = 14) -> list[list[Para]]:
    out: list[list[Para]] = []
    cur: list[Para] = []
    size = 0
    for p in paras:
        n = min(len(p.text), 6000)
        if cur and (size + n > max_chars or len(cur) >= max_paras):
            out.append(cur)
            cur, size = [], 0
        cur.append(p)
        size += n
    if cur:
        out.append(cur)
    return out


def _zone_line(doc: CaseDocument, z: Zone) -> str:
    agrees = f"; agrees with {', '.join(z.agrees_with)}" if z.agrees_with else ""
    return (f"{z.zone_id}: {' & '.join(z.judges)} | role={z.role} | paras {z.span or '-'} | "
            f"supported by {len(z.supported_by)}/{len(doc.coram) or '?'} judges{agrees}")


def _majority_threshold(doc: CaseDocument) -> int:
    n = len(doc.coram) or 5
    return n // 2 + 1


def _orders_text(doc: CaseDocument) -> str:
    zones = [z for z in doc.zones if z.role in {"order", "committee"}]
    paras = [p for z in zones for p in doc.zone_paragraphs(z.zone_id)]
    lead = doc.lead_zones
    if lead:
        lp = doc.zone_paragraphs(lead[0].zone_id)
        paras += lp[-3:]
    seen, out = set(), []
    for p in paras:
        if p.number not in seen:
            seen.add(p.number)
            out.append(_fmt_para(p, 2500))
    return "\n\n".join(out)[:12000]


_FACT_HEAD = re.compile(r"\b(?:fact|background|introduction|the\s+proceedings|the\s+dispute|the\s+charge|"
                        r"the\s+evidence|events|history|the\s+appeal|overview)\b", re.I)


def _facts_text(doc: CaseDocument, budget: int = 16000) -> str:
    lead = doc.lead_zones[0] if doc.lead_zones else (doc.zones[0] if doc.zones else None)
    if lead is None:
        return ""
    paras = doc.zone_paragraphs(lead.zone_id)
    chosen = [p for p in paras if p.heading_path and _FACT_HEAD.search(" ".join(p.heading_path))]
    if len(chosen) < 4:
        chosen = paras[:14]
    out, size = [], 0
    for p in chosen:
        t = _fmt_para(p, 3000)
        if size + len(t) > budget:
            break
        out.append(t)
        size += len(t)
    return "\n\n".join(out)


# ---------------------------------------------------------------------------
# Stages
# ---------------------------------------------------------------------------

SPEAKING_ROLES = {"lead", "joint_lead", "committee", "concurring_separate", "dissent", "order", "substantive"}


def build_inventory(doc: CaseDocument, llm: JSONModel, workers: int = 4) -> tuple[list[Item], list[str]]:
    warnings: list[str] = []
    jobs: list[tuple[Zone, list[Para]]] = []
    for z in doc.zones:
        if z.role not in SPEAKING_ROLES:
            continue
        paras = doc.zone_paragraphs(z.zone_id)
        for chunk in _chunks(paras):
            jobs.append((z, chunk))

    def run(job: tuple[Zone, list[Para]]) -> list[dict[str, Any]]:
        z, chunk = job
        user = (
            f"Case: {doc.neutral_citation} {doc.case_title or ''}\n"
            f"Court level: {doc.court_level}\n"
            f"Zone: {_zone_line(doc, z)}\n"
            "Zone map of the whole judgment:\n" + "\n".join(_zone_line(doc, x) for x in doc.zones) +
            "\n\nParagraphs of this zone:\n\n" + "\n\n".join(_fmt_para(p) for p in chunk)
        )
        res = llm.complete_json(system=INVENTORY_SYSTEM, user=user, schema=INVENTORY_SCHEMA,
                                name="lp_cp_inventory", max_tokens=4000)
        out = []
        for it in res.get("items", []):
            it["_zone"] = z
            it["_allowed"] = {p.number for p in chunk}
            out.append(it)
        return out

    with ThreadPoolExecutor(max_workers=workers) as ex:
        results = list(ex.map(run, jobs))

    items: list[Item] = []
    lp = cp = 0
    for batch in results:
        for raw in batch:
            z: Zone = raw["_zone"]
            num = raw["paragraph"]
            para = doc.para(num)
            if para is None or num not in raw["_allowed"]:
                warnings.append(f"Dropped item citing paragraph {num} outside zone {z.zone_id}.")
                continue
            pin = verify_quote(para, raw["quote"])
            if not pin.verified:
                # second chance: the quote may sit in an adjacent paragraph of the same zone
                for alt in (num - 1, num + 1):
                    ap = doc.para(alt)
                    if ap and ap.zone_id == z.zone_id:
                        alt_pin = verify_quote(ap, raw["quote"])
                        if alt_pin.verified:
                            para, pin = ap, alt_pin
                            break
            if not pin.verified:
                warnings.append(f"Dropped unverifiable quote at [{num}] ({raw['kind']}).")
                continue
            if raw["kind"] == "legal_principle":
                lp += 1
                iid = f"LP{lp}"
            else:
                cp += 1
                iid = f"CP{cp}"
            items.append(Item(
                item_id=iid, kind=raw["kind"], zone_id=z.zone_id, zone_judges=list(z.judges),
                zone_role=z.role, paragraph=para.number, heading_path=list(para.heading_path),
                quote=raw["quote"].strip(), statement=raw["statement"].strip(), issue=raw["issue"].strip(),
                status=raw["status"], pinpoint=pin.label(doc.neutral_citation), quote_verified=True,
            ))
    items.sort(key=lambda i: (i.paragraph, i.kind))
    return items, warnings


def build_combos(doc: CaseDocument, items: list[Item], llm: JSONModel) -> tuple[list[dict[str, Any]], list[Combo], list[str]]:
    warnings: list[str] = []
    if not items:
        return [], [], ["No verified LP/CP items; no combos built."]
    lines = []
    for it in items:
        q = it.quote if len(it.quote) < 400 else it.quote[:400] + "..."
        lines.append(f"{it.item_id} | {it.kind} | {it.zone_id} | [{it.paragraph}] | {it.status} | issue: {it.issue}\n"
                     f"   statement: {it.statement}\n   quote: \"{q}\"")
    outline = "\n".join(f"{h.zone_id} {'  ' * (h.level - 1)}{h.title}" for h in doc.headings)[:6000]
    user = (
        f"Case: {doc.neutral_citation} {doc.case_title or ''}\nCourt level: {doc.court_level}\n"
        f"Bench outcome: {doc.bench_outcome}; dissenting: {', '.join(doc.dissenting_judges) or 'none detected'}\n"
        "Zone map:\n" + "\n".join(_zone_line(doc, z) for z in doc.zones) +
        f"\n\nHeadings outline:\n{outline}\n\nOrders / dispositive paragraphs:\n{_orders_text(doc)}\n\n"
        "Inventory:\n" + "\n".join(lines)
    )
    res = llm.complete_json(system=COMBO_SYSTEM, user=user[:120000], schema=COMBO_SCHEMA,
                            name="combo_matcher", max_tokens=4000)
    by_id = {i.item_id: i for i in items}
    combos: list[Combo] = []
    for n, c in enumerate(res.get("combos", []), start=1):
        pids = [x for x in c["principle_ids"] if x in by_id]
        qids = [x for x in c["position_ids"] if x in by_id]
        zones = {by_id[x].zone_id for x in pids + qids}
        if not qids:
            warnings.append(f"Combo {n} discarded: no valid court position id.")
            continue
        if len(zones) > 1:
            warnings.append(f"Combo {n} discarded: mixed zones {sorted(zones)} (zone integrity rule).")
            continue
        zone_id = zones.pop()
        paras = sorted({by_id[x].paragraph for x in pids + qids})
        combos.append(Combo(
            combo_id=f"C{len(combos) + 1}", issue_id=c["issue_id"], zone_id=zone_id,
            principle_ids=pids, position_ids=qids, ratio_statement=c["ratio_statement"].strip(),
            classification=c["classification"], reasoning=c["reasoning"].strip(), paragraphs=paras,
        ))
    return res.get("core_issues", []), combos, warnings


def trial_test(doc: CaseDocument, combos: list[Combo], items: list[Item], llm: JSONModel) -> list[str]:
    warnings: list[str] = []
    if not combos:
        return warnings
    by_id = {i.item_id: i for i in items}
    facts = _facts_text(doc)
    orders = _orders_text(doc)
    for start in range(0, len(combos), 6):
        batch = combos[start:start + 6]
        desc = []
        for c in batch:
            z = doc.zone(c.zone_id)
            ev = "; ".join(f"{x} [{by_id[x].paragraph}] \"{by_id[x].quote[:300]}\"" for x in c.principle_ids + c.position_ids)
            desc.append(f"{c.combo_id} | zone {c.zone_id} ({z.role if z else '?'}: {' & '.join(z.judges) if z else '?'}) | "
                        f"classification proposed: {c.classification}\n  ratio: {c.ratio_statement}\n  evidence: {ev}")
        user = (
            f"Case: {doc.neutral_citation} {doc.case_title or ''}\nCourt level: {doc.court_level}\n"
            "Zone map:\n" + "\n".join(_zone_line(doc, z) for z in doc.zones) +
            f"\n\nMaterial facts (from the lead zone):\n{facts}\n\nOrders / disposition:\n{orders}\n\n"
            "Combos to test:\n" + "\n\n".join(desc)
        )
        res = llm.complete_json(system=TRIAL_SYSTEM, user=user, schema=TRIAL_SCHEMA,
                                name="trial_test", max_tokens=4000)
        by_combo = {t["combo_id"]: t for t in res.get("tests", [])}
        for c in batch:
            t = by_combo.get(c.combo_id)
            if not t:
                warnings.append(f"Trial test missing for {c.combo_id}.")
                continue
            c.material_facts_applied = t["material_facts_applied"]
            c.predicted_outcome = t["predicted_outcome"]
            c.actual_outcome = t["actual_outcome"]
            c.consistent_with_outcome = bool(t["consistent_with_outcome"])
            c.inversion_changes_outcome = bool(t["inversion_changes_outcome"])
            c.logically_intolerable = bool(t["logically_intolerable"])
            c.intolerability_reason = t["intolerability_reason"]
            c.confidence = float(t["confidence"])
            c.test_explanation = t["explanation"]
            if t.get("refined_ratio") and t["verdict"] == "TRUE_RATIO" and t["refined_ratio"].strip():
                c.ratio_statement = t["refined_ratio"].strip()
            c.verdict = t["verdict"]
    # deterministic gates -------------------------------------------------
    threshold = _majority_threshold(doc)
    for c in combos:
        z = doc.zone(c.zone_id)
        support = len(z.supported_by) if z else 0
        if z is None:
            c.authority_gate = "FAIL: unknown zone"
        elif z.role == "dissent":
            c.authority_gate = "FAIL: dissenting zone"
        elif z.role == "committee":
            c.authority_gate = f"PASS: Appeal Committee / Court ruling ({support} judges)"
        elif support >= threshold:
            c.authority_gate = f"PASS: majority support {support}/{len(doc.coram) or '?'}"
        else:
            c.authority_gate = f"FAIL: support {support}/{len(doc.coram) or '?'} below majority {threshold}"
        if c.verdict == "TRUE_RATIO":
            if c.authority_gate.startswith("FAIL"):
                # dissent -> minority view; separate concurrence without majority
                # support -> concurring view (persuasive, supports the result, not binding)
                c.verdict = "MINORITY_VIEW" if (z is None or z.role == "dissent") else "CONCURRING_VIEW"
            elif c.logically_intolerable or c.consistent_with_outcome is False:
                c.verdict = "FAILED_INTOLERABLE"
            elif c.classification == "obiter":
                c.verdict = "OBITER"
    return warnings


def build_summary(doc: CaseDocument, result_core: list[dict[str, Any]], combos: list[Combo], items: list[Item],
                  llm: JSONModel) -> dict[str, Any]:
    by_id = {i.item_id: i for i in items}
    true = [c for c in combos if c.verdict == "TRUE_RATIO"]
    obiter = [c for c in combos if c.verdict in {"OBITER", "NOT_NECESSARY"} or c.classification == "obiter"]
    dissent_items = [i for i in items if i.zone_role == "dissent"]
    user = (
        f"Case: {doc.neutral_citation} {doc.case_title or ''}\nAction no.: {', '.join(doc.action_numbers)}\n"
        f"Court level: {doc.court_level}\nDates: {json.dumps(doc.dates)}\nCoram: {', '.join(doc.coram)}\n"
        f"Bench outcome: {doc.bench_outcome}; dissenting: {', '.join(doc.dissenting_judges) or 'none'}\n"
        "Zone map:\n" + "\n".join(_zone_line(doc, z) for z in doc.zones) +
        "\n\nCore issues:\n" + "\n".join(f"{x['issue_id']}: {x['question']} -> {x['answer']}" for x in result_core) +
        "\n\nVerified true ratios:\n" + "\n".join(f"{c.combo_id} ({c.zone_id}, paras {c.paragraphs}): {c.ratio_statement}" for c in true) +
        "\n\nObiter combos:\n" + "\n".join(f"{c.combo_id} paras {c.paragraphs}: {c.ratio_statement}" for c in obiter) +
        "\n\nDissenting-zone items:\n" + "\n".join(f"{i.item_id} {i.zone_judges} [{i.paragraph}]: {i.statement}" for i in dissent_items[:30]) +
        f"\n\nOrders:\n{_orders_text(doc)}\n\nFacts:\n{_facts_text(doc, 8000)}\n\n"
        "Provide ratio_zh for every verified true ratio combo id listed above."
    )
    _ = by_id
    return llm.complete_json(system=SUMMARY_SYSTEM, user=user, schema=SUMMARY_SCHEMA, name="case_summary",
                             max_tokens=4000)


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


def analyse_judgment(raw: str, llm: JSONModel, *, source_url: str | None = None,
                     source_description: str = "operator-supplied judgment", case_title: str | None = None) -> CaseResult:
    doc = parse_judgment(raw, case_title=case_title)
    warnings = list(doc.warnings)
    items, w = build_inventory(doc, llm)
    warnings += w
    core, combos, w = build_combos(doc, items, llm)
    warnings += w
    warnings += trial_test(doc, combos, items, llm)
    summary = build_summary(doc, core, combos, items, llm) if combos else {}
    zh = {r["combo_id"]: r["ratio_zh"] for r in summary.get("ratio_zh", [])} if summary else {}
    for c in combos:
        c.ratio_zh = zh.get(c.combo_id, "")
    # who made the ratio
    makers = []
    for c in combos:
        if c.verdict == "TRUE_RATIO":
            z = doc.zone(c.zone_id)
            if z:
                makers.append({"combo_id": c.combo_id, "author_zone": c.zone_id, "authors": z.judges,
                               "concurred_by": [j for j in z.supported_by if j not in z.judges]})
    if summary:
        summary["ratio_makers"] = makers
    return CaseResult(
        neutral_citation=doc.neutral_citation, case_title=doc.case_title, action_numbers=doc.action_numbers,
        court_level=doc.court_level, proceeding_type=doc.proceeding_type, dates=doc.dates,
        primary_date=doc.primary_date, coram=doc.coram, bench_outcome=doc.bench_outcome,
        dissenting_judges=doc.dissenting_judges,
        zones=[{"zone_id": z.zone_id, "judges": z.judges, "role": z.role, "span": z.span,
                "paragraph_count": len(z.paragraph_numbers), "agrees_with": z.agrees_with,
                "supported_by": z.supported_by, "header": z.header} for z in doc.zones],
        headings=[f"{h.zone_id} {h.title}" for h in doc.headings],
        issues=core, items=items, combos=combos, summary=summary, warnings=warnings,
        provenance={"source_description": source_description, "source_url": source_url,
                    "sha256": sha256(raw.encode("utf-8")).hexdigest(),
                    "processed_at": datetime.now(UTC).isoformat(), "pipeline_version": PIPELINE_VERSION,
                    "model": getattr(llm, "model", "injected")},
    )
