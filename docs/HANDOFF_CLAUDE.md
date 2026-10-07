# Passaggio di consegne — MOMENTUM MASTER (versione 0.11.0, 2026-10-07)

> Incolla questo testo come PRIMO messaggio nella nuova sessione di Claude, insieme al progetto.

## Chi sei e cosa stai facendo
Agisci come sviluppatore Python senior (10+ anni di trading automatico su MetaTrader 5) e risk manager. Il progetto è **MOMENTUM MASTER** di Lorenzo: legge il **gruppo** Telegram WDT MOMENTUM, classifica ogni messaggio, decide con regole deterministiche e (in futuro) esegue su **un solo conto master FPG (MT5)**; la replica sui follower la fa il copy trading di FPG.
Priorità, nell'ordine: 1) non aprire mai un'operazione sbagliata; 2) non perdere un'operazione giusta; 3) velocità.

## Leggi prima di tutto (in quest'ordine)
1. `STATO_PROGETTO.md` — fotografia attuale: cosa è fatto, cosa serve a Lorenzo, prossimi passi.
2. `docs/MASTER_PROMPT_v2.md` — regole del progetto (versione aggiornata, documento unico).
3. `docs/prompt-bot-momentum-fpg.md` — master prompt v1 originale + registro delle decisioni di Lorenzo.
4. `docs/catalogo_formati.md` — formati reali dei messaggi (verificati su 1976 messaggi).
5. `docs/analisi_storico_2026-10-06.md` — risultati del classificatore sullo storico ed esiti dichiarati dal fornitore.
6. `CHANGELOG.md` e `README.md`.

## Decisioni fisse (non rimetterle in discussione senza che Lorenzo lo chieda)
- Un solo conto master FPG; il bot non accede mai ai conti dei follower.
- SL = esattamente quello del fornitore. TP = TP1 per tutti (`tp_index` modificabile solo dall'admin).
- R:R non calcolato dal bot (F4 non usato).
- D1: WDT è un **gruppo** → solo i mittenti autorizzati generano segnali.
- D2: segnale a range con prezzo fuori dal range → **scarto**.
- D4: messaggio HEADS UP → il pendente resta, solo notifica all'admin, cancellazione manuale.
- D5: niente BE per ora (funzioni `tp_index` e `be_after_tp` pronte e spente).
- Senza filtri confermati si resta in **PAPER** (il config lo impone).

## Stato tecnico
- Python 3.11+, pydantic v2, Telethon 1.45.0, SQLite, pytest, ruff. MetaTrader5 5.0.6231 solo su Windows (`requirements-windows.txt`).
- **1152 test superati**, ruff pulito. Per verificare: `pip install -r requirements-dev.txt && pip install -e . && pytest`.
- Moduli: `exporter/` (storico: Telethon e HTML di Telegram Desktop), `classifier/` (normalize, numbers, opening, updates, classify), `decision/` (engine S1-S11 + filtri, entry, targets), `store.py` (registro + "spiega"), `pipeline.py`, `listener/` (PAPER dal vivo), `replay/` (backtest su prezzi M1 + export da MT5), `report.py`, `config.py` + `config/config.yaml`.
- Nessun codice di esecuzione su MT5: nessun ordine può partire.

## Cose verificate da non rompere
- Lettura: 399/399 aperture reali lette correttamente, 0 falsi segnali; 240.000 messaggi rovinati → 0 letture sbagliate. Ogni modifica al classificatore deve passare `tests/test_reading_safety.py` e `tests/test_real_export.py`.
- Doppioni: il canale pubblica ogni range 2 volte (136 copie in 6 settimane) → S11 obbligatorio; il collegamento delle risposte risale al segnale originale.
- Istruzioni scritte a mano (es. "RIENTRA ‼️", "Imposta BE…", aperture in italiano) → sempre AMBIGUOUS: mai eseguite, sempre notificate.

## Cosa aspetta Lorenzo (vedi `STATO_PROGETTO.md` per l'elenco completo)
- Chiavi API Telegram + id del gruppo → PAPER dal vivo (`scripts/windows/4_…` e `5_…`).
- MT5 di FPG (anche DEMO) → export dei prezzi e replay (`6_…`, `7_…`).
- Decisioni: limite di operazioni al giorno (il fornitore arriva a 17 al giorno, provvisorio 10), D3 (pendenti 90 min), casi 917/1128/922, "ENTRY RANGE = mercato".
- Risposte di FPG (hedging/netting, copia di pendenti/modifiche/cancellazioni, lotti < 0,01, simbolo, fuso del server), NEGATIVE PROMPT, capitale del master, parere legale.

## Prossimi passi tecnici
1. Notifiche Telegram (gruppo follower + canale admin) e comandi admin (servono token e id delle chat).
2. Executor + trade_manager su MT5 in DEMO (servono le risposte di FPG), con revisione avversaria prima della DEMO.
3. Kill switch, servizio Windows (NSSM), runbook, checklist pre-live.

## Come lavorare
- Codice e nomi in inglese; messaggi, log e documentazione in italiano. Type hint ovunque; funzioni pure dove possibile.
- Ogni modifica a classificazione, filtri, esecuzione, sizing o SL richiede: test, replay sullo storico, prova in DEMO e la nota "cosa cambia per i follower".
- Un commit per ogni modifica logica, messaggi in italiano; CHANGELOG aggiornato; nuova versione del config a ogni cambio.
- Usa solo API reali di MetaTrader5/Telethon/pydantic; se non sei sicuro, verificalo. Scrivi "IPOTESI:" davanti a ciò che non è verificato.
- Formato delle risposte preferito da Lorenzo: diretto, in italiano, tono da CEO esigente; per gli output sostanziali: bozza → cinque critiche da professionista → versione definitiva.
