# Ratio Pipeline v0.2 — Zones, Combos and Trial Test

**Formula (proprietary to the project owner):**

> **Legal principle (LP) + Court position (CP) = Ratio decidendi**

Version 0.2 adds a model-assisted pipeline (`legal-less ratio …`) to the v0.1 deterministic paragraph scorer (`legal-less cfa …`, unchanged). It runs on one judgment at a time. The same steps repeat over a corpus with `ratio batch`.

| Stage | Module | Deterministic? | Output |
|---|---|---|---|
| 0. Structure | `structure.py` | Yes | Front matter, headings, paragraphs, judge zones |
| 1. Inventory | `ratio.py` (`extract_inventory`) | Model + programmatic quote check | Every LP and every CP, per zone |
| 2. Combos | `ratio.py` (`build_combos`) | Model + deterministic zone gate | LP+CP combos, each answering one issue |
| 3. Trial test | `ratio.py` (`trial_test`) | Model + deterministic authority gate | Verdict per combo |
| 4. Summary | `ratio.py` (`build_summary`) | Model | Bilingual case summary, ratio makers |
| 5. Export | `excel.py` | Yes | Excel register, app dataset |

## 0. Structure: headings and judge zones

The parser reads HKLII-style Markdown, HTML or API JSON and records the following:

- **Front matter:** neutral citation, action numbers, coram, every dated event (hearing, judgment, reasons for judgment, hearing and determination), case title.
- **Court level and proceeding type:** *Full Court (final appeal)* or *Appeal Committee (leave stage)*.
- **Heading paths:** every numbered paragraph carries the headings and sub-headings above it (e.g. `B. The statutory scheme › B.2 Section 14AA`), so a later stage cannot read a sentence out of its topical context.
- **Judge zones:** the judgment is split at each judge's heading (`Chief Justice Ma:`, `Mr Justice Ribeiro PJ and Mr Justice Fok PJ:` …). Each zone gets a role:

| Role | Meaning |
|---|---|
| `lead` / `joint_lead` | The principal judgment (one author or joint authors) |
| `concurring_agree` | "I agree with the judgment of …" — adopts another zone (`agrees_with`) |
| `concurring_separate` | Separate reasons that reach the same result |
| `dissent` | Detected from "X dissenting" in the front matter or order, and from the judge's own zone heading |
| `committee` | Appeal Committee determination (leave stage) |
| `order` | The formal order paragraph(s) |

`supported_by` lists every judge who adopts a zone. `bench_outcome` is `unanimous` or `majority`, and `dissenting_judges` is filled from the front matter or the order.

**Zone-integrity rule.** Every LP and CP belongs to exactly one zone. A combo may only join an LP and a CP **from the same zone** (cross-zone combos are discarded). So a dissenting judge's principle can never be paired with the majority's position, and a concurrence cannot be merged into the lead reasons.

## 1. Inventory: all legal principles and all court positions

Each zone is processed in chunks. The model must return each item with:

- `kind` (`legal_principle` / `court_position`), `paragraph`, `quote` (verbatim), `statement` (neutral restatement) and `issue`;
- **LP** = a general rule of law stated, adopted or applied by the judge (statute, precedent, constitutional provision, procedural rule);
- **CP** = the court's own determination on an issue — a holding, a finding, an acceptance or rejection of an argument, an answer to a question of law, or an order.

**Programmatic verification.** `verify_quote` checks that every quote appears verbatim in the cited paragraph. It allows ellipses and normalises quote glyphs and whitespace. Unverifiable quotes, and quotes outside the item's own zone, are **dropped** and logged in `warnings`. Pinpoints use the form `[2020] HKCFA 22 at [41] (s.B.2)`.

## 2. Combos

The model groups same-zone LPs and CPs into combos. Each combo answers one identified issue: **LP (rule) + CP (the court's determination applying it) → ratio statement**. Each combo records `principle_ids`, `position_ids`, `paragraphs`, `ratio_statement` (EN), `ratio_zh` (繁中) and a provisional `classification` (`candidate_ratio` / `obiter`).

## 3. Trial test and verification

Each combo is applied **back to the case's own material facts**:

1. **Consistency** — applying the ratio to the material facts must predict the actual outcome (`predicted_outcome` vs `actual_outcome`).
2. **Inversion (Wambaugh) test** — if the proposition were reversed, would the outcome change? If not, the proposition was not necessary to the decision → `NOT_NECESSARY`.
3. **Logical intolerability** — the ratio must not produce an outcome that is absurd or self-contradictory on those facts, or that contradicts the order actually made → `FAILED_INTOLERABLE`.
4. **Refinement** — a surviving ratio may be narrowed to the material facts (`refined_ratio`).
5. **Deterministic authority gate** (no model discretion):

| Zone | Gate |
|---|---|
| `committee` (Appeal Committee) | PASS — the Committee's ruling is the Court's ruling at leave stage |
| `lead` / `joint_lead` / separate zone supported by a majority of the coram | PASS |
| `dissent` | FAIL → `MINORITY_VIEW` |
| separate concurrence without majority support | FAIL → `CONCURRING_VIEW` |

**Final verdicts**

| Verdict | Meaning |
|---|---|
| `TRUE_RATIO` | Survived consistency, inversion, intolerability and authority — binding |
| `OBITER` | Not necessary to the decision, or a point left open |
| `NOT_NECESSARY` | Inversion would not change the outcome |
| `FAILED_INTOLERABLE` | Inconsistent with the outcome or logically intolerable on the facts |
| `MINORITY_VIEW` | Dissenting reasons |
| `CONCURRING_VIEW` | Separate concurrence without majority support — persuasive only |

### Leave-stage correction (v0.1 → v0.2)

v0.1 and the Turn-1 audit treated Appeal Committee (leave) reasoning as incapable of yielding ratio. **That rule is withdrawn.** A leave application is an application in its own right. Its LPs (e.g. the s.32 Hong Kong Court of Final Appeal Ordinance (Cap. 484) "question of great general or public importance" and "substantial and grave injustice" thresholds) and its CPs (the Committee's determination that the threshold is or is not met on the facts) form a ratio **at the leave stage**. The scope of that ratio is the leave question, not the merits. The pipeline labels this with `court_level = "Court of Final Appeal – Appeal Committee (leave stage)"`.

## 4. Case summary

Bilingual (EN / 繁體中文) fields: core issue, final result, summary, obiter list (paragraphs + note), dissent list (judge, paragraphs + note), Chinese ratio for every true ratio, and `ratio_makers` (author zone, authors, concurring judges) for every true ratio.

## 5. Commands

```bash
pip install -e '.[llm]'
export OPENAI_API_KEY=...            # any OpenAI-compatible endpoint (OPENAI_API_BASE)
export LEGALLESS_MODEL=gpt-6.1-sol   # optional
export LEGALLESS_MAX_CONCURRENCY=4   # optional; global cap on concurrent model calls

legal-less ratio structure judgment.md --json-output structure.json   # no model
legal-less ratio analyze  judgment.md --json-output case.json
legal-less ratio batch    corpus_dir/ results_dir/                    # resumable (SHA-256)
legal-less ratio export   results_dir/ --xlsx register.xlsx --app-json register.json
```

## Limitations

- Characterisation of LP/CP and the trial test are model-assisted. Verbatim quotes are machine-verified, but the legal classification **requires review by a lawyer** before it is relied on.
- Chinese text is a working translation using Department of Justice terminology where it exists. It is not an official translation.
- The authority gate counts judges by zone adoption. It does not resolve fragmented benches where no single proposition commands a majority; these appear as `CONCURRING_VIEW` and should be reviewed manually.
