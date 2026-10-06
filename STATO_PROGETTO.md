# STATO_PROGETTO.md

## 2026-10-06

**Fase corrente:** passo 1 completato lato codice (export reale da eseguire). Passi 2 e 3 **avviati in anticipo** sui messaggi di apertura, grazie a 8 screenshot e a un video del canale forniti da Lorenzo.
**Modalità del bot:** nessuna. Non esiste ancora né classificatore né esecuzione: niente PAPER, DEMO o LIVE.

### Completato
- Base del progetto: pyproject (ruff, pytest), requirements con versioni fissate, `.env.example`, `.gitignore` (segreti, sessioni e dati esclusi).
- `docs/prompt-bot-momentum-fpg.md`: master prompt salvato integralmente (v1, 2026-10-06).
- `exporter`: esportazione in sola lettura dello storico in JSONL, con ripresa, scrittura sicura (`.part`) e riepilogo statistico.
- `classifier.normalize` e `classifier.numbers` (punto 1.1b): normalizzazione del testo e lettura dei numeri con segnalazione dei casi ambigui.
- Script Windows con doppio clic (`scripts/windows/`) per installazione ed export.
- `analysis`: rapporto di esplorazione dello storico, pronto per il passo 2.
- `docs/catalogo_formati.md` v0.1: formati F-RANGE (mercato) e F-LIMIT (pendente), più 10 tipi di messaggi non di apertura. Verificato che 1 pip = 0,10, contato dal centro del range.
- Classificatore v0.1 (`classifier/classify.py`, `opening.py`, `models.py`): riconosce solo F-RANGE e F-LIMIT; tutto il resto finisce in AMBIGUOUS.
- Test golden: 12 aperture reali riconosciute con prezzi esatti; 12 messaggi reali non di apertura, nessuno classificato come segnale.
- L'exporter registra anche `sender_id`, necessario se WDT è un gruppo.
- `config/config.yaml` v0.1.0 + `config.py`: config validato. Il bot non parte con un config errato; DEMO e LIVE sono bloccati senza filtri confermati e dati FPG; chiavi sconosciute rifiutate; orari senza virgolette rifiutati (YAML li leggerebbe come numeri).
- Email a FPG preparata (8 domande): in attesa dell'invio da parte di Lorenzo.
- 154 test superati; ruff senza errori.
- Verificato: l'integrazione Telegram di Composio è un bot (Bot API) e non può leggere lo storico di WDT. L'export si fa solo con la sessione utente (Telethon).

### Decisioni prese
- 2026-10-06: R:R non calcolato, F4 non usato. Priorità del classificatore: messaggio di apertura (direzione, entrata, SL, TP1, mercato o pendente). Registrate in `docs/prompt-bot-momentum-fpg.md`.

### In corso
- Export reale del canale WDT MOMENTUM: lo esegue Lorenzo (servono le credenziali Telegram, che non devono passare in chat).

### Bloccanti
0. **Branch `main` + PR**: Lorenzo ha scelto l'opzione B (riscrittura pulita). Per eseguirla deve passare la sessione in modalità "Accept edits" e approvare il comando quando gli viene richiesto.
1. **Storico esportato** (`data/storico.jsonl` + `.summary.json`): senza lo storico non si possono fare il catalogo dei formati (passo 2) né il classificatore (passo 3).
2. **NEGATIVE PROMPT**: manca in `docs/prompt-bot-momentum-fpg.md`.
3. File di riferimento mancanti: `analisi-canali-segnali-oro.md` e `manuale-operativo-rischio-xauusd.md`. Non bloccano i passi 2-3, bloccano il 5 e il 6.

### Decisioni del 2026-10-06 (D1-D5)
- D1 gruppo → filtro sui mittenti (`classify(..., authorized_sender_ids)`), fatto.
- D2 fuori range → scarto (`decision/entry.py`), fatto.
- D4 HEADS UP → il pendente resta aperto, solo notifica all'admin, cancellazione manuale (da implementare con admin_bot e trade_manager).
- D5 TP1 e niente BE; funzioni `tp_index` e `be_after_tp` pronte e disattivate (`decision/targets.py`), fatto.

### Da confermare
- **D3, proposta:** durata del pendente F-LIMIT **90 minuti**, impostata come scadenza **sul broker** (ORDER_TIME_SPECIFIED), così scade anche se il bot si blocca. Inoltre: cancellazione immediata a `LIMIT ORDER CANCELLED`, nessun pendente oltre il rollover giornaliero né nel fine settimana. IPOTESI: nel video due pendenti sono stati annullati dal fornitore dopo circa 90 minuti (16:15 → 17:45; ~17:47 → 19:20). Da verificare sull'export.
- **Conto master hedging o netting?** Bloccante prima della DEMO: con D4 il pendente opposto resta aperto e, su un conto netting, se viene eseguito chiude o riduce la posizione aperta.
- Conferma che `ENTRY RANGE` = apertura a mercato.

### Rischi emersi dal video
- Le aperture F-RANGE vengono pubblicate **due volte**: il dedup S11 è obbligatorio, non un'opzione.
- `LIMIT ORDER CANCELLED` va implementato (CANCEL) prima di qualsiasi DEMO con pendenti.

### Punti aperti (non bloccanti adesso)
- FPG: copia dei pendenti, replica di modifiche e chiusure parziali, lotti follower < 0,01, ritardo di copia.
- Filtri F1-F13: da compilare dopo l'osservazione del canale.
- S9: minuti di blackout del venerdì e dell'apertura settimanale.
- IPOTESI da verificare: il fuso del server FPG (GMT+2/+3).

### Prossimo passo
Lorenzo esegue `scripts\windows\1_installa.bat`, poi `2_esporta_prova.bat` e `3_esporta_tutto.bat`, e manda `storico.jsonl`, `storico.summary.json` ed `esplorazione.md`.
Poi: passo 2, cioè `catalogo_formati.md` e l'elenco delle domande sui messaggi ambigui.
