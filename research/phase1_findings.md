# Phase 1 Findings

## Repository Identification

The public repository is **LooperRA/legal-less** at <https://github.com/LooperRA/legal-less>. Its default branch is `main`. The current repository contains only `README.md` and `LICENSE`; there are no source files, tests, branches, or Git tags. The history contains an initial commit and one README-clarity update.

The README defines two objectives: (1) reliably locate ratio decidendi in Hong Kong judgments and (2) analyze representation risk objectively using Hong Kong Courts daily cause lists.

## HK Court Diary Privacy Findings

The specified source, <https://hkcourtdiary.com/privacy>, states that HK Court Diary is operated by Terracotta Cyber Solutions Limited. It processes publicly available Judiciary cause-list information and provides a mobile-friendly view only during the Judiciary's current publication window. The policy identifies cause-list information as public source data but does not itself grant an archival, bulk-republication, or automated-scraping licence.

The implementation should therefore treat HK Court Diary as a discovery and viewing aid, retain source provenance, avoid collecting analytics or hearing-watch contact information, and rely on official Judiciary material wherever possible for durable records and verification. Any derived professional-representation analysis must separate observed court events from inferred risk, display uncertainty, preserve anonymization, and avoid unsupported allegations.

## Initial Engineering Consequences

Because the repository is a blank public starting point, both projects must be created as an auditable implementation rather than merely patched. The safest baseline is a deterministic ingestion and normalization layer, an evidence-linked extraction layer for CFA judgments, and a separate analytical layer that never turns absence of a judgment, adjournment, suspension, anonymization, or repeated appearances into misconduct claims.

## Disclaimer and Authoritative-Source Constraints

The HK Court Diary disclaimer at <https://hkcourtdiary.com/disclaimer> states that automated parsing may contain errors, omissions, or inaccuracies and directs users to verify hearing information against the official Judiciary daily cause list at <https://e-services.judiciary.hk/dcl/index.jsp?lang=en>. It also states that personal data appearing in a Daily Cause List should not be used for a purpose unrelated to scheduling and attendance.

This restriction materially changes the second project's data design. HK Court Diary must not be mined for practitioner profiling. The application should instead use it only as a human-facing pointer, use official published judgments as the durable and citable source for party and representation information, and permit cause-list ingestion only from data that the operator is legally entitled to process. Individual practitioners should not receive automated reputational scores. Firm-level event statistics must be descriptive, evidence-linked, minimum-count protected, and accompanied by explicit non-causation and coverage warnings.

The authoritative daily cause-list URL is <https://e-services.judiciary.hk/dcl/index.jsp?lang=en>. Initial browser rendering exposed only the service header, so further inspection is required to identify its technical interface and publication terms.

## Official Judiciary Publication Conditions

The official daily cause-list interface currently exposes four dates and a court selector. It states that its web results are for reference only, that lists posted in courts and tribunals are the official information, and that cause lists are normally posted by 6:30 p.m. on the preceding working day. It also warns that reporting restrictions under section 9P of the Criminal Procedure Ordinance may apply to bail proceedings.

The Judiciary copyright and disclaimer page at <https://www.judiciary.hk/en/other_information/disclaimer.html> states that website copyright belongs to the HKSAR Government and that reproduction for commercial purposes without permission is prohibited. It limits the website to general reference and private use, disclaims completeness and currency, and warns against treating it as an authoritative statement of law or practice.

Accordingly, the public repository should not ship a bulk mirror or republish copied cause lists. It should provide user-controlled import adapters, preserve citations and retrieval timestamps, store normalized facts rather than page copies, and require operators to confirm they have a lawful basis for any ingestion. Public demos should use synthetic or expressly permitted fixtures. Judgment extracts should remain short, traceable, and linked to official originals rather than reproduced wholesale.
