import asyncio
from datetime import datetime, timezone
import json

import httpx
import pytest
from fastapi.testclient import TestClient

from app import catalog as module
from app.catalog import CatalogError, extract_youtube_id, fetch_catalog, normalize_catalog, retry_after_seconds
from app.config import Settings
from app.main import create_app

MAPPING = {"youtube_url":"Link", "title":"Titolo", "genres":"Generi", "duration_minutes":"Minuti", "year":"Anno"}
HEADERS = list(MAPPING.values())
VALID = ["https://www.youtube.com/watch?v=AbCdEf12345", " A set ", " HOUSE ; Deep   House;house ", 60, 2024]


@pytest.fixture
def settings():
    return Settings("sheet_id", "'DJ Sets'!A1:Z", "unit-test-key", MAPPING)


@pytest.mark.parametrize("url", [
    "https://youtube.com/watch?v=AbCdEf12345&t=4&list=abc",
    "http://www.youtube.com/watch?v=AbCdEf12345", "https://m.youtube.com/watch?v=AbCdEf12345",
    "https://youtu.be/AbCdEf12345?t=5", "https://youtube.com/embed/AbCdEf12345", "https://youtube.com/live/AbCdEf12345",
])
def test_supported_url_forms(url):
    assert extract_youtube_id(url) == "AbCdEf12345"


@pytest.mark.parametrize("url", [None,"javascript:alert(1)","https://youtube.com.evil.test/watch?v=AbCdEf12345","https://evil.test/AbCdEf12345","https://youtube.com/shorts/AbCdEf12345","https://youtube.com/watch?v=short","https://youtu.be/AbCdEf12345/extra","https://user@youtube.com/watch?v=AbCdEf12345"])
def test_rejects_unapproved_urls(url):
    with pytest.raises(ValueError): extract_youtube_id(url)


def test_normalization_dedup_first_valid_and_mapping():
    rows = [HEADERS, [], VALID[:2], VALID, ["https://youtu.be/AbCdEf12345", "Duplicate", "techno", 100, 2025]]
    items = normalize_catalog({"values":rows}, MAPPING)
    assert len(items) == 1
    assert items[0].title == "A set"
    assert items[0].genres == ["house", "deep house"]
    assert items[0].duration_minutes == 60
    assert items[0].year == 2024
    assert normalize_catalog({"values":[HEADERS]}, MAPPING) == []


def test_reordered_case_insensitive_headers_and_extra_columns():
    indexes = [4, 0, 3, 2, 1]
    rows = [["EXTRA"] + [f" {HEADERS[i].upper()} " for i in indexes], ["unused"] + [VALID[i] for i in indexes]]
    assert normalize_catalog({"values":rows}, MAPPING)[0].title == "A set"


def test_owner_sheet_mapping_and_comma_separated_genres():
    mapping = {"youtube_url":"LinkYoutube", "title":"Artist", "genres":"CustomGenres", "duration_minutes":"Duration", "year":"Year"}
    rows = [
        ["ID", "LinkYoutube", "Link1001", "Artist", "Year", "Date", "Country", "EventName", "EventType", "Genres1001", "Duration", "DurationApprox", "CustomGenres"],
        [1, "https://www.youtube.com/watch?v=UVNsiVq_vX8", "", "Axwell", 2025, "18/07/2025", "Belgium", "Tomorrowland", "Festival", "Mainstage", 59, "1h", " EDM, Mainstage, Progressive   House, edm, Electro House, "],
    ]
    result = normalize_catalog({"values":rows}, mapping)
    assert len(result) == 1
    assert result[0].title == "Axwell"
    assert result[0].year == 2025
    assert result[0].duration_minutes == 59
    assert result[0].genres == ["edm", "mainstage", "progressive house", "electro house"]
    assert "Country" not in result[0].model_dump()


@pytest.mark.parametrize("field,value", [(1," "),(2,";;"),(2,[]),(3,0),(3,-1),(3,"nan"),(3,"inf"),(3,True),(3,"01:30"),(4,True),(4,2024.5),(4,999),(4,"20x4")])
def test_invalid_cells_are_skipped(field, value):
    row = VALID.copy(); row[field] = value
    assert normalize_catalog({"values":[HEADERS,row]}, MAPPING) == []


@pytest.mark.parametrize("payload", [{}, {"values":[]}, {"values":[HEADERS+[' titolo ']]}, {"values":[HEADERS[:-1]]}, {"values":[HEADERS,"bad"]}, {"values":[HEADERS],"majorDimension":"COLUMNS"}])
def test_bad_schema_fails_entire_catalog(payload):
    with pytest.raises(CatalogError) as result: normalize_catalog(payload, MAPPING)
    assert result.value.code == "CATALOG_SCHEMA_INVALID"


def test_configuration_is_required_and_secret_safe(monkeypatch):
    for name in ["GOOGLE_SHEETS_ID","GOOGLE_SHEETS_RANGE","GOOGLE_SHEETS_API_KEY","SHEET_COLUMN_MAP"]:
        monkeypatch.delenv(name, raising=False)
    with pytest.raises(ValueError, match="Configurazione mancante"): Settings.from_env()
    for name, value in {"GOOGLE_SHEETS_ID":"abc", "GOOGLE_SHEETS_RANGE":"Sets!A:Z", "GOOGLE_SHEETS_API_KEY":"DO_NOT_PRINT", "SHEET_COLUMN_MAP":json.dumps(MAPPING)}.items():
        monkeypatch.setenv(name,value)
    assert "DO_NOT_PRINT" not in repr(Settings.from_env())
    monkeypatch.setenv("SHEET_COLUMN_MAP",'{"title":"a","title":"b"}')
    with pytest.raises(ValueError,match="JSON valido"): Settings.from_env()


def test_http_routes_fresh_read_security_and_no_key_leak(settings):
    requests = []
    def upstream(request):
        requests.append(request)
        assert request.headers["X-Goog-Api-Key"] == "unit-test-key"
        assert request.url.params["valueRenderOption"] == "UNFORMATTED_VALUE"
        assert request.url.params["majorDimension"] == "ROWS"
        rows = [HEADERS, VALID] if len(requests) == 1 else [HEADERS]
        return httpx.Response(200, json={"values":rows})
    with TestClient(create_app(settings,httpx.MockTransport(upstream))) as client:
        assert client.get("/healthz").json() == {"status":"ok"}
        assert requests == []
        for path in ["/", "/static/app.js", "/static/player.js", "/static/styles.css"]:
            response = client.get(path)
            assert response.status_code == 200
            assert "unit-test-key" not in response.text
            assert response.headers["referrer-policy"] == "strict-origin-when-cross-origin"
            assert response.headers["x-content-type-options"] == "nosniff"
        result = client.get("/api/catalog")
        assert result.headers["cache-control"] == "no-store"
        assert len(result.json()["items"]) == 1
        assert set(result.json()["items"][0]) == {"youtube_id","title","genres","duration_minutes","year"}
        assert datetime.fromisoformat(result.json()["fetched_at"].replace("Z","+00:00")).tzinfo == timezone.utc
        assert client.get("/api/catalog").json()["items"] == []
        assert len(requests) == 2


@pytest.mark.parametrize("status,expected_code,expected_status", [(400,"CATALOG_UNAVAILABLE",503),(401,"CATALOG_UNAVAILABLE",503),(403,"CATALOG_UNAVAILABLE",503),(404,"CATALOG_UNAVAILABLE",503),(429,"CATALOG_RATE_LIMITED",503),(500,"CATALOG_UNAVAILABLE",503)])
def test_upstream_errors_and_retry_after(settings,status,expected_code,expected_status):
    calls = []
    def upstream(request):
        calls.append(request)
        return httpx.Response(status,headers={"Retry-After":"60"})
    with TestClient(create_app(settings,httpx.MockTransport(upstream))) as client:
        response = client.get("/api/catalog")
        assert response.status_code == expected_status
        assert response.json()["error"]["code"] == expected_code
        assert response.headers["cache-control"] == "no-store"
        assert response.headers["retry-after"] == "60"
        assert len(calls) == 1


@pytest.mark.parametrize("first", [429,500,502,"network","timeout"])
async def test_exactly_one_retry_can_recover(settings,monkeypatch,first):
    attempts=[]; waits=[]
    async def sleep(delay): waits.append(delay)
    monkeypatch.setattr(module.asyncio,"sleep",sleep)
    def upstream(request):
        attempts.append(request)
        if len(attempts) == 1:
            if first == "network": raise httpx.ConnectError("secret",request=request)
            if first == "timeout": raise httpx.ReadTimeout("secret",request=request)
            return httpx.Response(first)
        return httpx.Response(200,json={"values":[HEADERS,VALID]})
    async with httpx.AsyncClient(transport=httpx.MockTransport(upstream)) as client:
        assert len((await fetch_catalog(client,settings)).items) == 1
    assert len(attempts) == 2 and len(waits) == 1 and .5 <= waits[0] <= 1


async def test_retry_limit_and_timeout_contract(settings,monkeypatch):
    calls=[]
    async def no_sleep(_): pass
    monkeypatch.setattr(module.asyncio,"sleep",no_sleep)
    def upstream(request):
        calls.append(request)
        raise httpx.ReadTimeout("never expose this",request=request)
    async with httpx.AsyncClient(transport=httpx.MockTransport(upstream)) as client:
        with pytest.raises(CatalogError) as result: await fetch_catalog(client,settings)
    assert result.value.code == "CATALOG_TIMEOUT" and result.value.status == 504
    assert len(calls) == 2


async def test_total_deadline(settings,monkeypatch):
    monkeypatch.setattr(module,"TOTAL_TIMEOUT",.02)
    async def upstream(request):
        await asyncio.sleep(.1)
        return httpx.Response(200,json={"values":[HEADERS]})
    async with httpx.AsyncClient(transport=httpx.MockTransport(upstream)) as client:
        with pytest.raises(CatalogError) as result: await fetch_catalog(client,settings)
    assert result.value.code == "CATALOG_TIMEOUT"


def test_bad_google_json_and_internal_error_contract(settings):
    with TestClient(create_app(settings,httpx.MockTransport(lambda request: httpx.Response(200,text="bad json")))) as client:
        response=client.get("/api/catalog")
        assert response.status_code == 502 and response.json()["error"]["code"] == "CATALOG_SCHEMA_INVALID"
    def explode(request): raise RuntimeError("SECRET")
    with TestClient(create_app(settings,httpx.MockTransport(explode)),raise_server_exceptions=False) as client:
        response=client.get("/api/catalog")
        assert response.status_code == 500 and response.json()["error"]["code"] == "INTERNAL_ERROR"
        assert "SECRET" not in response.text


def test_retry_after_formats():
    assert retry_after_seconds("3") == 3
    assert retry_after_seconds("Wed, 21 Oct 2015 07:28:00 GMT") == 0
    assert retry_after_seconds("bad") is None
