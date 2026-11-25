from __future__ import annotations

from pathlib import Path

from legalless.excel import export_app_dataset, export_workbook
from legalless.ratio import analyse_judgment, verify_quote
from legalless.structure import Para, parse_judgment

FIXTURES = Path(__file__).parent / "fixtures"
MULTI = (FIXTURES / "synthetic_multizone.md").read_text(encoding="utf-8")
LEAVE = (FIXTURES / "synthetic_leave.md").read_text(encoding="utf-8")


# --------------------------------------------------------------------------- structure


def test_front_matter_and_dates():
    doc = parse_judgment(MULTI)
    assert doc.neutral_citation == "[2030] HKCFA 99"
    assert "FACV 99/2030" in doc.action_numbers
    assert doc.dates == {"hearing": "2030-03-03", "judgment": "2030-04-01"}
    assert len(doc.coram) == 5
    assert doc.proceeding_type == "substantive_appeal"


def test_zones_lead_concurrence_dissent_order():
    doc = parse_judgment(MULTI)
    roles = {z.zone_id: (z.judges, z.role) for z in doc.zones}
    assert roles["Z1"][1] == "concurring_agree"
    assert roles["Z2"][1] == "joint_lead"
    assert roles["Z2"][0] == ["Mr Justice Able PJ", "Mr Justice Baker PJ"]
    assert roles["Z3"][1] == "dissent"
    assert roles["Z4"][1] == "concurring_agree"
    assert roles["Z5"][1] == "order"
    lead = doc.zone("Z2")
    assert len(lead.supported_by) == 4  # Able, Baker + Chief Justice + Lord Dalton
    assert doc.bench_outcome == "majority"
    assert doc.dissenting_judges == ["Madam Justice Cole PJ"]


def test_headings_attach_to_paragraphs():
    doc = parse_judgment(MULTI)
    assert doc.para(4).heading_path == ["C The legal principle"]
    assert doc.para(4).zone_id == "Z2"
    assert doc.para(7).zone_id == "Z3"


def test_leave_determination_is_committee_zone():
    doc = parse_judgment(LEAVE)
    assert doc.proceeding_type == "leave_application"
    assert doc.court_level.startswith("Court of Final Appeal – Appeal Committee")
    assert doc.dates["hearing_and_determination"] == "2031-06-09"
    assert doc.zones[0].role == "committee"
    assert len(doc.zones[0].supported_by) == 3


# --------------------------------------------------------------------------- verbatim quotes


def test_verify_quote_exact_ellipsis_and_reject():
    p = Para(4, "In our judgment, a requirement that notice be “given” is satisfied by delivery. It is not otherwise.", "Z2")
    assert verify_quote(p, 'a requirement that notice be "given" is satisfied').verified
    pin = verify_quote(p, "In our judgment ... satisfied by delivery")
    assert pin.verified and pin.method == "ellipsis" and pin.sentence_from == 1
    assert verify_quote(p, "It is not otherwise").sentence_from == 2
    assert not verify_quote(p, "notice must be served personally").verified


# --------------------------------------------------------------------------- pipeline with a fake model


class FakeLLM:
    model = "fake"

    def complete_json(self, *, system, user, schema, name, max_tokens=4000):
        if name == "lp_cp_inventory":
            if "Zone: Z2" in user:
                return {"items": [
                    {"kind": "legal_principle", "paragraph": 4, "quote": "a contractual requirement that notice be \"given\" is satisfied by delivery to the registered office",
                     "statement": "Notice is given by delivery to the registered office.", "issue": "notice", "status": "stated_as_law"},
                    {"kind": "court_position", "paragraph": 5, "quote": "the notice posted on 1 May 2028 was validly given",
                     "statement": "The notice was valid.", "issue": "notice", "status": "applied_to_facts"},
                    {"kind": "court_position", "paragraph": 5, "quote": "this sentence is not in the judgment",
                     "statement": "fabricated", "issue": "notice", "status": "applied_to_facts"},
                ]}
            if "Zone: Z3" in user:
                return {"items": [
                    {"kind": "court_position", "paragraph": 7, "quote": "personal service was required by the course of dealing between the parties",
                     "statement": "Personal service required.", "issue": "notice", "status": "applied_to_facts"},
                ]}
            return {"items": []}
        if name == "combo_matcher":
            return {"core_issues": [{"issue_id": "I1", "question": "Was notice validly given?", "answer": "Yes"}],
                    "combos": [
                        {"issue_id": "I1", "zone_id": "Z2", "principle_ids": ["LP1"], "position_ids": ["CP1"],
                         "ratio_statement": "Notice is given by delivery to the registered office absent express terms.",
                         "classification": "candidate_ratio", "reasoning": "decisive"},
                        {"issue_id": "I1", "zone_id": "Z3", "principle_ids": [], "position_ids": ["CP2"],
                         "ratio_statement": "Personal service required by course of dealing.",
                         "classification": "dissenting_view", "reasoning": "dissent"},
                        {"issue_id": "I1", "zone_id": "Z2", "principle_ids": ["LP1"], "position_ids": ["CP2"],
                         "ratio_statement": "mixed", "classification": "candidate_ratio", "reasoning": "bad"},
                    ]}
        if name == "trial_test":
            tests = []
            for cid in ("C1", "C2"):
                if cid in user:
                    tests.append({"combo_id": cid, "material_facts_applied": "posted notice", "predicted_outcome": "allowed",
                                  "actual_outcome": "allowed", "consistent_with_outcome": cid == "C1",
                                  "inversion_changes_outcome": True, "logically_intolerable": False,
                                  "intolerability_reason": "", "verdict": "TRUE_RATIO", "refined_ratio": "",
                                  "confidence": 0.9, "explanation": "test"})
            return {"tests": tests}
        if name == "case_summary":
            return {"core_issue_en": "notice", "core_issue_zh": "通知", "final_result_en": "allowed",
                    "final_result_zh": "上訴得直", "summary_en": "s", "summary_zh": "摘要", "obiter": [],
                    "dissent": [{"judge": "Madam Justice Cole PJ", "paragraphs": "[7]", "note_en": "d", "note_zh": "異議"}],
                    "ratio_zh": [{"combo_id": "C1", "ratio_zh": "通知送達註冊辦事處即屬有效。"}]}
        raise AssertionError(name)


def test_pipeline_gates_and_exports(tmp_path):
    result = analyse_judgment(MULTI, FakeLLM())
    # fabricated quote dropped; cross-zone combo discarded
    assert [i.item_id for i in result.items] == ["LP1", "CP1", "CP2"]
    assert any("unverifiable" in w for w in result.warnings)
    assert any("mixed zones" in w for w in result.warnings)
    verdicts = {c.combo_id: c.verdict for c in result.combos}
    assert verdicts == {"C1": "TRUE_RATIO", "C2": "MINORITY_VIEW"}  # dissent cannot be ratio
    c1 = result.combos[0]
    assert c1.authority_gate.startswith("PASS") and c1.ratio_zh
    assert result.summary["ratio_makers"][0]["authors"] == ["Mr Justice Able PJ", "Mr Justice Baker PJ"]
    case = result.to_dict()
    xlsx = export_workbook([case], tmp_path / "out.xlsx")
    app = export_app_dataset([case], tmp_path / "app.json")
    assert xlsx.exists() and app.exists()
