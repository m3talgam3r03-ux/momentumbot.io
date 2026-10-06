# CHANGELOG

## [0.8.0] - 2026-10-06
### Aggiunto
- `classifier/updates.py`: CANCEL (LIMIT ORDER CANCELLED), CLOSE_FULL (OUT OF TRADE, TRADE COMPLETE), MOVE_BE (istruzioni BE in italiano e inglese), risultati, pre-annunci, riepiloghi, didascalie dei grafici; le istruzioni manuali restano AMBIGUOUS.
- Motore decisionale: CANCEL/CLOSE/MODIFY sul segnale collegato; BE solo se attivato (D5); HEADS UP solo notifica (D4); regole S5/S6/S8 anche sugli aggiornamenti.
- Registro: collegamento risposta → segnale (anche tramite i doppioni), versione dello schema (v2) con rifiuto dei registri vecchi.
### Impatto sui follower
Nessuno oggi (PAPER). Quando l'esecuzione sarà attiva: un pendente annullato dal fornitore verrà cancellato anche sul master (e quindi, se FPG lo replica, sui follower); un "OUT OF TRADE" chiuderà la posizione collegata.

## [0.7.0] - 2026-10-06
### Aggiunto
- `exporter/desktop_html.py`: lettura dell'export HTML di Telegram Desktop (+ `python -m momentum_master.exporter.desktop_html`).
- `docs/analisi_storico_2026-10-06.md`: classificatore su 1976 messaggi reali (399 aperture, 0 discordanze, 0 falsi segnali), doppioni, catalogo completo, esiti dichiarati dal fornitore.
- Catalogo dei formati v0.2; test con testi esatti dall'export (`tests/data/wdt_real_samples.json`).
### Impatto sui follower
Nessuno oggi. Confermato sullo storico: senza l'anti-doppione S11 sarebbero state aperte 136 posizioni in più in 6 settimane.

## [0.6.1] - 2026-10-06
### Corretto (sicurezza della lettura)
- Il classificatore accettava letture errate: range abbreviato o con refuso (es. "4138.96 - 39.96"), SL/TP/entrata con una cifra persa o in più, cifre non ASCII, intestazione con due direzioni, prezzi a 3 decimali, zeri iniziali. Ora sono tutti AMBIGUOUS.
- Nuovi limiti di plausibilità: range ≤ 3,00; SL e TP entro 30,00 dall'entrata; livelli dalla parte giusta; ogni riga di livello letta per intero.
### Test
- 20 casi d'attacco, mutazioni mirate su ogni prezzo dei 12 messaggi reali, fuzzing con controllo di lettura letterale.
### Impatto sui follower
Nessuno oggi. Quando il bot sarà attivo: un segnale con un refuso nei prezzi non verrà mai eseguito; verrà segnalato all'admin come AMBIGUOUS.

## [0.6.0] - 2026-10-06
### Aggiunto
- `decision/engine.py`: motore decisionale puro (S1-S11 + filtri F), un test per ogni reason_code.
- `store.py`: registro SQLite (WAL, idempotente) e comando per ricostruire una decisione.
- `pipeline.py`: classifica → decide → registra.
- Dipendenza `tzdata==2026.5` (fusi orari su Windows).
### Impatto sui follower
Nessuno: nessun ordine viene inviato. Quando il bot sarà attivo, ogni segnale pubblicato due volte verrà aperto una sola volta (S11).

## [0.5.0] - 2026-10-06
### Aggiunto
- `config/config.yaml` (v0.1.0, commentato) e `config.py` (modello pydantic + `python -m momentum_master.config`).
- Blocchi: config non valido → il bot non parte; DEMO/LIVE solo con filtri confermati e dati FPG; chiavi sconosciute e orari senza virgolette rifiutati.
- Dipendenza `pyyaml==6.0.3`.
### Impatto sui follower
Nessuno: il bot resta in PAPER per costruzione finché Lorenzo non conferma i filtri.

## [0.4.0] - 2026-10-06
### Aggiunto
- Filtro sui mittenti autorizzati nel classificatore (D1: WDT è un gruppo).
- `decision/entry.py`: segnale a range scartato se il prezzo di esecuzione è fuori dal range (D2).
- `decision/targets.py`: scelta del TP configurabile (`tp_index`, default 1) e pareggio configurabile (`be_after_tp`, default spento) (D5).
### Impatto sui follower
Nessuno oggi: niente è collegato all'esecuzione. Quando lo sarà, i follower riceveranno solo segnali pubblicati da MOMENTUM, eseguiti solo se il prezzo è nel range, con TP1 e senza BE.

## [0.3.0] - 2026-10-06
### Aggiunto
- `docs/catalogo_formati.md` v0.1 (da 8 screenshot e da un video del canale).
- Classificatore v0.1: riconosce le aperture F-RANGE (mercato) e F-LIMIT (pendente) estraendo direzione, entrata, SL, TP e TP OPEN. Qualsiasi deviazione dal formato → AMBIGUOUS con il motivo.
- Exporter: campo `sender_id` (schema JSONL v2, compatibile con i file v1).
- Test golden su 12 aperture reali e 12 messaggi reali non di apertura.
### Impatto sui follower
Nessuno. Il classificatore non è collegato a nessuna esecuzione.

## [0.2.0] - 2026-10-06
### Aggiunto
- `scripts/windows/`: installazione, export di prova ed export completo con doppio clic.
- `analysis`: rapporto di esplorazione dello storico (forme ricorrenti, parole, emoji, numeri, risposte, modifiche, orari) come base del catalogo dei formati.
### Corretto
- Exporter: la cartella del file di sessione viene creata se manca (prima la prima esecuzione falliva).
### Impatto sui follower
Nessuno. Non esiste ancora codice di esecuzione.

## [0.1.0] - 2026-10-06
### Aggiunto
- Base del progetto (pyproject, ruff, pytest, requirements con versioni fissate, `.env.example`).
- `exporter`: esporta in sola lettura lo storico del canale in JSONL (id, data UTC, testo invariato, reply_to, citazione, data di modifica, tipo di media, inoltro, firma, messaggi di servizio), con ripresa e riepilogo statistico.
- `classifier.normalize`: NFKC, emoji trasformate in token descrittivi, spazi e righe uniformati.
- `classifier.numbers`: numeri con virgola o punto; i casi ambigui ("2,650") vengono segnalati, mai scelti.
- `docs/prompt-bot-momentum-fpg.md`: master prompt v1.

### Impatto sui follower
Nessuno. Non esiste ancora codice di esecuzione.
