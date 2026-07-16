# Data Schemas

Project Two consumes operator-reviewed CSV files. Each row represents **one firm in one court record**. The software validates required fields before comparison and rejects ambiguous enum values or incomplete relationship evidence.

> A valid row establishes only the facts recorded in that source. It does not establish causation, negligence, misconduct, competence, case quality, or the completeness of the operator’s corpus.

## Cause-list CSV

The cause-list import is one firm/event observation per row.

| Column | Required | Format | Meaning and validation |
|---|:---:|---|---|
| `hearing_date` | Yes | `YYYY-MM-DD` | Listed hearing date. |
| `court` | Yes | Text | Court or tribunal as displayed by the permitted source. |
| `case_number` | Yes | Text | Hong Kong case number. Spacing and `No.` are normalized where a code, serial number, and year are present. |
| `case_name` | Yes | Text | Source case title, preserving anonymization. |
| `hearing_type` | Yes | Text | Source hearing description. |
| `event_status` | Yes | Text | Source event wording. It is classified descriptively as `suspended`, `stayed`, `adjourned`, `vacated`, `rescheduled`, `withdrawn`, `heard`, `listed`, or `unknown`. |
| `firm_name` | Yes | Text | Firm as shown by the source. Court placeholders such as `A Firm` remain anonymized. |
| `represented_side` | Yes | Text | Side or capacity associated with the firm in the record. |
| `source_url` | Yes | Absolute URL | Human-verifiable source page. |
| `retrieved_at` | Yes | ISO-8601 timestamp | Time at which the operator retrieved or reviewed the record. |
| `notes` | No | Text | Neutral review note; avoid speculation and unnecessary personal data. |

Template: [`../examples/cause_list_template.csv`](../examples/cause_list_template.csv)

### Cause-list example

```csv
hearing_date,court,case_number,case_name,hearing_type,event_status,firm_name,represented_side,source_url,retrieved_at,notes
2025-01-15,Court of Final Appeal,FACV 1/2025,Example A v Example B,Appeal,Listed,Example & Co,Appellant,https://example.invalid/cause/1,2026-07-16T14:00:00+08:00,Structural example only
```

## Judgment-representation CSV

The judgment import is one firm/case role per row. Records created by `extract-judgment` default to `firm_role=representative` and `relationship_to_firm=not_applicable`.

| Column | Required | Format | Meaning and validation |
|---|:---:|---|---|
| `judgment_date` | Yes | `YYYY-MM-DD` | Date of the judgment. |
| `court` | Yes | Text | Court identifier or reviewed court name. |
| `case_number` | Yes | Text | Case number used for exact matching. |
| `neutral_citation` | Yes | Text | Hong Kong neutral citation, where published. The importer requires a non-empty value. |
| `case_name` | Yes | Text | Reviewed title preserving anonymity. |
| `outcome` | Yes | Text | Reviewed disposition; do not reduce it to a firm “win/loss” label. |
| `firm_name` | Yes | Text | Firm appearing as representative or named party. |
| `represented_side` | Yes | Text | Represented side when `firm_role=representative`; procedural capacity when `firm_role=party`. |
| `firm_role` | Yes | Enum | Exactly `representative` or `party`. |
| `relationship_to_firm` | Yes | Enum | Exactly `not_applicable`, `former_client`, `current_client`, or `unknown`. |
| `relationship_evidence` | Conditional | Text | Required for `former_client` or `current_client`; quote or describe the express source passage and retain its reference. |
| `source_url` | Yes | Absolute URL | Human-verifiable final-judgment source. |
| `retrieved_at` | Yes | ISO-8601 timestamp | Operator retrieval or review time. |
| `source_reference` | Yes | Text | Paragraph, line, heading, or other stable source reference. |

Template: [`../examples/judgment_representations_template.csv`](../examples/judgment_representations_template.csv)

### Judgment example

```csv
judgment_date,court,case_number,neutral_citation,case_name,outcome,firm_name,represented_side,firm_role,relationship_to_firm,relationship_evidence,source_url,retrieved_at,source_reference
2025-02-03,HKCFA,FACV1/2025,[2025] HKCFA 1,Example A v Example B,Appeal dismissed,Example & Co,Appellant,representative,not_applicable,,https://example.invalid/judgment/1,2026-07-16T14:15:00+08:00,counsel appearance line
```

## Canonical identifiers

Case numbers matching a code, serial number, and year are normalized without guessing missing components. For example, `FACV No. 12 of 2024` and `FACV 12/2024` become `FACV12/2024`. Values that do not match the supported structure are reduced to uppercase alphanumeric characters and `/`; the operator remains responsible for reviewing them.

Firm names are normalized for exact comparison by removing limited presentation punctuation and common prefixes. The comparator does not use fuzzy similarity to confirm a firm match. Different spellings therefore remain unmatched until reviewed and corrected in the input.

## Anonymized firm placeholders

Labels such as `A Firm`, `Firm A`, and similar court placeholders receive a case-scoped internal key. Two appearances of `A Firm` in different cases are not treated as the same firm. The software does not attempt identity resolution and suppresses firm-level rates for every anonymized key.

## Exact matches and unmatched records

A confirmed evidence link requires both:

1. the same canonical case number; and
2. the same canonical firm name.

The JSON output preserves the match basis and both source URLs. If the case exists in the supplied judgment file but the firm is not confirmed, the record states `case found but firm not confirmed in final judgment`. If the exact case number is absent, it states `no final-judgment record for exact case number`. Neither statement means that no judgment or representation exists outside the supplied corpus.

## Descriptive metrics

| Metric | Definition |
|---|---|
| `cause_list_appearances` | Number of supplied cause-list rows for the firm key. |
| `unique_cause_list_cases` | Number of distinct canonical case numbers in those rows. |
| `suspended_events` | Rows whose event wording classified as `suspended`. |
| `non_substantive_events` | Rows classified as suspended, stayed, adjourned, vacated, rescheduled, or withdrawn. |
| `final_judgment_links` | Distinct exact case/firm links confirmed in the supplied judgment records. |
| `named_as_party_cases` | Distinct judgment cases where `firm_role=party`. |
| `verified_client_origin_claims` | Distinct party cases with `former_client` or `current_client` and non-empty express relationship evidence. |
| `suspended_event_rate` | Suspended rows divided by all supplied cause-list rows for an eligible, non-anonymized firm. |

The suspended-event rate is suppressed unless the firm has at least the operator-selected number of distinct cases. The command default is five and the minimum accepted value is two.

## Provenance

Each comparison report records the imported file descriptions, SHA-256 digests, parser version, generated timestamp, and mandatory interpretation warnings. Retain source URLs and retrieval timestamps in the CSV so every observation can be checked against its underlying record.
