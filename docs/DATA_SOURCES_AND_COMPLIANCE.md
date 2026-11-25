# Data Sources and Compliance (v0.2)

legal-less does **not** ship a crawler and does **not** bulk-download judgments. The operator supplies judgments they are entitled to process.

| Source | Finding (checked 2026-11) | Consequence |
|---|---|---|
| HKLII (`hklii.hk`) | Case pages are a single-page app. The judgment text is served from `/api`, and `robots.txt` has `User-agent: * Disallow: /api`. HKLII's catalogue reports 2,153 HKCFA decisions. | No automated bulk retrieval of `/api`. |
| Judiciary Legal Reference System (`legalref.judiciary.hk`) | `robots.txt` has `Disallow: /` for all agents. | No automated retrieval. |
| Judiciary website terms | Reproduction for commercial purposes is not permitted without permission (judiciary.hk disclaimer / copyright page). | Raw judgment text is never committed to this repository. Check the terms and obtain permission before any commercial or redistributive use. |

## Pilot
Seven judgments were opened one by one in a browser and saved locally: [2013] HKCFA 39, [2019] HKCFA 10, [2020] HKCFA 22, [2023] HKCFA 1 (Appeal Committee), [2024] HKCFA 31, [2025] HKCFA 8, [2026] HKCFA 37. Only derived analysis (short verbatim quotes with pinpoints, statements, verdicts) is published.

## Running all HKCFA cases
1. Obtain the full set lawfully: written permission from HKLII / the Judiciary, a licensed data export, or an operator-held copy.
2. Put one file per judgment in a directory (`.md`, `.html` or `.json`, any filename).
3. `legal-less ratio batch corpus/ results/` (resumable, safe to re-run).
4. `legal-less ratio export results/ --xlsx register.xlsx --app-json register.json`.
5. Replace `assets/data/register.json` in the mobile app and rebuild.

**Estimated effort (from the pilot):** 7 judgments (about 458 KB of text) produced 73 model calls and about 104k completion tokens, taking about 41 minutes at concurrency 3. That is roughly 15k output tokens and 6 minutes of model time per case on average (longer for multi-judge judgments). Scaling linearly to 2,153 cases gives about 32M output tokens and several days of wall-clock time at this concurrency. Cost depends on the model and endpoint chosen. A cheaper first pass with a smaller model, followed by lawyer review of flagged cases, is recommended.
