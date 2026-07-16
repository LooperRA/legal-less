# legal-less

**Auditable Hong Kong court-research tools for locating ratio decidendi and mapping legal-representation records without converting correlation into allegations.**

[繁體中文說明](README.zh-HK.md)

> **Proprietary equation:** **Court position + legal reasoning = ratio decidendi candidate.**

The repository contains two connected but analytically separate projects. **Project One** is restricted to judgments of the Hong Kong Court of Final Appeal (“HKCFA”). It identifies traceable ratio candidates and answers five mandatory questions. **Project Two** compares operator-reviewed cause-list records with final-judgment representation records by exact case number and firm name. It reports evidence-linked descriptive patterns, not misconduct, competence, causation, or case quality.

## Project status

| Project | Implemented capability | Deliberate boundary |
|---|---|---|
| **HKCFA Ratio Decidendi Locator** | Verifies HKCFA scope; parses front matter, parties, judges, numbered paragraphs, issues, costs, and ratio candidates; exports JSON and Markdown | Candidates remain reviewable propositions, not automated declarations of legal truth |
| **Representation Evidence Map** | Validates reviewed CSV records; normalizes case numbers and firm names; preserves anonymization; links exact case/firm evidence; suppresses unreliable rates | No unattended cause-list crawler, identity resolution, practitioner ranking, or automated blame/success claim |

The first public release is a **local evidence toolkit**. This keeps acquisition, legal basis, retention, and publication decisions with the operator. HK Court Diary’s privacy and disclaimer pages limit the intended use of cause-list personal data and warn that its parsed information may contain errors.[1] [2] The Judiciary describes its online cause-list results as reference material and publishes copyright and reliance conditions.[3] [4] Accordingly, this repository does not ship a crawler or bulk archive.

## Five-question framework

Every HKCFA report addresses the following questions and links its answer to source evidence.

| No. | Required question | Implemented treatment |
|---:|---|---|
| 1 | **Where was the case heard?** | Verifies the Court of Final Appeal from the heading plus an HKCFA citation or final-appeal action number. A physical venue is never invented. |
| 2 | **Who were the parties?** | Extracts all parties and procedural capacities from the front matter while preserving court-ordered anonymity. |
| 3 | **What was disputed?** | Prefers an express issue, question-of-law, or “this appeal concerns” passage over a generated narrative. |
| 4 | **Which party follows the costs in the cause?** | Reports the operative costs wording. It does not infer a costs order from the result alone. |
| 5 | **How did the court apply the ratio decidendi?** | Pairs a court-position passage with legal reasoning and, where identified, an application passage. Every component retains a paragraph reference and score. |

## Ratio-candidate model

The locator operates at paragraph level. A candidate must contain evidence of both components in the proprietary equation. Transparent features rank the candidates; they do not replace legal review.

| Component | Positive signals | Penalties or exclusions |
|---|---|---|
| **Court position** | “we hold”, “we conclude”, “the proper approach”, “should be allowed/dismissed”, an adopted rule, or a unanimous position | Counsel submissions, lower-court descriptions, dissent, or a passage that merely records procedural history |
| **Legal reasoning** | “because”, “for these reasons”, “therefore”, statutory construction, precedent treatment, or application of a principle | Unconnected quotations, headnotes, chronology, or a bare result |
| **Necessity/application** | Resolution of an identified issue, application to the present facts, and connection to disposition | Obiter signposts, matters left open, hypothetical reasoning, or costs-only disposition language |
| **Traceability** | Paragraph reference, source URL, retrieval time, parser version, and SHA-256 digest | Untraceable paraphrase or missing provenance |

A Markdown report separates the five answers from the ranked candidates. The JSON report preserves the position, reasoning, application, feature scores, confidence value, warnings, and source metadata for downstream review.

## Installation

The package requires **Python 3.11 or later**.

```bash
gh repo clone LooperRA/legal-less
cd legal-less
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

For development and validation:

```bash
pip install -e '.[dev]'
pytest
ruff check src tests
```

## Project One: analyze one HKCFA judgment

Provide a judgment that the operator is entitled to process as UTF-8 text, Markdown, or HTML. The command performs no network request; `--source-url` is recorded only as provenance.

```bash
legal-less cfa analyze judgment.html \
  --source-url 'https://www.hklii.hk/en/cases/hkcfa/2025/8' \
  --json-output output/case.json \
  --markdown-output output/case.md
```

If no output path is supplied, the Markdown report is written to standard output. Exit status `0` means the document was verified as HKCFA material. Exit status `2` means the court identity could not be verified and the document is out of scope.

### Example report structure

```text
Case metadata
├── court verification, citation, action number, title, judges
├── source URL, retrieval time, parser version, SHA-256
Five required questions
└── answer + evidence + limitation for each question
Ranked ratio candidates
└── court position + legal reasoning + application + score + warnings
```

## Project Two: build a representation evidence map

Project Two uses **reviewed, one-firm-per-row CSV records**. It intentionally separates extraction from publication. An extracted representation line is not evidence that a firm caused an event, lost a case, acted negligently, or was sued by a client.

### Step 1: extract representation lines from a local final judgment

```bash
legal-less representation extract-judgment judgment.html \
  --judgment-date 2025-05-20 \
  --source-url 'https://www.hklii.hk/en/cases/hkcfa/2025/8' \
  --retrieved-at '2026-07-16T14:00:00+08:00' \
  --case-name 'Reviewed case name' \
  --outcome 'Reviewed disposition' \
  --csv-output data/judgment-representations.csv
```

The extractor creates `firm_role=representative` records only. A firm may be marked as a party, or a litigant as a current/former client, only through human review of an express judgment passage. Any `former_client` or `current_client` value requires a non-empty `relationship_evidence` field.

### Step 2: prepare a permitted cause-list CSV

Copy [`examples/cause_list_template.csv`](examples/cause_list_template.csv) and populate it only with records the operator is permitted to process. Preserve the source event wording in `event_status`; the importer maps it to a descriptive status such as `suspended`, `stayed`, `adjourned`, `vacated`, `rescheduled`, `withdrawn`, `heard`, `listed`, or `unknown`.

### Step 3: compare reviewed records

```bash
legal-less representation compare \
  data/cause-list.csv \
  data/judgment-representations.csv \
  --minimum-case-count 5 \
  --json-output output/representation.json \
  --markdown-output output/representation.md
```

A confirmed link requires the **exact canonical case number and exact canonical firm name**. Unmatched records remain visible with a reason. The result does not assert that no judgment exists; it states only that no exact final-judgment record was matched in the supplied corpus.

## Project Two data contract

| Input | Required columns |
|---|---|
| **Cause-list CSV** | `hearing_date`, `court`, `case_number`, `case_name`, `hearing_type`, `event_status`, `firm_name`, `represented_side`, `source_url`, `retrieved_at`; optional `notes` |
| **Judgment CSV** | `judgment_date`, `court`, `case_number`, `neutral_citation`, `case_name`, `outcome`, `firm_name`, `represented_side`, `firm_role`, `relationship_to_firm`, `relationship_evidence`, `source_url`, `retrieved_at`, `source_reference` |

Dates use `YYYY-MM-DD`. `firm_role` must be `representative` or `party`. `relationship_to_firm` must be `not_applicable`, `former_client`, `current_client`, or `unknown`. See [`docs/DATA_SCHEMAS.md`](docs/DATA_SCHEMAS.md) and the files in [`examples/`](examples/) for the full field rules.

## Interpretation and privacy safeguards

| Safeguard | Enforced behavior |
|---|---|
| **Exact evidence links** | A final-judgment link requires canonical case-number and firm-name agreement; party-name similarity cannot confirm a link. |
| **Anonymized placeholders** | “A Firm” and similar court labels are isolated by case number and never aggregated across cases or resolved to an identity. |
| **Minimum-count suppression** | A firm-level suspended-event rate is suppressed below the operator’s distinct-case threshold and always suppressed for anonymized firms. |
| **No individual ranking** | Names of individual practitioners are outside the aggregation model. |
| **No causation inference** | Listing status and final disposition remain distinct facts. The report repeats non-causal warnings. |
| **Verified client-origin claims only** | A count is permitted only where the firm is a named party, the relationship is recorded as current/former client, and express supporting evidence is supplied. |
| **Local raw material** | Operator-provided source documents and generated working data are excluded from version control by default. |

> **Important:** Public-record aggregation can still create reputational and privacy risks. Review every source, match, relationship annotation, and intended publication context before sharing a report.

## Validation

The repository contains **14 deterministic tests** covering HKCFA verification, action-number and party extraction, the five questions, ratio scoring, penalties, source hashing, out-of-scope rejection, case/firm normalization, anonymized placeholders, exact evidence links, minimum-count suppression, client-relationship evidence, representation extraction, and all command outputs.

The parser was also manually validated against two public HKCFA formats without committing the judgment texts: `[2024] HKCFA 31` and `[2025] HKCFA 8`.[7] [8] Those checks exposed and corrected body-citation leakage, flattened party tables, endnote paragraph restarts, signature/counsel contamination, and the over-ranking of costs-only disposition passages. The derived observations are recorded in [`research/phase6_real_validation.md`](research/phase6_real_validation.md).

Run the release checks with:

```bash
ruff format --check src tests
ruff check src tests
pytest
```

## Repository structure

```text
legal-less/
├── docs/
│   ├── ARCHITECTURE.md
│   ├── DATA_SCHEMAS.md
│   └── PROJECT_SPEC.md
├── examples/
│   ├── cause_list_template.csv
│   └── judgment_representations_template.csv
├── research/
│   ├── phase1_findings.md
│   ├── phase3_sources.md
│   └── phase6_real_validation.md
├── src/legalless/
│   ├── cfa.py
│   ├── cli.py
│   ├── provenance.py
│   └── representation.py
├── tests/
├── LICENSE
├── pyproject.toml
└── README.md
```

## Architecture and future deployment

The implemented release is local-first and deterministic. A future authenticated dashboard may reuse the parser and evidence rules only after the operator confirms source permissions, retention controls, access roles, correction procedures, and publication review. See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

## Limitations

The locator ranks textual candidates and cannot determine authoritativeness by score alone. Separate reasons, concurrences, dissents, incorporated authorities, unnumbered judgments, Chinese-only layouts, scanned documents, or unusual formatting may require manual analysis. A report does not replace reading the judgment or obtaining legal advice.

The representation map is only as complete and accurate as its operator-provided corpus. A cause-list event is not a final result. A final judgment may omit earlier representatives, use different firm spellings, concern a related proceeding, or not exist within the supplied collection. The tool deliberately prefers an unmatched record to a speculative match.

## Contributing

Contributions should preserve evidence traceability, source permissions, anonymity, and the distinction between descriptive data and culpability. Add a regression test for every parser change. Do not commit raw judgments, bulk cause lists, private client data, or any material collected contrary to source conditions. See [`CONTRIBUTING.md`](CONTRIBUTING.md).

## Licence

The source code is released under the repository’s [MIT Licence](LICENSE). Source documents remain subject to their own copyright, privacy, access, and reuse conditions.

## References

[1]: https://hkcourtdiary.com/privacy "HK Court Diary — Privacy Policy"
[2]: https://hkcourtdiary.com/disclaimer "HK Court Diary — Disclaimer"
[3]: https://e-services.judiciary.hk/dcl/index.jsp?lang=en "Hong Kong Judiciary — Daily Cause Lists"
[4]: https://www.judiciary.hk/en/other_information/disclaimer.html "Hong Kong Judiciary — Copyright and Disclaimer"
[5]: https://www.hklii.hk/legal "HKLII — Legal Information and Usage Conditions"
[6]: https://www.hkcfa.hk/en/work/cases/judgments/index.html "Hong Kong Court of Final Appeal — Judgments"
[7]: https://www.hklii.hk/en/cases/hkcfa/2024/31 "[2024] HKCFA 31"
[8]: https://www.hklii.hk/en/cases/hkcfa/2025/8 "[2025] HKCFA 8"
