# Verification notes

Updated: 21 October 2026. Environment: Linux x86_64, Python 3.12.14, Node 24.19.0.

## Results

| Check | Result |
| --- | --- |
| Backend pytest suite | 58 tests passed |
| JavaScript selection and player tests | 8 tests passed |
| Playwright browser suite | 20 tests passed |
| Supplied example CSV | All 40 rows normalized successfully; copy is byte-identical to the upload |
| Visual review | Desktop at 1440 px and mobile at 390 px inspected |

## Changes covered

- `/api/catalog` and `?curated=false` select `AllSets`; `?curated=true` selects `Sets` in the same configured spreadsheet. Existing worksheet prefixes in `GOOGLE_SHEETS_RANGE` are replaced while the A1 cell range is retained. Invalid boolean queries are rejected before a Google request.
- Genre labels and tags preserve source capitalization. Duplicate genre options and filtering remain case-insensitive without changing the source data.
- Switching catalogs refreshes the set count, options, and player, and resets genre, duration, and year. Resetting filters keeps the chosen catalog. Full page reloads and browser back/forward cache restoration start with `AllSets`.
- Empty and failed catalog loads leave the switch usable. Reload catalog retries the selected source. Aborted or late responses cannot overwrite a newer catalog selection.
- Existing player lifecycle, exact `DurationApprox` filtering, combined filters, no autoplay, error handling, retry limits, request deadlines, and server-side API key handling are covered.
- Browser layout checks pass at widths of 320, 390, 768, and 1440 px. The larger uppercase NEXT SET button, simplified heading, and new switch were visually inspected.

## Test environment

Backend tests used the repository's frozen Python dependencies. `npm test` passed; direct execution of the two test files also reported six selection tests and two player tests.

The browser suite ran with Playwright 1.56.0 and Chromium 141.0.7390.37 (build 1194) in an isolated verification environment. The browser download for the locked Playwright version returned an unusable archive, so an older compatible browser environment was used. `pyproject.toml` and `uv.lock` were not changed for this workaround.

Google Sheets HTTP responses and the YouTube SDK are mocked in automated tests. These checks verify application behavior without credentials, external playback, or audio.

## Live deployment checks

Live Google Sheets API access and real YouTube playback were not exercised in this session because the uploaded repository does not include the owner's API key. The new feature includes backend changes, so deploy the full application after updating the repository. Confirm that both `AllSets` and `Sets` exist with the required column headers and are readable by the configured server-side API key.

Real YouTube playback on the final HTTPS domain, other browser engines, physical mobile devices, and the deployment's Docker build remain environment-specific checks.

## Retained historical snapshot

`scripts/catalog-snapshot.json` remains the original 19-set snapshot from 2 October 2026. It is separate from the new 40-row example CSV. The static preview uses one snapshot and disables catalog switching; the configured FastAPI application reads the selected worksheet live.
