# Changelog

## 0.2.0
- Added `legal-less ratio` pipeline: structure (headings, judge zones, coram, dissent), LP/CP inventory with verified verbatim quotes and pinpoints, same-zone combos, trial test (consistency, inversion, intolerability, authority gate), bilingual case summary, resumable batch and Excel/app exporters.
- **Changed rule:** Appeal Committee (leave-stage) reasoning can yield ratio (previous rule withdrawn).
- New verdict values: `MINORITY_VIEW`, `CONCURRING_VIEW`.
- Added docs: `RATIO_PIPELINE_V2.md`, `DATA_SOURCES_AND_COMPLIANCE.md`, `APP_STORE_RELEASE.md`, `research/phase7/PILOT_V0_2.md`.
- Packaging: `pyproject.toml` licence classifier corrected to The Unlicense (it said MIT while `LICENSE` is the Unlicense); `openpyxl` dependency and `llm` extra added.
## 0.1.0
- Initial release: deterministic HKCFA paragraph scorer and representation evidence map.
