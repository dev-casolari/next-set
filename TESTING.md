# Resoconto di verifica

Aggiornamento: 2 ottobre 2026. Ambiente: Linux x86_64, Python 3.12.14, Node 24.19.0.

## Foglio fornito

- Accesso anonimo alla pagina del Google Sheet verificato il 2 ottobre 2026; scheda `Sets`.
- Verificato il mapping `LinkYoutube`, `Artist`, `Year`, `CustomGenres`, con la colonna aggiuntiva `Duration` numerica in minuti.
- Normalizzati 19 set validi senza duplicati, con 19 generi distinti e durate da 44 a 154 minuti. I generi sono separati sulle virgole, ripuliti e deduplicati; resta supportato il separatore `;` originale.
- Anteprima aggiornata con una copia esplicitamente datata del catalogo. La lettura API automatica non è attiva: manca la chiave Google Sheets sul server e l'anteprima ospitata è statica.
- Aggiunto un test di regressione con lo schema del foglio fornito e generi separati da virgole.

## Eseguito

- **53 test pytest superati**: formati URL ammessi, host rifiutati, mapping e intestazioni, valori mancanti o invalidi, normalizzazione, duplicati, configurazione, contratto HTTP, header, nessuna esposizione della chiave, lettura nuova a ogni chiamata, catalogo vuoto, codici di errore, retry e limite temporale complessivo, schema reale e separazione dei generi sulle virgole.
- **6 test JavaScript superati**: confini 59,99/60/119,99/120 minuti, filtri AND, raggiungibilità degli indici della selezione uniforme, esclusione immediata del set corrente, zero/unico candidato, opzioni, metadati, distruzione del player precedente, callback tardivi ignorati, cue da zero, nessuna azione a fine video, errore e timeout recuperabili.
- **Benchmark Node**: 1.000 set, 1.000 estrazioni con filtri; media rilevata **0,021 ms per estrazione**. Misura della logica pura nel runtime Node, non del browser né della rete/player. Il test Playwright incluso misura separatamente la stessa operazione nel browser.

## Predisposto ma non eseguito

- Suite Playwright con catalogo e SDK YouTube simulati: interazione con filtri/reset, nessuna richiesta catalogo aggiuntiva, stati zero/unico candidato, assenza autoplay, cambio rapido, errori, ritorno dalla cache di navigazione, testo non interpretato come HTML, tastiera e viewport 320/390/768/1440 px.
- Verifica browser delle azioni WebMCP tramite registro simulato. Un contesto WebMCP nativo non era disponibile.
- Le prove browser non sono state eseguite: il download del browser Playwright in questo ambiente ha restituito un archivio inutilizzabile. Non è stata effettuata una verifica visiva del layout.

## Da eseguire prima del rilascio con dati reali

- Accesso al Google Sheet effettivo con chiave e mapping del proprietario; aggiunta/modifica/rimozione visibili alla ricarica.
- Riproduzione reale in HTTPS, controlli YouTube, errore 153/referrer e CSP sul dominio finale.
- Chrome, Firefox e Safari; Android e iOS reali; zoom testo al 200%.
- Build ed esecuzione Docker sul servizio di destinazione.

L'anteprima statica utilizza una copia del catalogo reale del 2 ottobre 2026. ID, intervallo e mapping sono configurati. La lettura Google Sheets API del backend richiede ancora la chiave; il suo collaudo reale e la distribuzione su hosting Python restano da completare.
