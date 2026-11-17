# AUREX — Phase 1 + provider backend

## Build the APK (GitHub Actions)
1. Create a private repo, push this folder, open the Actions tab.
2. Run "CI" (or push). Download the `aurex-debug-apk` artifact, unzip, install.
No Gradle wrapper is committed; CI uses Gradle 8.9 via setup-gradle. To build locally in Android Studio, open the folder (it will sync), or run `gradle wrapper --gradle-version 8.9` once.

## Backend
cd backend && python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt && cp .env.example .env   # put the key in .env only
AUREX_ENV=dev uvicorn app.main:app --reload
GET /health, /v1/providers/health, /v1/quotes, (dev only) /v1/dev/talasanj-raw

## Talasanj mapping
Run scripts/probe_talasanj.sh, send the "safe to paste" part, then
config/talasanj_mapping.json is written from the real shape (see providers/mapping.py).
Until then the provider reports status "unmapped" and the app shows "no data".

## Add a provider
Subclass Provider (providers/base.py), implement _fetch(), add it to the list in main.py in priority order. Reuse an asset_id only if market and unit are identical.
## Add a language
Create res/values-<code>/strings.xml and add an entry to languageOptions in Screens.kt.
