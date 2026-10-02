# NextSet

Webapp a pagina unica per estrarre un DJ set dal proprio Google Sheet e ascoltarlo nel player ufficiale YouTube. Backend **Python/FastAPI**, frontend **HTML, CSS e JavaScript nativi**, senza compilazione, database o account applicativi.

## Avvio rapido

Servono Python 3.12+ e [uv](https://docs.astral.sh/uv/getting-started/installation/).

```bash
uv sync --frozen
cp .env.example .env
# Il foglio e le colonne sono già configurati; impostare la propria API key.
uv run python -m app
```

Aprire `http://localhost:8000`. `PORT` modifica la porta. Il comando `python -m app` carica `.env` e avvia Uvicorn senza reload. Le variabili d'ambiente già impostate prevalgono sul file.

Per sviluppo con ricaricamento del codice:

```bash
uv run uvicorn app.main:app --env-file .env --reload
```

La configurazione è validata all'avvio: un valore obbligatorio mancante o un mapping invalido impedisce l'avvio. `.env` è escluso da Git e Docker. Non inserire la chiave nel frontend.

## Collegare Google Sheets

1. Abilitare **Google Sheets API** nel proprio progetto Google Cloud.
2. Creare una API key server e limitarla a Google Sheets API. Se l'hosting ha un IP di uscita fisso, limitare anche gli IP. Non applicare restrizioni per referrer a una chiave utilizzata dal backend.
3. Rendere il foglio leggibile da chiunque abbia il link, senza login. NextSet legge una sola fonte configurata e non scrive nel foglio.
4. Copiare l'ID fra `/d/` e `/edit` nell'URL del foglio in `GOOGLE_SHEETS_ID`.
5. Impostare `GOOGLE_SHEETS_RANGE` includendo intestazioni e righe. Il catalogo fornito usa `'Sets'!A1:P`.
6. Impostare `SHEET_COLUMN_MAP` con le intestazioni effettive. L'ordine delle colonne non conta.

| Variabile | Valore |
| --- | --- |
| `GOOGLE_SHEETS_ID` | ID del foglio pubblico, obbligatorio |
| `GOOGLE_SHEETS_RANGE` | Intervallo A1 con la riga di intestazione, obbligatorio |
| `GOOGLE_SHEETS_API_KEY` | Chiave server, obbligatoria |
| `SHEET_COLUMN_MAP` | JSON con tutti e cinque i campi logici, obbligatorio |
| `LOG_LEVEL` | `INFO` per impostazione predefinita |
| `PORT` | `8000` per impostazione predefinita |

Il file `.env.example` è già predisposto per [il foglio fornito](https://docs.google.com/spreadsheets/d/1T01Q7k-0L0SCEz-aqWACO4BrK1ERsqgxW_DXKcdbIRc/edit), scheda `Sets`. Il mapping verificato è:

```json
{"youtube_url":"LinkYoutube","title":"Artist","genres":"CustomGenres","duration_minutes":"Duration","year":"Year"}
```

| Campo logico | Dati nel foglio |
| --- | --- |
| `youtube_url` | URL `watch?v=`, `youtu.be/`, `/embed/` o `/live/`; ID di 11 caratteri |
| `title` | Testo non vuoto di `Artist`, usato come titolo del set |
| `genres` | `CustomGenres`: generi separati da virgole, ad esempio `House, Tech House`; è accettato anche `;` |
| `duration_minutes` | `Duration`: minuti numerici positivi, verificati nel foglio; non usare `DurationApprox` |
| `year` | Anno dell'esibizione, intero di quattro cifre |

Il backend richiede valori numerici non formattati a Sheets: una cella numerica inserita con la virgola nel foglio italiano va bene. Una stringa di testo come `92,5` o una cella oraria non sostituiscono una durata numerica in minuti.

Righe non valide e duplicati sono scartati; per i duplicati prevale la prima riga valida. I generi sono normalizzati e deduplicati. Intestazioni richieste assenti o duplicate invalidano il catalogo. Le colonne extra vengono ignorate. I log riportano il numero di riga relativo all'intervallo letto; per avere i numeri del foglio, iniziare l'intervallo dalla riga 1.

Non occorrono OAuth del visitatore, YouTube Data API, pubblicazione CSV o credenziali Google nel browser. Non vengono recuperati automaticamente metadati dai video.

## Comportamento

- Una lettura del catalogo all'apertura o ricarica; nessuna cache del catalogo e nessun aggiornamento durante la sessione.
- I filtri sono applicati localmente con AND. Genere singolo, anno singolo e durata: `< 60`, `60 ≤ durata < 120`, `≥ 120` minuti.
- Ogni estrazione è uniforme sui candidati, escludendo il set corrente quando esistono alternative. Nessuna cronologia persistente.
- Cambio filtro e reset ricreano sempre il player dall'inizio, anche se resta lo stesso unico set. Zero risultati rimuovono il player; un risultato disabilita “Altro DJ set”.
- Nessun autoplay, audio avviato dal solo Play di YouTube, nessun cambio alla fine del video.
- Cambio rapido dei filtri: gli eventi dei vecchi player sono ignorati. “Altro DJ set” è disabilitato durante il caricamento, i filtri rimangono disponibili.
- Timeout Google complessivo di 8 secondi e al massimo un retry per rete, 429 o 5xx; timeout browser e player di 12 secondi.
- Nessun uso applicativo di cookie, localStorage o parametri URL per le selezioni. YouTube può utilizzare propri cookie nel player incorporato.

In caso di differenze fra i documenti, prevalgono le specifiche tecniche e il documento funzionale con **genere, durata e anno**. Quindi 120 minuti appartengono alla fascia `≥ 120` e un cambio filtro ripristina il video anche con un solo candidato.

## Contratto HTTP

| Endpoint | Comportamento |
| --- | --- |
| `GET /` | Pagina HTML |
| `GET /static/{file}` | Asset locali |
| `GET /api/catalog` | `{ "fetched_at": "…Z", "items": […] }`, `Cache-Control: no-store` |
| `GET /healthz` | `{ "status": "ok" }`; non verifica Google |

Gli errori hanno forma `{"error":{"code":"…","message":"…"}}`.

| HTTP | Codice |
| --- | --- |
| 502 | `CATALOG_SCHEMA_INVALID` |
| 503 | `CATALOG_UNAVAILABLE` oppure `CATALOG_RATE_LIMITED` |
| 504 | `CATALOG_TIMEOUT` |
| 500 | `INTERNAL_ERROR` |

`Retry-After` è riportato quando Google fornisce un valore valido. Errori di configurazione o stack trace non vengono esposti al visitatore.

## Docker e rilascio

```bash
docker build -t nextset .
docker run --rm --env-file .env -p 8000:8000 nextset
```

Il container usa Python ufficiale, dipendenze del lockfile e un utente senza privilegi. Distribuirlo su un servizio che esegua container Python, impostare i segreti nell'hosting e terminare HTTPS sul proxy. Pagina e API devono condividere dominio e protocollo; non serve CORS.

Sono già impostati `X-Content-Type-Options: nosniff`, `Referrer-Policy: strict-origin-when-cross-origin` e CSP per il player. Non sovrascrivere il referrer con `no-referrer`: può causare errore YouTube 153. Configurare `/healthz` per il controllo di processo.

Prima del rilascio con dati reali: verificare lettura anonima del foglio via API, corrispondenza delle colonne, aggiornamento dopo ricarica e riproduzione manuale di un video sul dominio HTTPS definitivo. L'assenza di un account nell'app non modifica eventuali restrizioni di accesso imposte dall'hosting.

## Anteprima con il catalogo reale

L'anteprima ospitata è **statica** e privata. Dal 2 ottobre 2026 usa una copia dei **19 set** letti dal foglio `Sets`, con metadati effettivi. Mostra la data della copia e che la sincronizzazione automatica non è attiva. L'accesso pubblico alla pagina del foglio è stato verificato; la lettura tramite Google Sheets API richiede ancora la chiave del proprietario.

La copia è in `scripts/catalog-snapshot.json` e contiene soltanto i cinque campi normalizzati. Non è una cache del backend né un collegamento continuo al foglio. L'anteprima non esegue Python: per la sincronizzazione ad ogni ricarica serve distribuire il servizio FastAPI su un hosting Python e configurare la chiave server.

Per riprodurla localmente senza chiave Google:

```bash
python scripts/build_preview.py --catalog scripts/catalog-snapshot.json
python -m http.server 8000 --directory dist
```

Il backend di produzione non usa mai questa copia come ripiego in caso di errore. Per un catalogo aggiornato ad ogni apertura avviare il servizio FastAPI configurato. `python scripts/build_preview.py` senza opzioni continua a creare la demo originale con cinque video e metadati di esempio.

## Test

```bash
uv sync --frozen
uv run pytest -q
npm test
# Flussi browser deterministici (catalogo e SDK YouTube simulati):
uv run playwright install chromium
RUN_BROWSER_TESTS=1 uv run pytest tests/test_browser.py -q -s
```

Node 20+ è necessario solo per i sei test JavaScript; non servono pacchetti npm né Node in produzione. I test browser sono disabilitati per impostazione predefinita. `RUN_BROWSER_TESTS=1` li abilita e, se il browser manca, falliscono senza nascondere il problema.

Vedere [TESTING.md](TESTING.md) per risultati e verifiche non eseguite. Le chiamate Google e l'SDK YouTube sono simulati nei test, per evitare credenziali, rete e riproduzione di audio. Una simulazione non certifica la riproducibilità reale dei video.

## Struttura

| Percorso | Responsabilità |
| --- | --- |
| `app/main.py` | Route, lifespan, client HTTP condiviso, header ed errori |
| `app/config.py` | Validazione configurazione e mapping |
| `app/catalog.py` | Accesso Sheets, retry, timeout, normalizzazione |
| `app/models.py` | Contratto JSON |
| `app/static/` | Pagina, stile, stato, selezione pura, ciclo di vita del player |
| `tests/` | pytest, test Node e flussi Playwright |
| `scripts/` | Build separata dell'anteprima statica |
| `uv.lock` | Dipendenze Python bloccate con hash |

Il frontend offre anche due strumenti WebMCP, quando supportati dal browser: lettura della selezione e scelta di un set con filtri. Sono un miglioramento facoltativo e non sono necessari per usare l'app.

## Documentazione ufficiale

- [Google Sheets: spreadsheets.values.get](https://developers.google.com/workspace/sheets/api/reference/rest/v4/spreadsheets.values/get)
- [Google Cloud: API keys](https://cloud.google.com/docs/authentication/api-keys-use)
- [YouTube: IFrame Player API](https://developers.google.com/youtube/iframe_api_reference)
- [YouTube: parametri del player](https://developers.google.com/youtube/player_parameters)
- [FastAPI: Docker](https://fastapi.tiangolo.com/deployment/docker/)
