# STATO_PROGETTO.md

## 2026-10-06

**Fase corrente:** passo 1 dell'ordine di lavoro (exporter + export dello storico). Codice pronto; **export reale da eseguire**.
**Modalità del bot:** nessuna. Non esiste ancora né classificatore né esecuzione: niente PAPER, DEMO o LIVE.

### Completato
- Base del progetto: pyproject (ruff, pytest), requirements con versioni fissate, `.env.example`, `.gitignore` (segreti, sessioni e dati esclusi).
- `docs/prompt-bot-momentum-fpg.md`: master prompt salvato integralmente (v1, 2026-10-06).
- `exporter`: esportazione in sola lettura dello storico in JSONL, con ripresa, scrittura sicura (`.part`) e riepilogo statistico.
- `classifier.normalize` e `classifier.numbers` (punto 1.1b): normalizzazione del testo e lettura dei numeri con segnalazione dei casi ambigui.
- Script Windows con doppio clic (`scripts/windows/`) per installazione ed export.
- `analysis`: rapporto di esplorazione dello storico, pronto per il passo 2.
- 56 test superati; ruff senza errori.
- Verificato: l'integrazione Telegram di Composio è un bot (Bot API) e non può leggere lo storico di WDT. L'export si fa solo con la sessione utente (Telethon).

### In corso
- Export reale del canale WDT MOMENTUM: lo esegue Lorenzo (servono le credenziali Telegram, che non devono passare in chat).

### Bloccanti
0. **Branch `main` + PR**: il repository ha un solo branch, quindi non c'è una base per la PR. Crearla richiede di riscrivere la storia del branch, operazione bloccata dai permessi della sessione: serve il via libera di Lorenzo (vedi chat).
1. **Storico esportato** (`data/storico.jsonl` + `.summary.json`): senza lo storico non si possono fare il catalogo dei formati (passo 2) né il classificatore (passo 3).
2. **NEGATIVE PROMPT**: manca in `docs/prompt-bot-momentum-fpg.md`.
3. File di riferimento mancanti: `analisi-canali-segnali-oro.md` e `manuale-operativo-rischio-xauusd.md`. Non bloccano i passi 2-3, bloccano il 5 e il 6.

### Punti aperti (non bloccanti adesso)
- FPG: copia dei pendenti, replica di modifiche e chiusure parziali, lotti follower < 0,01, ritardo di copia.
- Filtri F1-F13: da compilare dopo l'osservazione del canale.
- S9: minuti di blackout del venerdì e dell'apertura settimanale.
- IPOTESI da verificare: il fuso del server FPG (GMT+2/+3).

### Prossimo passo
Lorenzo esegue `scripts\windows\1_installa.bat`, poi `2_esporta_prova.bat` e `3_esporta_tutto.bat`, e manda `storico.jsonl`, `storico.summary.json` ed `esplorazione.md`.
Poi: passo 2, cioè `catalogo_formati.md` e l'elenco delle domande sui messaggi ambigui.
