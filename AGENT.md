# Run NextSet locally

NextSet is a FastAPI app with a plain HTML/CSS/JavaScript frontend. There is no frontend build step. The backend reads its catalog from Google Sheets, so the app needs valid Google Sheets configuration to start.

## Requirements

- Python 3.12 or newer
- `curl` for the `uv` installer
- A Google Sheet readable without signing in, plus a server-side Google Sheets API key

## 1. Open the project directory

In a terminal, change to the repository directory:

```bash
cd /workspaces/next-set
```

If you cloned the project somewhere else, use that directory instead.

## 2. Install uv

Check whether `uv` is already installed:

```bash
uv --version
```

If Bash reports `uv: command not found`, install it on Linux/macOS using the official installer:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Open a new terminal, return to the project directory, and verify:

```bash
uv --version
```

If it is still not found in the current Bash session, add the usual user install directory to `PATH`:

```bash
export PATH="$HOME/.local/bin:$PATH"
uv --version
```

## 3. Install Python dependencies

From the project root, run:

```bash
uv sync --frozen
```

This creates/updates the project virtual environment and installs the locked runtime and development dependencies.

## 4. Configure Google Sheets

Create a local `.env` file from the template:

```bash
cp .env.example .env
```

Edit `.env` and verify or set these values:

```dotenv
GOOGLE_SHEETS_ID=your_spreadsheet_id
GOOGLE_SHEETS_RANGE="AllSets!A1:P"
GOOGLE_SHEETS_API_KEY=your_server_side_api_key
SHEET_COLUMN_MAP='{"youtube_url":"LinkYoutube","title":"Artist","genres":"CustomGenres","duration_minutes":"Duration","year":"Year"}'
LOG_LEVEL=INFO
PORT=8000
```

Configure the Google Sheet and API key if you do not already have them:

1. Enable the Google Sheets API in a Google Cloud project and create an API key for server-side use. Restrict the key to the Google Sheets API; do not use browser-referrer restrictions for this backend key.
2. Make the spreadsheet readable by anyone with its link, without signing in. NextSet only reads the sheet.
3. Set `GOOGLE_SHEETS_ID` to the ID between `/d/` and `/edit` in the spreadsheet URL.
4. Create worksheets named `AllSets` and `Sets`. Both need the required headers. The app reads `AllSets` by default; the “Only curated sets” switch reads `Sets`.
5. Set `GOOGLE_SHEETS_RANGE` to an A1 range that includes the header row and data, for example `AllSets!A1:P`. The app selects the worksheet tab based on the switch.
6. Set `SHEET_COLUMN_MAP` to a JSON object mapping the five logical fields (`youtube_url`, `title`, `genres`, `duration_minutes`, and `year`) to the exact header text in your sheet. Column order does not matter.

Keep `.env` and API keys private. Do not paste the API key into frontend files or commit `.env`. Existing environment variables take precedence over values in `.env`. The app validates required configuration at startup and will not start if it is missing or invalid.

## 5. Start the app

For local development with automatic reload:

```bash
uv run uvicorn app.main:app --env-file .env --reload
```

Alternatively, start without automatic reload:

```bash
uv run python -m app
```

Open [http://localhost:8000](http://localhost:8000) in your browser. To use another port, set `PORT` in `.env`.

Stop the server with `Ctrl+C`.

## 6. Run tests (optional)

Run the backend catalog tests:

```bash
uv run pytest tests/test_catalog.py -q
```

Run the complete Python test suite:

```bash
uv run pytest -q
```

The tests mock Google Sheets requests and do not need a live API key or spreadsheet. The frontend tests use Node.js and npm:

```bash
npm ci
npm test
```
