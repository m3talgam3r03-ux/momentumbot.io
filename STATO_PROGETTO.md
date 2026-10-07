# STATO_PROGETTO.md

## 2026-10-06 (fine giornata) — versione 0.11.0

**Fase corrente:** passi 1-4 completati lato codice (export, catalogo, classificatore, decisioni in PAPER). Passo 5 (filtri + replay) pronto: **aspetta i prezzi M1 da MT5**.
**Modalità del bot:** PAPER (bloccata dal config finché i filtri non sono confermati). Nessun codice di esecuzione su MT5: nessun ordine può partire.
**Test:** 1152 superati, ruff senza errori.

### Completato
| Area | Cosa c'è | Prova |
|---|---|---|
| Storico | Export Telethon + lettore dell'export HTML di Telegram Desktop | 1976 messaggi reali letti (26/08 → 06/10) |
| Catalogo | `docs/catalogo_formati.md` v0.3, `docs/analisi_storico_2026-10-06.md` | ogni tipo di messaggio, con frequenze ed esempi reali |
| Classificatore | Aperture F-RANGE / F-LIMIT, aggiornamenti (CANCEL, CLOSE, BE), risultati, rumore; istruzioni manuali → AMBIGUOUS | 399/399 aperture, 0 discordanze, 0 falsi segnali; 240.000 messaggi rovinati: 0 letture sbagliate |
| Decisioni | Regole S1-S11, filtri F, doppioni (S11), D2 fuori range, CANCEL/CLOSE sul segnale collegato, BE spento (D5), HEADS UP solo notifica (D4), messaggi cancellati | un test per ogni motivo di scarto; collegamento verificato su tutto lo storico |
| Registro | SQLite con versione dello schema, comando "spiega" | ogni decisione ricostruibile |
| PAPER dal vivo | Listener Telethon in sola lettura, arretrati registrati e mai eseguiti, latenza, heartbeat | test del nucleo; avvio reale da fare |
| Replay | Stessa pipeline su prezzi M1, esiti simulati in modo prudente, export prezzi da MT5 | test su barre sintetiche; replay reale da fare |
| Rapporto | Rapporto giornaliero dal registro (`python -m momentum_master.report`) | test |
| Config | `config/config.yaml` validato, PAPER forzata senza filtri confermati | test |

### Decisioni prese (registro completo in `docs/prompt-bot-momentum-fpg.md`)
- R:R non calcolato (F4 non usato); priorità al messaggio di apertura.
- D1 è un gruppo → solo mittenti autorizzati. D2 fuori range → scarto. D4 HEADS UP → solo notifica, cancellazione manuale. D5 TP1, niente BE (funzioni pronte e spente).

### Serve Lorenzo — per proseguire
**Bloccanti per la PAPER dal vivo**
1. `telegram.group_id` nel config: `scripts\windows\4_trova_id_gruppo.bat`.
2. `.env` con `TG_API_ID` / `TG_API_HASH` sul PC o VPS (my.telegram.org).
3. Confermare che "SALA 2 (V)" (nome nell'export) è il gruppo WDT MOMENTUM da leggere.

**Bloccanti per il replay (passo 5)**
4. MT5 di FPG (anche DEMO) su Windows → `6_esporta_prezzi_mt5.bat` → `7_replay.bat` → mandare `data\replay.md`.

**Decisioni**
5. F11: il fornitore arriva a 17 segnali/giorno; il limite provvisorio è 10 (44 segnali scartati in 6 settimane). Tenere, alzare, togliere?
6. D3: pendenti con scadenza di 90 minuti sul broker (proposta). OK?
7. Segnale 917 (range largo 6), formato manuale 1128, apertura in italiano 922: lasciarli in AMBIGUOUS (proposta)?
8. Confermare che `ENTRY RANGE` = apertura a mercato (lo storico non mostra casi contrari).

**Prima della DEMO**
9. Risposte di FPG (email pronta): hedging/netting, copia di pendenti/modifiche/cancellazioni, lotti < 0,01, ritardo, simbolo e fuso del server.
10. Approvare `docs/MASTER_PROMPT_v2.md` (scritto da Claude il 2026-10-07; nessun negative prompt per decisione di Lorenzo); file `analisi-canali-segnali-oro.md` e `manuale-operativo-rischio-xauusd.md`.
11. Capitale del conto master (per il lotto, oggi un segnaposto da 0,01).
12. Parere legale sul servizio di copia verso terzi.
13. PR su GitHub: modalità "Accept edits" + "procedi con B".

### Prossimi passi tecnici (Claude), dopo i punti sopra
- Notifiche Telegram (gruppo follower + canale admin) e comandi admin: servono il token del bot di notifica e gli id delle chat.
- Executor e trade_manager su MT5 (passo 6, DEMO): servono le risposte di FPG.
- Kill switch, servizio Windows (NSSM), runbook, checklist pre-live.
