# prompt-bot-momentum-fpg.md

> **Versione:** 2026-10-06 · v1 (MASTER PROMPT fornito da Lorenzo in chat il 2026-10-06, riportato integralmente qui sotto)
>
> **Sezioni ancora mancanti in questo file:**
> - **NEGATIVE PROMPT**: ora in `docs/NEGATIVE_PROMPT.md` (2026-10-07, da approvare).
> - **Filtri di Lorenzo (F1–F13)**: da compilare. Senza filtri confermati il bot resta in PAPER.
> - **S9**: minuti prima della chiusura del venerdì e dopo l'apertura settimanale da definire.
> - **Punti aperti con FPG**: copia dei pendenti, replica di modifiche e chiusure parziali, lotti follower < 0,01, ritardo di copia.

## Decisioni di Lorenzo (registro)

| Data | Decisione | Effetto |
|---|---|---|
| 2026-10-06 | Il R:R **non** va calcolato dal bot. | F4 (`min_rr_tp1`) non è usato. Le regole di sicurezza restano invariate: S2 controlla solo che SL e TP stiano dalla parte giusta dell'entrata, non calcola il R:R. |
| 2026-10-06 | Priorità del classificatore: capire il **messaggio di apertura**, cioè direzione, entrata, **SL**, **TP1** e se l'ordine è **a mercato o pendente**. | Il catalogo dei formati parte da questi campi. Lo SL resta obbligatorio: senza SL il segnale non si apre (decisione fissa: SL del fornitore). |
| 2026-10-06 | **D1** WDT MOMENTUM è un **gruppo**. | Si considerano solo i messaggi degli account autorizzati (`telegram.channel_poster_ids`); gli altri sono NOISE. Gli id si ricavano dall'export. |
| 2026-10-06 | **D2** F-RANGE con prezzo fuori dal range → **scarto**. | BUY confrontato con l'ask, SELL con il bid; bordi inclusi; tolleranza 0 (configurabile, solo dopo replay). |
| 2026-10-06 | **D5** TP1 per tutti, **niente BE** per ora. | Funzioni già pronte e disattivate: `tp_index` (1-5) e `be_after_tp` (None). Si attivano solo con una nuova versione del config. |
| 2026-10-06 | **D3** Durata del pendente F-LIMIT: Lorenzo chiede un consiglio. | Proposta in attesa di conferma: vedi STATO_PROGETTO.md. |
| 2026-10-06 | **D4** HEADS UP (pendente opposto a una posizione aperta): il pendente **resta aperto**; Lorenzo decide se cancellarlo **a mano**. | Nessuna azione automatica: notifica all'admin con il testo del messaggio, il pendente e la posizione aperta. Servirà un comando admin per cancellare il pendente; la riconciliazione deve riconoscere una cancellazione manuale come voluta e non come errore. |
