# Legal-less Project Specification

## Purpose

The repository contains two connected but analytically separate projects. **Project One** locates and explains the ratio decidendi in judgments of the Hong Kong Court of Final Appeal (“HKCFA”). **Project Two** compares law-firm representation events appearing in permitted cause-list data with final-judgment representation records, without converting correlation into allegations of fault.

> **Proprietary equation:** **Court position + legal reasoning = ratio decidendi.**

The equation is implemented as an auditable ranking rule rather than an opaque summary. A proposition can qualify as a ratio candidate only when the judgment text provides evidence of both: (a) the court’s operative position on an issue necessary to disposition; and (b) the reasoning that connects authority, rule, facts, and result.

## Project One: HKCFA Ratio Decidendi Locator

The locator is restricted to judgments identified as decisions of the **Hong Kong Court of Final Appeal**. A document that cannot be verified as HKCFA material must be rejected or marked out of scope rather than silently analyzed as a final-appellate decision.

Every completed analysis must answer the following five questions.

| No. | Required question | Operational meaning | Minimum evidence |
|---:|---|---|---|
| 1 | **Where was the case heard?** | Court, jurisdiction, and, where available, hearing venue or court building. | Court heading or official metadata; venue must never be invented. |
| 2 | **Who were the parties?** | Appellant/applicant/respondent and any additional parties, preserving court-ordered anonymity. | Case title, coram/front matter, or party section. |
| 3 | **What was disputed?** | The issue or issues the court had to decide, not a general narrative of the litigation. | Express “issue/question/appeal” language or a reasoned issue reconstruction tied to paragraph references. |
| 4 | **Which party follows the costs in the cause?** | The costs order and the party bearing or receiving costs. If the formula “costs in the cause” is used, identify the contingent effect. | Operative order, disposition, or express costs paragraph. “Not found” is preferable to inference. |
| 5 | **How did the court apply the ratio decidendi?** | The rule adopted by the court, the legally material facts, the inferential bridge, and the result to which the rule was applied. | At least one court-position passage and one legal-reasoning passage, each with paragraph or line provenance. |

### Ratio Candidate Model

The locator operates at paragraph level. It identifies propositions and scores them using transparent features. Scores rank candidates; they do not declare legal truth without supporting passages.

| Component | Positive indicators | Exclusions or penalties |
|---|---|---|
| **Court position** | “we hold”, “we conclude”, “the proper approach”, “the appeal is allowed/dismissed”, adoption of a stated rule, majority concurrence | Party submissions, neutral history, quotations not adopted by the court, dissent unless expressly requested |
| **Legal reasoning** | “because”, “therefore”, “it follows”, statutory construction, precedent treatment, application to material facts | Pure procedural chronology, unconnected quotations, headnotes, counsel arguments |
| **Necessity to disposition** | Passage resolves an identified issue and connects to an operative order | Obiter signposts, hypothetical discussion, issue left open, alternative observations not needed for result |
| **Authority and court position** | Majority or unanimous reasons of the HKCFA; clear adoption by the deciding judges | Separate concurrence without majority adoption; dissenting reasons |
| **Traceability** | Stable paragraph numbers, source URL, retrieval date, document hash | Untraceable paraphrase or missing source metadata |

The output must distinguish **candidate ratio**, **supporting reasoning**, **application**, **disposition**, **costs**, and **confidence limitations**. The system must never present a generated paraphrase without the evidence passages from which it was derived.

## Project Two: Representation Evidence Map

The second project maps court events and judgment records by normalized case number. It is an **evidence map**, not a misconduct detector, negligence classifier, or lawyer-ranking service.

### Permitted Analytical Claims

| Claim type | Permitted treatment |
|---|---|
| A firm appears repeatedly | Report a count, date range, courts, case numbers, and coverage period. |
| A listed event was adjourned, stayed, suspended, vacated, or otherwise changed | Report only the exact event label present in the permitted source and the retrieval date. Do not attribute causation. |
| A final judgment names a firm as legal representative | Record the side represented and cite the judgment passage or metadata. |
| A firm is itself a named party in a judgment | Record the procedural fact and role. Do not infer a solicitor-client dispute unless the judgment expressly establishes it. |
| A firm is anonymized as “A Firm” or similar | Preserve the anonymization and prohibit attempted identity resolution. |
| No final judgment was matched | Report “no matched judgment in the indexed corpus”; never report that no judgment exists. |

### Prohibited Automated Conclusions

The software must not automatically assert that a legal representative caused a suspension, lost a case, acted negligently, was sued by a client, poses a professional risk, or has a success/failure rate. It must not score or rank individual practitioners. Human-reviewed annotations may record an expressly stated solicitor-client claim only when linked to the exact judgment source and supporting passage.

### Matching Rules

Case-number matching is deterministic. The canonical key is composed of jurisdiction code, proceeding type, serial number, and year when those components are available. Party-name similarity may suggest a possible match but cannot create a confirmed match by itself. Every match stores its method and confidence category.

| Match category | Rule |
|---|---|
| **Exact** | Canonical case number agrees across records. |
| **Cross-proceeding** | Judgment expressly identifies the lower proceeding or related appeal number. |
| **Suggested** | Party and date features indicate a possible link; requires human review. |
| **Rejected** | Conflicting court, year, serial number, or party roles. |

## Shared Provenance Requirements

Every imported record must include a source URL or source description, retrieval timestamp, SHA-256 digest of the imported content, parser version, and any warnings. Raw documents are local operator inputs and are excluded from version control by default. Public fixtures must be synthetic structural examples or short, properly attributed extracts permitted for testing.

The HK Court Diary disclaimer limits cause-list personal data to scheduling and attendance purposes and warns of parsing inaccuracies.[1] The official Judiciary site describes its online cause-list results as reference material and restricts commercial reproduction without permission.[2] [3] The repository therefore ships **operator-controlled import tools**, not an unattended public-data harvester.

## Acceptance Criteria

Project One is complete when the command-line interface can ingest an HKCFA text or HTML judgment, verify or flag court identity, segment numbered paragraphs, answer the five questions with evidence references, rank ratio candidates using both equation components, and export machine-readable JSON plus a readable Markdown report.

Project Two is complete when the command-line interface can ingest permitted cause-list exports and judgment records, normalize case numbers and firm names, preserve anonymization, create exact or review-required links, and export an evidence-linked firm-level report containing counts and coverage warnings but no automated fault or success claims.

Both projects must include deterministic unit tests, documented data schemas, sample commands, privacy and evidentiary safeguards, and a clean installation path using Python 3.11 or later.

## References

[1]: https://hkcourtdiary.com/disclaimer "HK Court Diary — Disclaimer"
[2]: https://e-services.judiciary.hk/dcl/index.jsp?lang=en "Hong Kong Judiciary — Daily Cause Lists"
[3]: https://www.judiciary.hk/en/other_information/disclaimer.html "Hong Kong Judiciary — Copyright and Disclaimer"
