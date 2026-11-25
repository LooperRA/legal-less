"""Excel export of ratio pipeline results (one workbook for any number of cases)."""
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from openpyxl import Workbook
from openpyxl.formatting.rule import CellIsRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

INK = "1F2A44"
GOLD = "B08D57"
PALE = "F4F1EA"
THIN = Side(style="thin", color="D0CCC2")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
HEAD_FONT = Font(name="Calibri", bold=True, color="FFFFFF", size=11)
HEAD_FILL = PatternFill("solid", fgColor=INK)
WRAP = Alignment(wrap_text=True, vertical="top")
VERDICT_FILLS = {
    "TRUE_RATIO": "D8EAD3", "OBITER": "FFF2CC", "NOT_NECESSARY": "FCE5CD",
    "FAILED_INTOLERABLE": "F4CCCC", "MINORITY_VIEW": "D9D2E9", "CONCURRING_VIEW": "DDEBF7", "UNTESTED": "EEEEEE",
}


def _sheet(wb: Workbook, title: str, headers: list[tuple[str, int]], rows: list[list[Any]], *,
           verdict_col: int | None = None):
    ws = wb.create_sheet(title)
    for c, (h, w) in enumerate(headers, start=1):
        cell = ws.cell(row=1, column=c, value=h)
        cell.font, cell.fill, cell.alignment, cell.border = HEAD_FONT, HEAD_FILL, Alignment(wrap_text=True, vertical="center"), BORDER
        ws.column_dimensions[get_column_letter(c)].width = w
    for r, row in enumerate(rows, start=2):
        for c, v in enumerate(row, start=1):
            if isinstance(v, (list, dict)):
                v = json.dumps(v, ensure_ascii=False) if isinstance(v, dict) else "; ".join(map(str, v))
            cell = ws.cell(row=r, column=c, value=v)
            cell.alignment, cell.border = WRAP, BORDER
            if r % 2 == 0:
                cell.fill = PatternFill("solid", fgColor=PALE)
    ws.freeze_panes = "C2" if len(headers) > 3 else "A2"
    ws.row_dimensions[1].height = 32
    if rows:
        ws.auto_filter.ref = f"A1:{get_column_letter(len(headers))}{len(rows) + 1}"
    if verdict_col and rows:
        col = get_column_letter(verdict_col)
        for verdict, color in VERDICT_FILLS.items():
            ws.conditional_formatting.add(
                f"{col}2:{col}{len(rows) + 1}",
                CellIsRule(operator="equal", formula=[f'"{verdict}"'], fill=PatternFill("solid", fgColor=color),
                           font=Font(bold=True)))
    return ws


def _items_index(case: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {i["item_id"]: i for i in case.get("items", [])}


def _evidence(case: dict[str, Any], ids: list[str]) -> str:
    idx = _items_index(case)
    out = []
    for x in ids:
        it = idx.get(x)
        if it:
            out.append(f"{x} {it['pinpoint']}: “{it['quote']}”")
    return "\n".join(out)


def load_results(results_dir: str | Path) -> list[dict[str, Any]]:
    cases = []
    for p in sorted(Path(results_dir).glob("*.json")):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict) and "combos" in data:
            cases.append(data)

    def key(c: dict[str, Any]) -> tuple[int, int]:
        cit = c.get("neutral_citation") or "[0] HKCFA 0"
        try:
            y = int(cit.split("]")[0].strip("["))
            n = int(cit.rsplit(" ", 1)[-1])
        except ValueError:
            y, n = 0, 0
        return (-y, -n)

    return sorted(cases, key=key)


def export_workbook(cases: list[dict[str, Any]], path: str | Path) -> Path:
    wb = Workbook()
    ws = wb.active
    ws.title = "Read Me"
    generated = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    n_true = sum(1 for c in cases for x in c["combos"] if x["verdict"] == "TRUE_RATIO")
    lines = [
        ("legal-less v0.2 – HKCFA Ratio Decidendi Register / 終審法院裁定理由登記冊", True),
        ("Formula / 方程式: LEGAL PRINCIPLE + COURT POSITION = RATIO DECIDENDI（法律原則 + 法院立場 = 裁定理由）", True),
        (f"Generated / 製備日期: {generated}    Cases / 案件數目: {len(cases)}    Verified true ratios / 經核實裁定理由: {n_true}", False),
        ("", False),
        ("Pipeline / 流程", True),
        ("1. Structure: headings, sub-headings, numbered paragraphs, judge zones (lead / joint lead / Appeal Committee / concurring / dissent / order).", False),
        ("2. Inventory: every legal principle (LP) and court position (CP) per zone, each with a verbatim quote machine-verified against the paragraph and a pinpoint (paragraph and sentence).", False),
        ("3. Combination: LP + CP combos matched by issue within one zone only (zone integrity rule – no cross-zone mixing).", False),
        ("4. Trial test: each combo applied to the case's own material facts; consistency with outcome, inversion (necessity) test and logical-intolerability test; then a deterministic authority gate (majority of the bench or Appeal Committee ruling).", False),
        ("5. Only combos surviving every test carry the verdict TRUE_RATIO. Leave-stage (Appeal Committee) rulings are analysed and can yield ratio.", False),
        ("", False),
        ("Verdict legend / 判定圖例", True),
        ("TRUE_RATIO – survived all tests (裁定理由) | OBITER – not necessary / left open (附帶意見) | NOT_NECESSARY – outcome would not change | FAILED_INTOLERABLE – inconsistent or logically intolerable | MINORITY_VIEW – dissenting zone (少數意見) | CONCURRING_VIEW – separate concurrence without majority support; persuasive only (協同意見)", False),
        ("", False),
        ("Caveats / 注意事項", True),
        ("Machine-assisted analysis. Verbatim quotes are programmatically checked against the source text supplied; legal characterisation (ratio / obiter) is model-assisted and must be reviewed by a qualified lawyer before reliance. Pinpoints refer to paragraph numbers of the judgment as published on HKLII; sentence numbers are counted within the paragraph.", False),
        ("Chinese text is a working translation for access-to-justice purposes and is not an official translation of the judgment.", False),
        ("Sheets: Case Summary | True Ratio | Combos & Trial Test | Legal Principles | Court Positions | Zones | Obiter & Dissent | Data Quality", False),
    ]
    for r, (text, bold) in enumerate(lines, start=1):
        cell = ws.cell(row=r, column=1, value=text)
        cell.alignment = Alignment(wrap_text=True, vertical="top")
        cell.font = Font(bold=bold, size=13 if r == 1 else 11, color=INK if bold else "000000")
    ws.column_dimensions["A"].width = 150

    # Case Summary -----------------------------------------------------------
    rows = []
    for c in cases:
        s = c.get("summary") or {}
        makers = s.get("ratio_makers", [])
        maker_txt = "\n".join(
            f"{m['combo_id']}: {' & '.join(m['authors'])}" + (f" (concurred: {', '.join(m['concurred_by'])})" if m["concurred_by"] else "")
            for m in makers)
        true = [x for x in c["combos"] if x["verdict"] == "TRUE_RATIO"]
        rows.append([
            c.get("neutral_citation"), c.get("case_title"), ", ".join(c.get("action_numbers", [])),
            c.get("court_level"), c.get("proceeding_type"), c.get("primary_date"),
            "; ".join(f"{k}: {v}" for k, v in (c.get("dates") or {}).items()),
            ", ".join(c.get("coram", [])), c.get("bench_outcome"), ", ".join(c.get("dissenting_judges", [])) or "None",
            maker_txt, s.get("core_issue_en", ""), s.get("core_issue_zh", ""),
            "\n\n".join(f"{x['combo_id']} {x['paragraphs']}: {x['ratio_statement']}" for x in true),
            "\n\n".join(f"{x['combo_id']}: {x.get('ratio_zh', '')}" for x in true),
            s.get("final_result_en", ""), s.get("final_result_zh", ""),
            "\n".join(f"{o['paragraphs']}: {o['note_en']}" for o in s.get("obiter", [])),
            "\n".join(f"{d['judge']} {d['paragraphs']}: {d['note_en']}" for d in s.get("dissent", [])) or "None",
            s.get("summary_en", ""), s.get("summary_zh", ""), len(true),
        ])
    _sheet(wb, "Case Summary", [
        ("Neutral citation", 16), ("Case", 30), ("Action no.", 16), ("Court level", 24), ("Proceeding", 16),
        ("Date (reasons/judgment)", 14), ("All dates", 26), ("Coram", 34), ("Bench", 11), ("Dissenting", 18),
        ("Ratio made by", 30), ("Core issue (EN)", 45), ("核心爭議 (中)", 40), ("True ratio (EN) [paras]", 60),
        ("裁定理由 (中)", 50), ("Final result (EN)", 40), ("最終結果 (中)", 36), ("Obiter (EN)", 50),
        ("Dissenting comments (EN)", 45), ("Summary (EN)", 60), ("案情摘要 (中)", 50), ("No. true ratios", 9),
    ], rows)

    # True Ratio --------------------------------------------------------------
    rows = []
    for c in cases:
        issues = {i["issue_id"]: i["question"] for i in c.get("issues", [])}
        zones = {z["zone_id"]: z for z in c.get("zones", [])}
        for x in c["combos"]:
            if x["verdict"] != "TRUE_RATIO":
                continue
            z = zones.get(x["zone_id"], {})
            rows.append([
                c.get("neutral_citation"), c.get("case_title"), x["combo_id"], issues.get(x["issue_id"], x["issue_id"]),
                x["ratio_statement"], x.get("ratio_zh", ""), " & ".join(z.get("judges", [])), z.get("role"),
                ", ".join(f"[{p}]" for p in x["paragraphs"]),
                _evidence(c, x["principle_ids"]), _evidence(c, x["position_ids"]),
                x["authority_gate"], x["test_explanation"], x["confidence"], x["verdict"],
            ])
    _sheet(wb, "True Ratio", [
        ("Neutral citation", 16), ("Case", 28), ("Combo", 8), ("Issue", 40), ("Ratio decidendi (EN)", 60),
        ("裁定理由 (中)", 50), ("Made by", 28), ("Zone role", 12), ("Paras", 16),
        ("Legal principle – verbatim with pinpoint", 70), ("Court position – verbatim with pinpoint", 70),
        ("Authority gate", 26), ("Trial-test reasoning", 60), ("Confidence", 10), ("Verdict", 14),
    ], rows, verdict_col=15)

    # Combos & Trial Test ----------------------------------------------------
    rows = []
    for c in cases:
        for x in c["combos"]:
            rows.append([
                c.get("neutral_citation"), x["combo_id"], x["zone_id"], x["issue_id"], x["classification"],
                x["ratio_statement"], ", ".join(x["principle_ids"]), ", ".join(x["position_ids"]),
                ", ".join(f"[{p}]" for p in x["paragraphs"]), x["material_facts_applied"], x["predicted_outcome"],
                x["actual_outcome"], x["consistent_with_outcome"], x["inversion_changes_outcome"],
                x["logically_intolerable"], x["intolerability_reason"], x["authority_gate"], x["confidence"],
                x["verdict"], x["test_explanation"],
            ])
    _sheet(wb, "Combos & Trial Test", [
        ("Neutral citation", 16), ("Combo", 8), ("Zone", 7), ("Issue", 7), ("Proposed class", 15),
        ("Ratio candidate", 55), ("LP ids", 12), ("CP ids", 12), ("Paras", 16), ("Material facts applied", 45),
        ("Outcome produced by ratio", 40), ("Actual outcome", 40), ("Consistent?", 11), ("Inversion changes outcome?", 12),
        ("Logically intolerable?", 12), ("Intolerability reason", 35), ("Authority gate", 26), ("Confidence", 10),
        ("Verdict", 14), ("Explanation", 55),
    ], rows, verdict_col=19)

    for kind, title in (("legal_principle", "Legal Principles"), ("court_position", "Court Positions")):
        rows = []
        for c in cases:
            for it in c.get("items", []):
                if it["kind"] != kind:
                    continue
                rows.append([c.get("neutral_citation"), it["item_id"], it["zone_id"], " & ".join(it["zone_judges"]),
                             it["zone_role"], f"[{it['paragraph']}]", " > ".join(it["heading_path"]), it["issue"],
                             it["status"], it["quote"], it["pinpoint"], it["statement"],
                             "Yes" if it["quote_verified"] else "No"])
        _sheet(wb, title, [
            ("Neutral citation", 16), ("Id", 7), ("Zone", 7), ("Judge(s)", 28), ("Zone role", 14), ("Para", 7),
            ("Heading path", 34), ("Issue", 30), ("Status", 18), ("Verbatim quote", 70), ("Pinpoint", 28),
            ("Restatement", 50), ("Quote verified", 9),
        ], rows)

    rows = []
    for c in cases:
        for z in c.get("zones", []):
            rows.append([c.get("neutral_citation"), z["zone_id"], " & ".join(z["judges"]), z["role"], z["span"],
                         z["paragraph_count"], ", ".join(z["agrees_with"]), ", ".join(z["supported_by"]), z["header"]])
    _sheet(wb, "Zones", [("Neutral citation", 16), ("Zone", 7), ("Judge(s)", 34), ("Role", 18), ("Paragraphs", 14),
                         ("Count", 8), ("Agrees with", 12), ("Supported by", 60), ("Header in judgment", 40)], rows)

    rows = []
    for c in cases:
        s = c.get("summary") or {}
        for o in s.get("obiter", []):
            rows.append([c.get("neutral_citation"), "Obiter / 附帶意見", "", o["paragraphs"], o["note_en"], o["note_zh"]])
        for d in s.get("dissent", []):
            rows.append([c.get("neutral_citation"), "Dissent / 異議", d["judge"], d["paragraphs"], d["note_en"], d["note_zh"]])
    _sheet(wb, "Obiter & Dissent", [("Neutral citation", 16), ("Type", 16), ("Judge", 24), ("Paras", 16),
                                    ("Note (EN)", 70), ("說明 (中)", 60)], rows)

    rows = []
    for c in cases:
        p = c.get("provenance", {})
        rows.append([c.get("neutral_citation"), len(c.get("items", [])), len(c.get("combos", [])),
                     sum(1 for x in c["combos"] if x["verdict"] == "TRUE_RATIO"), len(c.get("warnings", [])),
                     "\n".join(c.get("warnings", [])[:15]), p.get("model"), p.get("pipeline_version"),
                     p.get("processed_at"), p.get("sha256")])
    _sheet(wb, "Data Quality", [("Neutral citation", 16), ("LP+CP items", 10), ("Combos", 9), ("True ratios", 9),
                                ("Warnings", 9), ("Warning detail", 70), ("Model", 14), ("Pipeline", 9),
                                ("Processed at", 24), ("Input SHA-256", 66)], rows)

    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    wb.save(out)
    return out


def export_app_dataset(cases: list[dict[str, Any]], path: str | Path) -> Path:
    """Compact JSON consumed by the mobile app (no raw judgment text)."""
    slim = []
    for c in cases:
        s = c.get("summary") or {}
        idx = _items_index(c)
        issues = {i["issue_id"]: i for i in c.get("issues", [])}
        zones = {z["zone_id"]: z for z in c.get("zones", [])}

        def ev(ids: list[str], _idx: dict[str, Any] = idx) -> list[dict[str, Any]]:
            return [{"id": i, "para": _idx[i]["paragraph"], "pinpoint": _idx[i]["pinpoint"], "quote": _idx[i]["quote"]}
                    for i in ids if i in _idx]

        slim.append({
            "citation": c.get("neutral_citation"), "title": c.get("case_title"), "actions": c.get("action_numbers"),
            "courtLevel": c.get("court_level"), "proceeding": c.get("proceeding_type"), "date": c.get("primary_date"),
            "dates": c.get("dates"), "coram": c.get("coram"), "bench": c.get("bench_outcome"),
            "dissenting": c.get("dissenting_judges"),
            "coreIssue": {"en": s.get("core_issue_en", ""), "zh": s.get("core_issue_zh", "")},
            "result": {"en": s.get("final_result_en", ""), "zh": s.get("final_result_zh", "")},
            "summary": {"en": s.get("summary_en", ""), "zh": s.get("summary_zh", "")},
            "obiter": s.get("obiter", []), "dissent": s.get("dissent", []),
            "zones": [{"id": z["zone_id"], "judges": z["judges"], "role": z["role"], "span": z["span"]} for z in c.get("zones", [])],
            "combos": [{
                "id": x["combo_id"], "verdict": x["verdict"], "issue": issues.get(x["issue_id"], {}).get("question", ""),
                "ratio": {"en": x["ratio_statement"], "zh": x.get("ratio_zh", "")}, "zone": x["zone_id"],
                "madeBy": zones.get(x["zone_id"], {}).get("judges", []), "paras": x["paragraphs"],
                "principles": ev(x["principle_ids"]), "positions": ev(x["position_ids"]),
                "test": {"facts": x["material_facts_applied"], "predicted": x["predicted_outcome"],
                         "actual": x["actual_outcome"], "consistent": x["consistent_with_outcome"],
                         "inversion": x["inversion_changes_outcome"], "intolerable": x["logically_intolerable"],
                         "authority": x["authority_gate"], "confidence": x["confidence"],
                         "explanation": x["test_explanation"]},
            } for x in c["combos"]],
        })
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"generated": datetime.now(UTC).isoformat(), "cases": slim}, ensure_ascii=False), encoding="utf-8")
    return out
