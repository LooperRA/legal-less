# Phase 3 Source and Pattern Research

## Authoritative Judgment Sources

The HKCFA’s Judgments in Decided Cases page directs users to the searchable HKLII CFA database and warns that recent decisions may appear first on the HKCFA Recent Judgments page.[1] The Judiciary’s Legal Reference System provides newly added and historical judgments and permits downloading for private study and research; commercial use requires written application.[2] HKLII’s HKCFA collection reported 2,144 files and a last-updated date of 16 July 2026 when reviewed.[3]

The implementation therefore accepts local text, Markdown, or HTML supplied by an operator for research use. It records the official or HKLII source URL but does not ship a bulk downloader or a judgment mirror.

## Six-Judgment Structural Sample

Six judgments were examined across civil, criminal, revenue, property, and commercial matters. The sample was selected to exercise multiple action numbers, joint judgments, unanimous reasons, party capacities, anonymization-sensitive names, multiple orders, and costs language.

| Neutral citation | Action number | Structural observation | Costs observation |
|---|---|---|---|
| `[2026] HKCFA 27` | `FACV1/2026` | Unanimous judgment with party roles in original action and counterclaim; counsel and solicitors listed at the end | Multiple detailed costs orders at paragraph 8 |
| `[2026] HKCFA 25` | `FACC3/2025` | Criminal constitutional appeal; express issue statement at paragraph 1 | Costs not identified in the extracted portion |
| `[2026] HKCFA 2` | `FACV3/2025` | Joint judgment; four questions introduced together; legal representatives included in a party’s extended capacity description | Costs not identified in the extracted portion |
| `[2025] HKCFA 11` | `FACV11/2024` | Separate agreement paragraphs followed by one substantive judgment | Disposition identified; costs not identified in the extracted portion |
| `[2025] HKCFA 8` | `FACV12/2024` | Joint reasons; express “at issue” formulation; result stated near the opening | Costs not identified in the extracted portion |
| `[2024] HKCFA 31` | `FACV5/2024` | One main judgment with four express concurrences; footnotes and Markdown tables | Order nisi for appellant to pay respondent’s appeal costs at paragraph 58 |

## Parser Signals

| Target | High-value signals observed | False-positive control |
|---|---|---|
| Court identity | `COURT OF FINAL APPEAL`, `HKCFA`, `FACV`, `FACC`, `FAMV`, `FAMC` | A lower-court judgment may cite HKCFA cases, so citation text alone cannot verify court identity |
| Issue | `This appeal raises`, `At issue`, `question of law`, `concerns`, `the issues` | Submissions framed as a party’s argument are not automatically the court’s issue formulation |
| Court position | `we conclude`, `we are not satisfied`, `should be dismissed`, `the Court therefore unanimously`, express adoption of a rule | Descriptions of what the Court of Appeal held must not be treated as the HKCFA’s own holding |
| Legal reasoning | `because`, `therefore`, `accordingly`, `it follows`, `for those reasons`, `no good reason`, application of authority to facts | A reasoning connector inside quoted authority or counsel submissions is not the court’s reasoning unless adopted |
| Disposition | `appeal is dismissed/allowed`, `orders ... varied`, `Court therefore`, `we order` | Interim procedural history must not be mistaken for the final order |
| Costs | `costs ... paid by`, `shall pay the costs`, `order nisi`, `taxed if not agreed`, `no order as to costs` | The word “costs” in factual history or submissions is not an operative costs order |

The raw formats include numbered paragraphs rendered as `1.`, escaped Markdown forms such as `1\.`, tables for parties and coram, section headings, footnotes that resemble paragraph references, nested lists, multilingual party names, ordinal suffixes split by layout, and separate concurrence paragraphs. These variations require line-based segmentation with normalization, followed by opinion-attribution checks.

## Case Identifiers

HKCFA action numbers commonly use `FACV`, `FACC`, `FAMV`, or `FAMC`, followed by a serial number and four-digit year. A single judgment can contain several action numbers and related lower-court numbers. The canonicalizer must retain all observed identifiers and designate the HKCFA action number separately from related proceedings.

The official daily cause-list page exposes date-specific court categories through a `date` parameter in `DDMMYYYY` form and a court selector, with the Court of Final Appeal as a distinct option. Its front-end submits `lang`, `date`, and `court` to `view.jsp`. The public repository must not depend on that private web flow or collect party lists for profiling; the findings are used only to define an import schema compatible with operator-provided exports.

## Privacy and Evidentiary Safeguards

The official cause-list service states that online results are for reference and that posted court lists are the official information.[4] HK Court Diary warns that its automated parsing can be inaccurate and states that personal data in cause lists should not be used outside scheduling and attendance.[5] The Judiciary’s general personal-information statement also directs court-record access or correction requests to the relevant Registrar or authorised court officer.[6]

The representation project therefore uses the following controls: operator-supplied inputs; source and retrieval provenance; raw-data exclusion from Git; preservation of anonymity; no personal practitioner scoring; exact-case-number matching for confirmed links; human review for party-name suggestions; descriptive counts only; minimum-count suppression configurable by the operator; and a mandatory distinction between an observed event label and any explanation for that event.

## References

[1]: https://www.hkcfa.hk/en/work/cases/judgments/index.html "HKCFA — Judgments in Decided Cases"
[2]: https://www.judiciary.hk/en/judgments_legal_reference/judgments.html "Hong Kong Judiciary — Judgments"
[3]: https://www.hklii.hk/en/cases/hkcfa/ "HKLII — Court of Final Appeal"
[4]: https://e-services.judiciary.hk/dcl/index.jsp?lang=en "Hong Kong Judiciary — Daily Cause Lists"
[5]: https://hkcourtdiary.com/disclaimer "HK Court Diary — Disclaimer"
[6]: https://www.judiciary.hk/en/other_information/pics.html "Hong Kong Judiciary — Personal Information Collection Statement"

## HKLII Usage Boundary

HKLII’s Legal page states that it does not give general consent for its case-law databases to be indexed by other websites, places case-law outside permitted robot access, and blocks spiders and automated agents. It describes HKLII as an end-user reading service rather than a repository for third-party republication and reserves its value-added markup.[7]

The repository must therefore **not include an HKLII crawler**. HKLII URLs may be stored as human-verifiable citations, and individual users may supply a locally saved judgment for their own permitted research. Production-scale corpus acquisition must come from an original provider under permission or another authorised channel.

[7]: https://www.hklii.hk/legal "HKLII — Legal, Privacy and Usage Policy"
