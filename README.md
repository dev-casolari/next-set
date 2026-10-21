# NextSet

A single-page app that picks a random DJ set from your Google Sheet and plays it in the official YouTube player. Built with **Python/FastAPI** and **plain HTML, CSS, and JavaScript**, with no frontend build step, database, or application accounts.

Choose a genre, duration, and year, or press **NEXT SET** to discover something new. Turn on **Only curated sets** to choose from your handpicked catalog.

## Quick start

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/getting-started/installation/).

```bash
uv sync --frozen
cp .env.example .env
# Check the spreadsheet configuration and set your server-side API key in .env.
uv run python -m app
```

Open `http://localhost:8000`. Set `PORT` to use a different port. `python -m app` loads `.env` and starts Uvicorn without automatic reload. Existing environment variables take precedence over values in `.env`.

For development with automatic code reload:

```bash
uv run uvicorn app.main:app --env-file .env --reload
```

Configuration is validated at startup: missing required values or an invalid column mapping prevent the server from starting. Keep `.env` and API keys out of source control, and never put the key in frontend code.

## Connect Google Sheets

1. Enable the **Google Sheets API** in your Google Cloud project.
2. Create a server-side API key and restrict it to the Google Sheets API. If your hosting service has a fixed outbound IP address, also restrict the key to that IP. Do not use browser-referrer restrictions for a key used by the backend.
3. Make the spreadsheet readable by anyone with its link, without signing in. NextSet only reads the configured spreadsheet; it does not write to it.
4. Copy the ID between `/d/` and `/edit` in the spreadsheet URL into `GOOGLE_SHEETS_ID`.
5. Create two worksheets in that spreadsheet: **`AllSets`** for the complete catalog and **`Sets`** for curated sets. Both need the same required column headers.
6. Set `GOOGLE_SHEETS_RANGE` to an A1 range that includes the header and data rows, such as `AllSets!A1:P`.
7. Set `SHEET_COLUMN_MAP` to the actual column headers. Column order does not matter.

### Catalog selection

The **Only curated sets** switch appears below the filters and is off by default.

| Switch | Worksheet read |
| --- | --- |
| Off, the default | `AllSets` |
| On | `Sets` |

Changing the switch fetches the selected worksheet from the same `GOOGLE_SHEETS_ID`, resets the genre, duration, and year filters, and refreshes the filter options and set count. **Reset filters** keeps the selected catalog. Retrying a failed catalog load keeps the selected source; a full page reload starts with `AllSets` again. Each worksheet must be readable and contain the required headers, even if it has no data rows.

`GOOGLE_SHEETS_RANGE` controls the cell range used in either worksheet. NextSet replaces its worksheet prefix according to the switch: `AllSets!A1:P` reads `AllSets!A1:P` when off and `Sets!A1:P` when on. An existing configuration such as `'Sets'!A1:P` remains compatible and still defaults to `AllSets`; its `A1:P` portion is preserved.

| Variable | Value |
| --- | --- |
| `GOOGLE_SHEETS_ID` | Public spreadsheet ID; required |
| `GOOGLE_SHEETS_RANGE` | A1 cell range including the header row; required. The worksheet is selected by the switch. |
| `GOOGLE_SHEETS_API_KEY` | Server-side API key; required |
| `SHEET_COLUMN_MAP` | JSON object containing all five logical fields; required |
| `LOG_LEVEL` | Defaults to `INFO` |
| `PORT` | Defaults to `8000` |

`.env.example` contains the ID of [the supplied spreadsheet](https://docs.google.com/spreadsheets/d/1T01Q7k-0L0SCEz-aqWACO4BrK1ERsqgxW_DXKcdbIRc/edit) and the following column mapping. Replace the spreadsheet ID to use your own catalog.

```json
{"youtube_url":"LinkYoutube","title":"Artist","genres":"CustomGenres","duration_minutes":"Duration","year":"Year"}
```

| Logical field | Spreadsheet data |
| --- | --- |
| `youtube_url` | `LinkYoutube`: a `watch?v=`, `youtu.be/`, `/embed/`, or `/live/` URL with an 11-character video ID |
| `title` | Nonempty `Artist` text, followed by `@ EventName` and the matching country flag when those columns are present |
| `genres` | `CustomGenres`: comma-separated genres, such as `House, Tech House`; semicolons are also supported |
| `event_type` | Optional `EventType` column, shown before the genre tags in a distinct color |
| `duration_minutes` | `Duration`: a positive number of minutes, used for the shown duration |
| `duration_approx` | Optional `DurationApprox` value, used for the exact duration filter options (for example `30min`, `1h`, `1h 30min`) |
| `year` | `Year`: the performance year as a four-digit integer |

The backend requests unformatted numeric values from Sheets. A numeric cell entered using a decimal comma in an Italian spreadsheet is supported; a text value such as `92,5` or a time-of-day cell is not a substitute for a numeric duration in minutes.

Invalid rows and duplicate video IDs are skipped; the first valid row wins for each video. Genre names keep their original capitalization, with whitespace cleaned up. Duplicate names are matched case-insensitively and retain their first source spelling; genre filters also match case-insensitively. Missing or duplicate required headers invalidate the catalog. Extra columns are ignored. Log row numbers are relative to the range read; start the range at row 1 to match the spreadsheet's row numbers.

No visitor OAuth, YouTube Data API, published CSV endpoint, or Google credentials in the browser are needed. NextSet does not automatically fetch video metadata.

## Example CSV

[examples/sets.csv](examples/sets.csv) is an unchanged copy of the supplied `Sets` export, with **40 sets** and the original column names and genre casing.

To try the same schema in a new spreadsheet:

1. Import the CSV into a worksheet named `Sets`.
2. Create `AllSets` with the same header row. You can copy the example rows there initially and then add the rest of your catalog.
3. Configure the spreadsheet ID, API key, and column mapping as described above.

NextSet reads the five mapped columns and also uses `EventName` and `Country` to add `@ EventName [flag]` after each artist in the set title. The optional `EventType` column is shown before genres. The flag is added for countries in the configured flag dictionary; unknown country names leave the flag off. Other fields such as `ID`, `Link1001`, and `Score` do not affect selection. The CSV is sample input for Google Sheets, not an automatic production fallback or a local CSV data source.

## Behavior

- The catalog is read when the page opens or reloads, and when **Only curated sets** changes. Catalog responses are not cached. Filter changes and **NEXT SET** use the already loaded catalog.
- Filters are combined with AND: one genre, one year, and one exact `DurationApprox` value. The displayed duration continues to use `Duration`.
- Each random selection is uniform across eligible sets, excluding the current video when alternatives exist. Selection history is not persisted.
- Changing or resetting filters recreates the player from the beginning, even if the same single set remains. No matches remove the player; one match disables **NEXT SET**.
- Playback starts only when the visitor presses Play in YouTube. There is no autoplay and no automatic selection when a video ends.
- Events from old players are ignored after rapid filter changes. **NEXT SET** is disabled while the player loads; filters remain available.
- Google requests have an 8-second total deadline and at most one retry for network errors, HTTP 429, or HTTP 5xx. Browser catalog requests and player loading have 12-second timeouts.
- The app does not persist selections in cookies, localStorage, or the page URL. YouTube may use its own cookies in the embedded player.

A filter change restarts the video even when only one set matches.

## HTTP API

| Endpoint | Behavior |
| --- | --- |
| `GET /` | HTML page |
| `GET /static/{file}` | Local assets |
| `GET /api/catalog` | Reads `AllSets`; returns `{ "fetched_at": "…Z", "items": […] }` with `Cache-Control: no-store` |
| `GET /api/catalog?curated=false` | Explicitly reads `AllSets` |
| `GET /api/catalog?curated=true` | Reads `Sets` with the same response format and cache policy |
| `GET /healthz` | Returns `{ "status": "ok" }`; does not check Google |

Catalog errors use `{"error":{"code":"…","message":"…"}}`.

| HTTP | Code |
| --- | --- |
| 502 | `CATALOG_SCHEMA_INVALID` |
| 503 | `CATALOG_UNAVAILABLE` or `CATALOG_RATE_LIMITED` |
| 504 | `CATALOG_TIMEOUT` |
| 500 | `INTERNAL_ERROR` |

An invalid `curated` query value returns HTTP 422 using FastAPI's validation error format. `Retry-After` is forwarded when Google provides a valid value. Configuration errors and stack traces are not exposed to visitors.

## Docker and deployment

```bash
docker build -t nextset .
docker run --rm --env-file .env -p 8000:8000 nextset
```

The container uses the official Python image, dependencies from the lockfile, and an unprivileged user. Deploy it to a service that runs Python containers, configure secrets in the hosting environment, and terminate HTTPS at the proxy. The page and API must share the same domain and protocol; CORS is not required.

The app sets `X-Content-Type-Options: nosniff`, `Referrer-Policy: strict-origin-when-cross-origin`, and a Content Security Policy for the player. Do not override the referrer policy with `no-referrer`, which can cause YouTube error 153. Use `/healthz` for the process health check.

Before deploying with live data, check that both worksheets are readable through the API, the column mapping is correct, switching catalogs returns the intended rows, reloading reflects spreadsheet changes, and manual playback works on the final HTTPS domain. Hosting-level access restrictions are independent of the app's lack of user accounts.

## Static preview

The repository includes `scripts/catalog-snapshot.json`, a snapshot of **19 sets** from the `Sets` worksheet dated **2 October 2026**. It contains only the five normalized fields. This is a saved snapshot, not a backend cache or a live connection to Google Sheets.

To run the static preview locally without a Google API key:

```bash
python scripts/build_preview.py --catalog scripts/catalog-snapshot.json
python -m http.server 8000 --directory dist
```

The preview runs without Python application logic and does not synchronize with either worksheet. Its **Only curated sets** switch is disabled because it contains only one snapshot. Use the configured FastAPI service to switch between the current `AllSets` and `Sets` catalogs. Production never falls back to the snapshot when Google requests fail.

Running `python scripts/build_preview.py` without options builds a demo using five videos with example metadata.

## Tests

```bash
uv sync --frozen
uv run pytest -q
npm test
# Deterministic browser flows with a mocked catalog and YouTube SDK:
uv run playwright install chromium
RUN_BROWSER_TESTS=1 uv run pytest tests/test_browser.py -q -s
```

Node 20+ is needed only for JavaScript tests; production does not require Node or npm packages. Browser tests are disabled by default. `RUN_BROWSER_TESTS=1` enables them; if the browser is missing, the tests fail rather than silently skipping that issue.

See [TESTING.md](TESTING.md) for verification notes. Tests mock Google requests and the YouTube SDK to avoid credentials, network dependencies, and audio playback. Mocked playback does not establish that every real video can be embedded.

## Project structure

| Path | Responsibility |
| --- | --- |
| `app/main.py` | Routes, lifespan, shared HTTP client, headers, and errors |
| `app/config.py` | Configuration and column mapping validation |
| `app/catalog.py` | Sheets access, retries, timeouts, and normalization |
| `app/models.py` | JSON response contract |
| `app/static/` | Page, styles, state, selection logic, and player lifecycle |
| `tests/` | pytest, Node tests, and Playwright flows |
| `examples/sets.csv` | Original example spreadsheet export |
| `scripts/` | Static preview and source archive scripts |
| `uv.lock` | Locked Python dependencies with hashes |
| `LICENSE` | MIT software license |

The frontend also exposes two optional WebMCP tools when the browser supports them: reading the current selection and choosing a set with filters. They are not required to use the app.

Create a source-only archive, including the license and example CSV, with:

```bash
python scripts/package_source.py
```

The archive is written to `dist/NextSet.zip` and excludes secrets and generated caches.

## License

The project software and documentation are available under the [MIT License](LICENSE), a permissive license that allows reuse and modification while requiring the copyright and license notices to be retained. See the [official MIT license text](https://opensource.org/license/mit).

This software license does not grant rights to the music, videos, artwork, or other third-party content referenced by the catalog. Those rights remain with their respective owners.

## Official documentation

- [Google Sheets: spreadsheets.values.get](https://developers.google.com/workspace/sheets/api/reference/rest/v4/spreadsheets.values/get)
- [Google Cloud: API keys](https://cloud.google.com/docs/authentication/api-keys-use)
- [YouTube: IFrame Player API](https://developers.google.com/youtube/iframe_api_reference)
- [YouTube: player parameters](https://developers.google.com/youtube/player_parameters)
- [FastAPI: Docker](https://fastapi.tiangolo.com/deployment/docker/)
