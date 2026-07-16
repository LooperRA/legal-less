# Security Policy

## Supported version

The latest commit on the default branch is the supported development version until tagged releases are published.

## Report privately

Please report security or privacy vulnerabilities through a private GitHub security advisory for this repository. Do not include credentials, private client data, unpublished court material, bulk personal data, or identity-resolution details in a public issue.

A useful report should describe the affected version or commit, the input conditions, the observed behavior, the expected safe behavior, and the smallest non-sensitive reproduction. Synthetic data is strongly preferred.

## Relevant vulnerability classes

| Area | Examples |
|---|---|
| **Privacy/anonymity** | Cross-case aggregation of `A Firm`, accidental identity resolution, unexpected retention of raw personal data, or output that exposes fields outside the documented schema |
| **Evidence integrity** | Incorrect source hash, lost provenance, fabricated paragraph reference, or a confirmed match created without the documented exact keys |
| **Input handling** | Malformed HTML/CSV causing code execution, uncontrolled file access, or resource exhaustion beyond ordinary parser limits |
| **Legal/reputational safeguards** | Automated output that states misconduct, negligence, causation, competence, or client relationship without the required evidence gates |
| **Dependency/security** | A vulnerable runtime dependency or packaging configuration affecting users of the command-line tools |

## Out of scope

Disagreement with a candidate’s legal interpretation is normally a methodology or parser issue rather than a security vulnerability, unless the system falsely represents generated material as sourced evidence or bypasses a documented review gate. Source-site availability, completeness, and third-party terms are outside this repository’s control.

## Data minimization

Do not send a full judgment or cause-list corpus when a short synthetic fixture can reproduce the problem. Remove names, URLs, case identifiers, metadata, and file paths that are not necessary to demonstrate the defect.
