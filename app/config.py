"""Configuration is server-only and validated before accepting requests."""
import json
import os
import re
from dataclasses import dataclass, field

FIELDS = ("youtube_url", "title", "genres", "duration_minutes", "year")

COUNTRY_FLAGS = {
    "Argentina": "🇦🇷",
    "Armenia": "🇦🇲",
    "Australia": "🇦🇺",
    "Belgium": "🇧🇪",
    "Bolivia": "🇧🇴",
    "Bosnia and Herzegovina": "🇧🇦",
    "Brasil": "🇧🇷",
    "Canada": "🇨🇦",
    "Colombia": "🇨🇴",
    "Croatia": "🇭🇷",
    "Egypt": "🇪🇬",
    "Finland": "🇫🇮",
    "France": "🇫🇷",
    "Iceland": "🇮🇸",
    "India": "🇮🇳",
    "Indonesia": "🇮🇩",
    "Italy": "🇮🇹",
    "Japan": "🇯🇵",
    "Jordan": "🇯🇴",
    "Maldives": "🇲🇻",
    "Malta": "🇲🇹",
    "Mexico": "🇲🇽",
    "Netherlands": "🇳🇱",
    "Norway": "🇳🇴",
    "Romania": "🇷🇴",
    "Singapore": "🇸🇬",
    "Sint Maarten": "🇸🇽",
    "Spain": "🇪🇸",
    "Sweden": "🇸🇪",
    "Switzerland": "🇨🇭",
    "Turkey": "🇹🇷",
    "Ukraine": "🇺🇦",
    "United Kingdom": "🇬🇧",
    "United States": "🇺🇸",
}


def normalize_header(value: str) -> str:
    return value.strip().casefold()


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate mapping key")
        result[key] = value
    return result


@dataclass(frozen=True)
class Settings:
    sheet_id: str
    sheet_range: str
    api_key: str = field(repr=False)
    column_map: dict[str, str]
    log_level: str = "INFO"

    def __post_init__(self):
        if not re.fullmatch(r"[A-Za-z0-9_-]+", self.sheet_id):
            raise ValueError("GOOGLE_SHEETS_ID non valido")
        if not self.sheet_range.strip() or not self.api_key.strip():
            raise ValueError("GOOGLE_SHEETS_RANGE e GOOGLE_SHEETS_API_KEY sono obbligatori")
        if not isinstance(self.column_map, dict) or set(self.column_map) != set(FIELDS):
            raise ValueError("SHEET_COLUMN_MAP deve associare esattamente i cinque campi logici")
        if any(not isinstance(v, str) or not v.strip() for v in self.column_map.values()):
            raise ValueError("SHEET_COLUMN_MAP contiene intestazioni non valide")
        if len({normalize_header(v) for v in self.column_map.values()}) != len(FIELDS):
            raise ValueError("SHEET_COLUMN_MAP contiene intestazioni duplicate")
        if self.log_level not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
            raise ValueError("LOG_LEVEL non valido")

    def catalog_range(self, curated: bool = False) -> str:
        """Reuse configured cells while selecting the requested catalog worksheet."""
        cells = self.sheet_range.rsplit("!", 1)[-1].strip()
        worksheet = "Sets" if curated else "AllSets"
        return f"{worksheet}!{cells}"

    @classmethod
    def from_env(cls):
        names = ("GOOGLE_SHEETS_ID", "GOOGLE_SHEETS_RANGE", "GOOGLE_SHEETS_API_KEY", "SHEET_COLUMN_MAP")
        missing = [name for name in names if not os.environ.get(name, "").strip()]
        if missing:
            raise ValueError("Configurazione mancante: " + ", ".join(missing))
        try:
            mapping = json.loads(os.environ["SHEET_COLUMN_MAP"], object_pairs_hook=_unique_object)
        except (ValueError, TypeError):
            raise ValueError("SHEET_COLUMN_MAP deve essere un oggetto JSON valido senza chiavi duplicate") from None
        return cls(os.environ[names[0]].strip(), os.environ[names[1]].strip(),
                   os.environ[names[2]].strip(), mapping, os.getenv("LOG_LEVEL", "INFO").upper())
