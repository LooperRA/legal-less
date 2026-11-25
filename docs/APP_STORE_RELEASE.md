# Apple App Store Release Guide — "Legal-less Ratio"

The app is an Expo / React Native app, offline-first, with the register bundled as JSON (`assets/data/register.json`). It has no accounts, no tracking and no network calls for content.

| Item | Value |
|---|---|
| App name | Legal-less Ratio |
| Bundle ID | `space.manus.legalless.t130449961404556` (change in `app.config.ts` before submission if you want your own domain, e.g. `com.looperra.legalless`) |
| Category | Reference (secondary: Education) |
| Languages | English, Traditional Chinese (in-app toggle) |
| Age rating | 4+ (no objectionable content) |
| Price | Free |

## Steps (the account holder must do 1–2 and 5–7)
1. Enrol in the **Apple Developer Program** (US$99/year; individual or organisation with a D-U-N-S number).
2. In App Store Connect, create the app record with the bundle ID above.
3. Build the iOS binary from the Manus project (Publish / iOS build in the project Dashboard), then upload to **TestFlight**.
4. Test on a device: browse, search, case page (EN/繁中), save, About.
5. Complete App Store Connect metadata: description, keywords, screenshots (6.7" and 6.5" iPhone, 12.9" iPad if supported), support URL, privacy policy URL.
6. Answer **App Privacy**: "Data Not Collected". Bookmarks and language are stored locally on the device only.
7. Submit for App Review with the notes below.

## Suggested listing text
**Subtitle:** Hong Kong CFA ratio decidendi
**Description:** Browse Hong Kong Court of Final Appeal decisions broken down into legal principles, court positions and tested ratio decidendi. Each ratio shows its paragraph numbers and verbatim quotes with pinpoints, who made it, the trial-test result, obiter observations and dissenting views. English and Traditional Chinese.

## App Review notes
"No login required. The app is a legal-research reference tool. Content is derived from publicly available Hong Kong Court of Final Appeal judgments and is bundled in the app. It is not legal advice. No data is collected."

## Privacy policy (host this text at a public URL)
Legal-less Ratio does not collect, store on a server, share or sell personal data. Language preference and bookmarks are kept on your device only and are deleted when you uninstall the app. The app makes no analytics or advertising requests.

## Required in-app disclaimer (present on the Method tab)
Analysis is generated with model assistance and machine-verified quotations. It is **not legal advice**, has not been endorsed by the Judiciary, and must be checked against the official judgment. Chinese text is a working translation.

## Content-rights checklist before submission
- Confirm you may redistribute the derived analysis (the app bundles short quotations and original summaries only, not full judgments).
- Obtain permission from the Judiciary / HKLII if the app is commercial, or before scaling to all HKCFA decisions.
- Do not describe the app as official or as affiliated with the Hong Kong Judiciary.
- Keep the Unlicense / public-domain status of the code separate from third-party content rights.

## Current dataset
The build contains the 7-case pilot. Replace `assets/data/register.json` with the full export once a lawful full corpus has been processed (see `DATA_SOURCES_AND_COMPLIANCE.md`).
