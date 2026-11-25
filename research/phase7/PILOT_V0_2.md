# Phase 7 — v0.2 pilot (7 HKCFA judgments)

Run: gpt-6.1-sol, concurrency 3. All quotes machine-verified against the source paragraph.

| Case | Title | Court level | Date | Bench | Zones | LP | CP | Combos | True ratio | Obiter | Minority | Concurring only | Failed |
|---|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| [2013] HKCFA 39 | W V. The Registrar Of Marriages | Full Court (final appeal) | 2013-05-13 | majority | 5 | 113 | 108 | 18 | 10 | 0 | 3 | 5 | 0 |
| [2019] HKCFA 10 | Comilang, Milagros Tecson And Another V. | Full Court (final appeal) | 2019-04-04 | unanimous | 5 | 61 | 42 | 18 | 13 | 5 | 0 | 0 | 0 |
| [2020] HKCFA 22 | H V. Director Of Immigration | Full Court (final appeal) | 2020-07-14 | unanimous | 5 | 53 | 24 | 5 | 2 | 3 | 0 | 0 | 0 |
| [2023] HKCFA 1 | Hksar V. Choy Yuk Ling (蔡玉玲) | Appeal Committee (leave stage) | 2023-01-17 | unanimous | 1 | 2 | 2 | 2 | 2 | 0 | 0 | 0 | 0 |
| [2024] HKCFA 31 | V Capital Limited V. Margaret Chiu | Full Court (final appeal) | 2024-12-18 | unanimous | 6 | 48 | 21 | 6 | 5 | 1 | 0 | 0 | 0 |
| [2025] HKCFA 8 | So Kwai Chung V. Wong Wai Ying Anita And | Full Court (final appeal) | 2025-05-20 | unanimous | 5 | 30 | 33 | 5 | 4 | 1 | 0 | 0 | 0 |
| [2026] HKCFA 37 | Dr Leung Ka Lau V. The Medical Council O | Full Court (final appeal) | 2026-11-23 | unanimous | 5 | 24 | 33 | 5 | 4 | 1 | 0 | 0 | 0 |

## Observations
- **[2013] HKCFA 39 (W v Registrar of Marriages):** the five zones were identified correctly: Ma CJ and Ribeiro PJ joint lead, Chan PJ dissent, Bokhary NPJ separate concurrence, Lord Hoffmann NPJ "agree", and the order. The Chan PJ combos are `MINORITY_VIEW`. Bokhary NPJ's separate reasons fail the majority gate and are `CONCURRING_VIEW`. A first run labelled them `MINORITY_VIEW`; that was a labelling defect, fixed by adding the `CONCURRING_VIEW` verdict.
- **[2020] HKCFA 22:** the s.14AA / O.59 r.21(1)(g) point is a true ratio. The s.14AB / BL 82 question is classed as obiter because the Court said it did not arise (para 49).
- **[2023] HKCFA 1:** Appeal Committee reasoning yields two true ratios at the leave stage.
- Zero `FAILED_INTOLERABLE` verdicts in 7 cases. The test never flagged a combo that the Court had actually decided, so it should be treated as a filter for obiter and minority material, not yet as a proven error detector. A seeded-error evaluation is the recommended next step.
- Open item: [2019] HKCFA 10 and [2024] HKCFA 31 had quotes dropped as unverifiable; see `warnings` in each result.
