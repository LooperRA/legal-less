# Real-Judgment Validation Notes

Two individual HKCFA judgments were opened manually for parser validation; no bulk collection or crawler was used.

## `[2024] HKCFA 31` — V Capital Limited v Margaret Chiu

Source: https://www.hklii.hk/en/cases/hkcfa/2024/31

The extracted public page contains an express issue formulation concerning a Master’s jurisdiction to order imprisonment without leave under section 12 of the Bankruptcy Ordinance. It distinguishes the Court of Appeal’s reasoning from the HKCFA’s position, identifies an inapplicable question at paragraph 52, applies the certified question to the present case at paragraph 53, and ends with a unanimous dismissal plus an order that the appellant pay the respondent’s appeal costs. These features directly test the implementation’s submission/lower-court penalties, issue locator, necessity/application features, disposition language, and costs-order locator.

## `[2025] HKCFA 8` — So Kwai Chung v Wong Wai Ying Anita and Others

Source: https://www.hklii.hk/en/cases/hkcfa/2025/8

The public page exposes a formal front matter with `FACV No. 12 of 2024`, `[2025] HKCFA 8`, the Court of Final Appeal heading, multiple plaintiffs and defendants with procedural roles, a five-member coram, dates, three separate agreement paragraphs, and joint reasons beginning at paragraph 4. Paragraph 4 begins “This appeal concerns” and “At issue”; paragraph 5 presents competing party contentions; paragraph 6 states “For the reasons that follow” and the result. These features test formal action-number inference, split ordinal and table-layout hazards, multi-party handling, opinion attribution, issue signals, party-submission penalties, and position-plus-reasoning pairing.

The locally saved page copies used for validation are temporary research inputs and are excluded from the repository. Only derived validation observations and source links are retained.

## Post-fix parser results

| Judgment | Scope/citation | Action number | Parties | Paragraph boundary | Issue | Costs | Top equation candidate |
|---|---|---|---:|---:|---|---|---|
| `[2024] HKCFA 31` | Verified, `[2024] HKCFA 31` | `FACV5/2024` only; the body citation `FAMV1/2004` is excluded | 2 anonymized parties | 58 | ¶3 | ¶58 | Court position ¶54 + legal reasoning/application ¶53, score 11.0 |
| `[2025] HKCFA 8` | Verified, `[2025] HKCFA 8` | `FACV12/2024` | 5 parties with trial and appeal capacities | 66 | ¶4 | ¶66 | Adopted application/reasoning at ¶53, score 8.0 |

Manual inspection confirms that the 2024 top pair applies the certified-question analysis in the present case before stating the Court’s answer, while the 2025 top paragraph explains why the declaration must bind successors in title to prevent the identified detriment. The final costs/disposition passages no longer outrank these substantive passages merely because they contain “accordingly” or an order.

The fixes derived from this validation are covered by the synthetic regression suite without committing copyrighted judgment text. The repository records only source URLs, derived structural observations, and test-generated data.
