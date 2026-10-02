"""Build a labelled static preview, never the production backend."""
import argparse
from datetime import datetime
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--catalog", type=Path, help="Normalized catalog snapshot instead of demo data")
args = parser.parse_args()
catalog_path = args.catalog.resolve() if args.catalog else ROOT / "scripts/demo-catalog.json"
catalog = json.loads(catalog_path.read_text())
date = datetime.fromisoformat(catalog["fetched_at"].replace("Z", "+00:00")).strftime("%d/%m/%Y")
notice = (f"Anteprima · Catalogo del tuo foglio aggiornato al {date}. Sincronizzazione automatica non attiva."
          if args.catalog else "Anteprima · Catalogo dimostrativo con metadati di esempio. Il tuo Google Sheet non è collegato.")
DIST.mkdir(exist_ok=True)
shutil.copytree(ROOT / "app/static", DIST / "static", dirs_exist_ok=True)
html = (ROOT / "app/static/index.html").read_text()
html = html.replace("<body>", '<body data-preview="true">')
html = html.replace("Anteprima · Catalogo dimostrativo, non collegato al tuo Google Sheet.", notice)
(DIST / "index.html").write_text(html)
shutil.copyfile(catalog_path, DIST / "preview-catalog.json")
# These headers apply to the static demonstration where the host supports _headers.
(DIST / "_headers").write_text("/*\n  X-Content-Type-Options: nosniff\n  Referrer-Policy: strict-origin-when-cross-origin\n/preview-catalog.json\n  Cache-Control: no-store\n")
print("Static NextSet demonstration written to dist/")
