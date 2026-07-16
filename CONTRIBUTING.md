# Contributing to legal-less

Contributions are welcome when they preserve the project’s central requirements: **traceable evidence, deterministic behavior, court-ordered anonymity, source permissions, and the distinction between descriptive facts and culpability**.

## Development setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
pytest
ruff check src tests
```

The package supports Python 3.11 and later. Every parser, normalizer, schema, or command change should include an executable regression test.

## Evidence and data rules

Do not commit raw judgments, bulk cause lists, client files, private correspondence, access credentials, or personal data collected for a one-off analysis. Public fixtures must be synthetic structural examples or short material that the contributor is entitled to reproduce.

| Requirement | Contribution rule |
|---|---|
| **Source permission** | Confirm that collection, use, retention, and republication comply with the source’s terms and applicable law. A public URL does not by itself establish permission to republish a corpus. |
| **Provenance** | Preserve source description/URL, retrieval time, parser version, SHA-256 digest, stable references, and warnings. |
| **Anonymity** | Never attempt to resolve `A Firm`, anonymized parties, initials, or other court-protected labels. Add tests proving case-scoped isolation where relevant. |
| **Legal conclusions** | Do not turn a candidate score into an authoritative holding. Do not infer negligence, misconduct, causation, competence, or success from hearing events or dispositions. |
| **Matching** | A confirmed Project Two link must retain its basis. Fuzzy or party-name similarity may support a review suggestion only; it must not silently become an exact match. |
| **Client relationships** | `current_client` or `former_client` requires express source evidence and a stable reference. |

## Parser changes

A parser pull request should explain the real formatting problem in derived terms, add the smallest synthetic fixture that reproduces it, and demonstrate that prior regression tests still pass. Avoid committing the real judgment text when a compact structural fixture is sufficient.

Run the release checks before submitting:

```bash
ruff format --check src tests
ruff check src tests
pytest
```

## Documentation changes

Documentation must state current behavior rather than proposed features. Clearly label future architecture, model-assisted analysis, scheduled ingestion, hosted dashboards, or data stores as unimplemented unless the associated code and tests are included.

External factual claims should link to authoritative sources. Preserve the project’s warnings about source completeness, human review, copyright, privacy, and reputational risk.

## Security and responsible disclosure

Do not open a public issue containing private court records, credentials, unpublished legal material, or a reproducible disclosure involving sensitive data. Follow [`SECURITY.md`](SECURITY.md) for private reporting.

## Licence

By contributing, you agree that your code and documentation contributions may be distributed under the repository’s MIT Licence. This does not change the copyright or use conditions of any source document.
