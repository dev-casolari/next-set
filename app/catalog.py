"""Read Google Sheets once per request; never cache data or fetch cell URLs."""
import asyncio
import logging
import math
import random
import re
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import parse_qs, quote, urlsplit

import httpx

from app.config import FIELDS, Settings, normalize_header
from app.models import CatalogResponse, DJSet

logger = logging.getLogger("nextset.catalog")
VIDEO_ID = re.compile(r"^[A-Za-z0-9_-]{11}$")
TOTAL_TIMEOUT = 8.0
REQUEST_TIMEOUT = 3.5
ERRORS = {
    "CATALOG_SCHEMA_INVALID": (502, "Il catalogo non ha il formato previsto. Riprova più tardi."),
    "CATALOG_UNAVAILABLE": (503, "Catalogo non disponibile. Riprova più tardi."),
    "CATALOG_RATE_LIMITED": (503, "Il catalogo è temporaneamente occupato. Riprova più tardi."),
    "CATALOG_TIMEOUT": (504, "Il catalogo sta impiegando troppo tempo. Riprova più tardi."),
    "INTERNAL_ERROR": (500, "Si è verificato un errore. Riprova più tardi."),
}


class CatalogError(Exception):
    def __init__(self, code: str, retry_after: int | None = None):
        self.code = code
        self.status, self.message = ERRORS[code]
        self.retry_after = retry_after
        super().__init__(code)


def extract_youtube_id(value) -> str:
    if not isinstance(value, str):
        raise ValueError("youtube_url mancante o non testuale")
    try:
        url = urlsplit(value.strip())
        if url.scheme not in {"http", "https"} or url.username or url.password:
            raise ValueError()
        host = url.hostname
        if host not in {"youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be"}:
            raise ValueError()
        if url.port not in {None, 80, 443}:
            raise ValueError()
        if host == "youtu.be":
            candidate = url.path.removeprefix("/")
        elif url.path == "/watch":
            candidate = parse_qs(url.query).get("v", [""])[0]
        else:
            match = re.fullmatch(r"/(?:embed|live)/([A-Za-z0-9_-]{11})", url.path)
            candidate = match.group(1) if match else ""
        if not VIDEO_ID.fullmatch(candidate):
            raise ValueError()
        return candidate
    except ValueError:
        raise ValueError("youtube_url non supportato") from None


def parse_row(values: dict) -> DJSet:
    video_id = extract_youtube_id(values["youtube_url"])
    title = values["title"]
    if not isinstance(title, str) or not title.strip():
        raise ValueError("title mancante")
    genre_cell = values["genres"]
    if not isinstance(genre_cell, str):
        raise ValueError("genres non validi")
    # CustomGenres uses commas; keep compatibility with semicolon catalogs.
    genres = list(dict.fromkeys(" ".join(g.split()).lower() for g in re.split(r"[,;]", genre_cell) if g.strip()))
    if not genres:
        raise ValueError("genres mancanti")
    duration = values["duration_minutes"]
    if isinstance(duration, bool) or not isinstance(duration, (str, int, float)):
        raise ValueError("duration_minutes non valida")
    try:
        duration = float(duration)
    except (ValueError, OverflowError):
        raise ValueError("duration_minutes non valida") from None
    if not math.isfinite(duration) or duration <= 0:
        raise ValueError("duration_minutes non positiva o non finita")
    year = values["year"]
    if isinstance(year, bool) or not isinstance(year, (str, int, float)):
        raise ValueError("year non valido")
    if isinstance(year, str):
        if not re.fullmatch(r"[0-9]{4}", year.strip()):
            raise ValueError("year deve avere quattro cifre")
        year = int(year.strip())
    if not math.isfinite(year) or year != int(year) or not 1000 <= year <= 9999:
        raise ValueError("year non valido")
    return DJSet(youtube_id=video_id, title=title.strip(), genres=genres,
                 duration_minutes=duration, year=int(year))


def normalize_catalog(payload, column_map: dict[str, str]) -> list[DJSet]:
    if not isinstance(payload, dict) or payload.get("majorDimension", "ROWS") != "ROWS":
        raise CatalogError("CATALOG_SCHEMA_INVALID")
    rows = payload.get("values")
    if not isinstance(rows, list) or not rows or any(not isinstance(r, list) for r in rows):
        raise CatalogError("CATALOG_SCHEMA_INVALID")
    headers = [normalize_header(x) if isinstance(x, str) else "" for x in rows[0]]
    indexes = {}
    for field in FIELDS:
        header = normalize_header(column_map[field])
        if headers.count(header) != 1:
            logger.warning("catalog_schema_invalid field=%s reason=missing_or_duplicate_header", field)
            raise CatalogError("CATALOG_SCHEMA_INVALID")
        indexes[field] = headers.index(header)
    items, seen = [], set()
    for row_number, row in enumerate(rows[1:], start=2):
        cells = {field: row[index] if index < len(row) else None for field, index in indexes.items()}
        try:
            item = parse_row(cells)
        except (ValueError, TypeError, OverflowError) as error:
            # Reasons come exclusively from our validators, never cell contents.
            logger.warning("catalog_row_skipped row=%s reason=%s", row_number, str(error))
            continue
        if item.youtube_id in seen:
            logger.info("catalog_row_skipped row=%s reason=duplicate_video", row_number)
            continue
        seen.add(item.youtube_id)
        items.append(item)
    logger.info("catalog_normalized valid_rows=%s discarded_rows=%s", len(items), len(rows) - 1 - len(items))
    return items


def retry_after_seconds(value: str | None) -> int | None:
    if not value:
        return None
    try:
        if re.fullmatch(r"\d+", value.strip()):
            return int(value.strip())
        date = parsedate_to_datetime(value)
        if date.tzinfo is None:
            date = date.replace(tzinfo=timezone.utc)
        return max(0, math.ceil((date - datetime.now(timezone.utc)).total_seconds()))
    except (ValueError, TypeError, OverflowError):
        return None


async def fetch_catalog(client: httpx.AsyncClient, settings: Settings) -> CatalogResponse:
    started = time.monotonic()
    url = f"https://sheets.googleapis.com/v4/spreadsheets/{settings.sheet_id}/values/{quote(settings.sheet_range, safe='')}"
    final_status = "error"
    try:
        async with asyncio.timeout(TOTAL_TIMEOUT):
            for attempt in range(2):
                remaining = TOTAL_TIMEOUT - (time.monotonic() - started)
                retry_after = None
                try:
                    response = await client.get(
                        url, params={"majorDimension": "ROWS", "valueRenderOption": "UNFORMATTED_VALUE"},
                        headers={"X-Goog-Api-Key": settings.api_key},
                        timeout=min(REQUEST_TIMEOUT, remaining),
                    )
                except httpx.TimeoutException:
                    error = CatalogError("CATALOG_TIMEOUT")
                except httpx.RequestError:
                    error = CatalogError("CATALOG_UNAVAILABLE")
                else:
                    logger.info("google_read attempt=%s http_status=%s", attempt + 1, response.status_code)
                    if response.status_code == 200:
                        fetched_at = datetime.now(timezone.utc)
                        try:
                            payload = response.json()
                        except (ValueError, UnicodeDecodeError):
                            raise CatalogError("CATALOG_SCHEMA_INVALID") from None
                        items = normalize_catalog(payload, settings.column_map)
                        final_status = "ok"
                        return CatalogResponse(fetched_at=fetched_at, items=items)
                    retry_after = retry_after_seconds(response.headers.get("Retry-After"))
                    code = "CATALOG_RATE_LIMITED" if response.status_code == 429 else "CATALOG_UNAVAILABLE"
                    error = CatalogError(code, retry_after)
                    if response.status_code != 429 and response.status_code < 500:
                        raise error
                remaining = TOTAL_TIMEOUT - (time.monotonic() - started)
                delay = max(random.uniform(0.5, 1.0), retry_after or 0)
                if attempt == 1 or delay >= remaining:
                    raise error
                await asyncio.sleep(delay)
    except TimeoutError:
        raise CatalogError("CATALOG_TIMEOUT") from None
    finally:
        logger.info("catalog_read outcome=%s duration_ms=%.1f", final_status, (time.monotonic() - started) * 1000)
    raise CatalogError("CATALOG_UNAVAILABLE")
