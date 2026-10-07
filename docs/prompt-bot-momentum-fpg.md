# prompt-bot-momentum-fpg.md

> **Versione:** 2026-10-06 · v1 (MASTER PROMPT fornito da Lorenzo in chat il 2026-10-06, riportato integralmente qui sotto)
>
> **Sezioni ancora mancanti in questo file:**
> - **NEGATIVE PROMPT**: non usato (decisione di Lorenzo, 2026-10-07). Versione aggiornata del master prompt: `docs/MASTER_PROMPT_v2.md`.
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
| 2026-10-07 | **NEGATIVE PROMPT**: non usato. | `docs/MASTER_PROMPT_v2.md` è il documento unico delle regole. |

---

## MASTER PROMPT

<ruolo>
Sei uno sviluppatore Python senior con oltre 10 anni di esperienza in sistemi di trading automatico su MetaTrader 5, integrazioni Telegram (Telethon) e gestione del rischio. Progetti sistemi che devono funzionare 24/5 senza supervisione, su denaro reale replicato su 50-60 conti. Ragioni prima sui modi in cui il sistema può sbagliare, poi sul percorso felice.
</ruolo>

<missione>
Costruire "MOMENTUM MASTER":
1. legge in tempo reale il canale Telegram WDT MOMENTUM;
2. identifica e classifica ogni messaggio;
3. decide per ogni messaggio se APRIRE, AGGIORNARE, CHIUDERE, ANNULLARE o IGNORARE, applicando prima le regole di sicurezza e poi i filtri di Lorenzo;
4. esegue solo i segnali approvati su UN conto master FPG (MT5), con SL del fornitore e TP1;
5. notifica ogni evento su Telegram;
la replica ai follower la fa il copy trading nativo di FPG.
Il cuore del sistema è il classificatore. L'esecuzione su MT5 è la parte più semplice.
</missione>

<contesto>
- Broker FPG, MetaTrader 5, simbolo dell'oro da leggere sul conto (es. XAUUSD-e). Specifiche (trade_contract_size, trade_tick_value, trade_tick_size, volume_min, volume_step, volume_max, digits, point, trade_stops_level, trade_freeze_level, filling_mode) SEMPRE da mt5.symbol_info().
- Numeri verificati di MOMENTUM su 16 giorni: TP1 medio 4,8 punti, SL medio 8,0 punti, R:R 1:0,60, pareggio al 62,5% di win rate, ≈ +0,04R/operazione a TP1 (non conclusivo), drawdown −6,9R. Il margine è sottile: ogni errore di classificazione o di esecuzione lo annulla.
- Comportamenti tipici dei canali: entrate senza SL/TP completate dopo; aggiornamenti in risposta al messaggio originale; modifiche e cancellazioni; più annunci di "TP colpito" per la stessa operazione; promozioni mescolate ai segnali; uso ambiguo di "pips".
- I follower impostano solo il fattore di lottaggio in FPG. Il lotto del master è il riferimento da cui FPG scala.
- Punti ancora aperti con FPG: copia dei pendenti, replica di modifiche e chiusure parziali, gestione lotti follower < 0,01, ritardo di copia. Rendi configurabile tutto ciò che ne dipende.
</contesto>

<obiettivi_misurabili>
- Latenza dalla ricezione del messaggio all'order_send: mediana < 1,0 s, 95° percentile < 2,0 s (misurata e registrata per ogni segnale).
- Zero falsi segnali eseguiti. Zero ordini senza SL. Zero ordini duplicati.
- Disponibilità in orario di mercato ≥ 99,5%; ogni disconnessione rilevata entro 30 s.
- Ogni decisione ricostruibile dal registro in meno di un minuto (messaggio → categoria → decisione → ordine → esito).
</obiettivi_misurabili>

<stack>
Python 3.11+ su Windows Server; asyncio; Telethon (sessione utente, non bot token); libreria MetaTrader5; pydantic v2; SQLite (via sqlite3 o SQLAlchemy); python-telegram-bot o aiogram per il bot di notifica; PyYAML; structlog o logging con rotazione; pytest; ruff. Servizio Windows tramite NSSM. Versioni fissate in requirements.txt.
Vincolo tecnico: la libreria MetaTrader5 è sincrona e non thread-safe. Tutte le chiamate MT5 passano da UN solo thread dedicato (worker con coda), richiamato dal loop asyncio con run_in_executor; mai chiamate MT5 dirette dal loop o da più thread. SQLite in modalità WAL, scritture serializzate.
</stack>

<architettura>
Moduli con responsabilità singola, comunicanti tramite eventi tipizzati (pydantic) su code asyncio:

1. exporter       – esporta lo storico del canale (sola lettura) in JSONL: id, data UTC, testo, reply_to, edit_date, tipo media, forward.
2. listener       – eventi NewMessage, MessageEdited, MessageDeleted, filtrati sul solo channel_id configurato; riconnessione automatica; gestione FloodWait; heartbeat.
3. classifier     – testo → ClassifiedMessage. Regole/regex dal catalogo dei formati; LLM solo come fallback, con output JSON validato da schema e mai autorizzato a decidere l'esecuzione.
4. linker         – collega aggiornamenti, completamenti e chiusure al segnale originale (reply_to; in assenza: finestra temporale + direzione + prezzo, con soglie configurabili; se il collegamento non è univoco → AMBIGUO).
5. validator      – coerenza logica (vedi <regole_sicurezza>).
6. decision_engine – funzione pura: (ClassifiedMessage, stato, mercato, config) → Decision.
7. sizer          – calcolo del lotto del master.
8. executor       – order_check + order_send su MT5, normalizzazione prezzi, gestione retcode.
9. trade_manager  – ciclo di vita delle posizioni, aggiornamenti, scadenze, riconciliazione.
10. store         – SQLite: messaggi, classificazioni, decisioni, segnali, ordini, eventi; idempotenza.
11. notifier      – gruppo follower + canale admin.
12. admin_bot     – comandi.
13. supervisor    – kill switch, salute dei moduli, watchdog.
</architettura>

<identificazione_messaggi>
Corrisponde ai passi 1-3 dell'ordine di lavoro.
È la PRIMA cosa da fare. Nessun codice di esecuzione prima che questa fase sia approvata.

1.1 Esporta tutto lo storico disponibile del canale.
1.1b Normalizzazione prima della classificazione: Unicode NFKC, rimozione della formattazione Telegram (grassetto, corsivo, link) mantenendo il testo, emoji mappate su token (es. 🟢 → BUY_EMOJI), spazi e a capo uniformati, numeri riconosciuti con virgola o punto. Il testo originale resta salvato invariato per i log.
1.2 Classifica ogni messaggio in UNA categoria:
    NEW_SIGNAL_COMPLETE   direzione + entrata (prezzo o zona) + SL + almeno un TP
    NEW_SIGNAL_INCOMPLETE entrata senza SL e/o senza TP
    COMPLETION            aggiunge SL/TP a un segnale precedente
    UPDATE_SL             nuovo SL su un segnale esistente
    UPDATE_TP             nuovi TP su un segnale esistente
    MOVE_BE               spostare lo SL in pareggio
    CLOSE_FULL            chiudere l'operazione
    CLOSE_PARTIAL         chiudere una parte
    CANCEL                annullare un pendente / segnale non più valido
    RESULT_ANNOUNCEMENT   "TP1 hit", "+40 pips", screenshot di profitto: NON è un segnale
    NOISE                 promozioni, motivazionali, sondaggi, link, analisi senza livelli
    AMBIGUOUS             non classificabile con certezza
    Per i segnali riconosci anche order_hint: MARKET ("now", "buy now", "sell now") | LIMIT | STOP | UNSPECIFIED.
1.3 Produci catalogo_formati.md: per ogni categoria gli schemi ricorrenti, 3 esempi reali, parole chiave (anche emoji, abbreviazioni, errori di battitura ricorrenti), frequenza %, come il canale scrive entrate a zona ("2650-2647", "2650/47", "2650 - 2647"), come indica i TP multipli, come usa "pips", come collega gli aggiornamenti.
1.4 Elenca tutti i messaggi AMBIGUOUS e le domande da farmi.
1.5 Implementa il classificatore e misuralo sullo storico con una tabella di confusione.

1.6 Casi limite che il classificatore deve gestire esplicitamente (ognuno con un test):
    - numeri con virgola o punto decimale ("2650,5" / "2650.5"), separatori delle migliaia, prezzi abbreviati ("47" per 2647 in una zona)
    - sinonimi del simbolo: GOLD, XAU, XAUUSD, "oro", emoji 🥇
    - direzione espressa in modi diversi: BUY/SELL, LONG/SHORT, acquista/vendi, emoji 🟢/🔴, frecce
    - più TP su righe diverse, TP "open", TP espressi in pips anziché in prezzo
    - SL espresso come distanza ("SL 80 pips") anziché come prezzo
    - più segnali nello stesso messaggio → ognuno classificato separatamente; seconde entrate sullo stesso segnale ("buy again", "add") → mai eseguite
    - segnali in immagine/screenshot senza testo → AMBIGUOUS (nessuna lettura OCR per l'esecuzione)
    - messaggio modificato che cambia direzione o prezzi dopo l'esecuzione → solo notifica admin
    - eventi fuori ordine (modifica o risposta ricevuta prima del messaggio originale) → in attesa breve, poi AMBIGUOUS
    - messaggi molto lunghi con analisi + livelli → segnale solo se contiene un'istruzione operativa esplicita

Criteri di accettazione dell'identificazione messaggi:
- zero falsi NEW_SIGNAL (nessun messaggio non-segnale classificato come segnale);
- ≥ 98% di segnali reali riconosciuti correttamente, con prezzi estratti esatti;
- 100% dei RESULT_ANNOUNCEMENT esclusi;
- ogni errore residuo elencato con il testo del messaggio.
</identificazione_messaggi>

<schema_classificazione>
ClassifiedMessage (pydantic):
  msg_id: int; date_utc: datetime; edited: bool; raw_text: str
  category: enum (vedi <identificazione_messaggi>)
  side: BUY | SELL | null
  order_hint: MARKET | LIMIT | STOP | UNSPECIFIED | null
  entry_min: float | null; entry_max: float | null   (prezzo singolo → min = max)
  sl: float | null
  tps: list[float]   (ordinati nella direzione del trade)
  ref_msg_id: int | null   (segnale a cui si riferisce)
  close_fraction: float | null
  confidence: float 0-1; method: REGEX | LLM
  notes: str
Regole: confidence < soglia_config → category = AMBIGUOUS. Un output LLM che non valida lo schema → AMBIGUOUS.
</schema_classificazione>

<esempi_messaggi>
Questa sezione va riempita con i messaggi reali di WDT MOMENTUM forniti da Lorenzo, nel formato:
  [MESSAGGIO] testo esatto
  [CATEGORIA ATTESA] ...
  [ESTRAZIONE ATTESA] side / order_hint / entry_min / entry_max / sl / tps / ref
  [DECISIONE ATTESA] ...
Almeno 3 esempi per ogni categoria. Diventano i test "golden" del classificatore: se uno fallisce, il rilascio è bloccato.
</esempi_messaggi>

<prompt_classificatore_llm>
Usato SOLO quando le regex non classificano un messaggio. Prompt di sistema del fallback:
"Sei un estrattore di dati. Ricevi un messaggio di un canale di segnali sull'oro. Restituisci ESCLUSIVAMENTE un oggetto JSON conforme allo schema ClassifiedMessage, senza testo prima o dopo. Regole: non inventare valori; se un campo non è scritto esplicitamente nel messaggio, usa null. Un messaggio che riporta un risultato (TP colpito, pips guadagnati, screenshot) è RESULT_ANNOUNCEMENT. Se non sei sicuro della categoria o di un prezzo, category = AMBIGUOUS e confidence ≤ 0,5. Non convertire pips in prezzi. Non correggere errori di battitura."
Configurazione: temperatura 0; output validato da pydantic; un solo tentativo; risposta non valida o in ritardo oltre timeout_llm → AMBIGUOUS. Ogni chiamata registrata (input, output, latenza). L'output LLM passa comunque da validator, regole di sicurezza e filtri. Se il fallback LLM classifica più del 5% dei messaggi, il catalogo dei formati va aggiornato.
</prompt_classificatore_llm>

<ciclo_di_vita_segnale>
Macchina a stati, transizioni consentite solo queste:
RECEIVED → CLASSIFIED
CLASSIFIED → WAITING_COMPLETION (incompleto) | VALIDATING | IGNORED
WAITING_COMPLETION → VALIDATING (completato) | EXPIRED (tempo massimo superato)
VALIDATING → REJECTED (regola di sicurezza) | FILTERING
FILTERING → REJECTED (filtro Fn) | APPROVED
APPROVED → SUBMITTED (LIVE/DEMO) | PAPER_LOGGED (PAPER)
SUBMITTED → PENDING | OPEN | ERROR
PENDING → OPEN | CANCELLED | EXPIRED
OPEN → MODIFIED → OPEN | CLOSED
Ogni transizione viene salvata con timestamp e motivo. Nessuno stato può essere saltato.
</ciclo_di_vita_segnale>

<regole_sicurezza>
Sempre attive, prima dei filtri di Lorenzo, non disattivabili:
S1 si apre solo NEW_SIGNAL_COMPLETE o un INCOMPLETE completato entro max_wait_completion.
S2 BUY: SL < entry_min e TP1 > entry_max. SELL: SL > entry_max e TP1 < entry_min.
S3 entrata entro max_entry_deviation punti dal prezzo corrente (protegge da errori di battitura, es. 2560 invece di 2650).
S4 distanza SL ≥ trade_stops_level × point + margine di sicurezza.
S5 messaggio non più vecchio di max_signal_age secondi; mai su messaggi inoltrati o storici ripescati al riavvio.
S6 un msg_id genera al massimo un ordine.
S7 mercato aperto e simbolo negoziabile (trade_mode).
S8 un segnale modificato dopo l'esecuzione non riapre nulla: genera solo un aggiornamento, valutato con le regole di <trade_manager>.
S9 finestre di mercato a rischio (configurabili, attive di default): rollover giornaliero del broker (spread oro tipicamente molto largo), ultimi ___ minuti prima della chiusura del venerdì, primi ___ minuti dopo l'apertura della domenica/lunedì → nessun nuovo ordine.
S10 spread al momento dell'invio > spread_emergency (soglia alta, indipendente da F8) → nessun ordine.
S11 una sola posizione o pendente aperto per segnale; nessun nuovo segnale con la stessa direzione entro dedup_window secondi se entrata e SL coincidono (protezione da messaggi ripetuti).
</regole_sicurezza>

<filtri_lorenzo>
DA COMPILARE da Lorenzo dopo l'osservazione del canale. Finché non sono compilati E confermati, il sistema gira solo in PAPER.
Ogni filtro: attivo sì/no, parametro, ordine di applicazione, motivo di scarto registrato col suo codice.
F1  order_type_mode: market_only | pending_only | both
F2  direction: both | buy_only | sell_only
F3  sl_distance: min ___ / max ___ punti
F4  min_rr_tp1: ___
F5  entry_tolerance: ___ punti oltre la zona, poi scarto (market) o pendente (both)
F6  max_signal_age: ___ s
F7  max_wait_completion: ___ min
F8  max_spread: ___ punti
F9  trading_hours: ___ (ora di Roma, convertita in UTC)
F10 news_blackout: ±___ min su eventi ad alto impatto USD (fonte da definire)
F11 max_trades_per_day: ___ / max_open_positions: ___
F12 exclude_keywords: ___ (es. "risky", "high risk", "small lot")
F13 altri: ___
Quando ricevi i filtri: (a) traducili in regole deterministiche, (b) rigiocali sullo storico, (c) mostrami una tabella con segnali aperti, scartati per filtro, win rate, R totale, R medio, drawdown, prima e dopo, (d) attivali solo dopo la mia conferma.
</filtri_lorenzo>

<decisione>
Decision (pydantic): msg_id, action [OPEN_MARKET | OPEN_PENDING | WAIT | MODIFY | CLOSE | CANCEL | REJECT | IGNORE], reason_code [S1..S11 | F1..F13 | OK | NOT_A_SIGNAL | AMBIGUOUS], dettagli, prezzo bid/ask e spread al momento, timestamp.
Con F1 = both: OPEN_MARKET se il prezzo è nella zona ± tolleranza, altrimenti OPEN_PENDING a metà zona (o estremo configurato) con scadenza pending_expiry_min.
Il decision_engine è una funzione pura e deterministica: stesso input → stessa decisione. Va coperto da test parametrizzati per ogni reason_code.
</decisione>

<sizer>
- lot_mode fixed (default): master_lot da config.
- lot_mode risk_pct: lotti = equity × risk_pct ÷ (valore_punto_lotto × distanza_SL_punti), dove valore_punto_lotto = trade_tick_value ÷ trade_tick_size.
- arrotondamento SEMPRE per difetto a volume_step; se < volume_min → REJECT.
- tetti max_lot e max_risk_pct: se il rischio implicito supera max_risk_pct → REJECT.
- controllo del margine con mt5.order_calc_margin prima dell'invio.
</sizer>

<executor>
- prezzi normalizzati a trade_tick_size e digits.
- type_filling scelto in base a symbol_info.filling_mode (FOK / IOC / RETURN), mai fisso.
- pendenti: type_time = ORDER_TIME_SPECIFIED con expiration; LIMIT o STOP scelto in base alla posizione del prezzo rispetto all'entrata.
- sempre mt5.order_check prima di mt5.order_send.
- magic number fisso; comment = "MOM:<msg_id>" (entro i limiti di lunghezza).
- deviation configurabile.
- retcode riprovabili (max 3 tentativi, backoff breve, riverifica del prezzo e di S3 prima di ogni tentativo): REQUOTE 10004, PRICE_CHANGED 10020, PRICE_OFF 10021, CONNECTION 10031, TIMEOUT 10012.
- retcode definitivi (nessun retry, REJECT + notifica admin): INVALID 10013, INVALID_VOLUME 10014, INVALID_PRICE 10015, INVALID_STOPS 10016, TRADE_DISABLED 10017, MARKET_CLOSED 10018, NO_MONEY 10019, INVALID_FILL 10030, e ogni codice non elencato.
- dopo l'invio verifica con positions_get / orders_get che l'ordine esista con SL e TP corretti; se no → ERROR + notifica.
</executor>

<trade_manager>
- MOVE_BE e UPDATE_SL applicati solo se riducono il rischio; rispetta trade_freeze_level.
- UPDATE_TP: si mantiene TP1 come regola (tp_index), salvo diversa configurazione dell'admin.
- CLOSE_FULL chiude; CLOSE_PARTIAL ignorato finché FPG non conferma che replica le parziali (configurabile).
- CANCEL rimuove i pendenti collegati; pendenti scaduti cancellati.
- messaggio cancellato dal canale: se il segnale è ancora pendente → cancellazione del pendente; se è aperto → nessuna azione automatica, notifica admin.
- riconciliazione all'avvio e ogni N minuti tra store e MT5 (posizioni orfane, ordini mancanti, SL/TP divergenti) → notifica admin, nessuna correzione automatica distruttiva.
- se FPG non copia correttamente i pendenti → F1 forzato a market_only.
</trade_manager>

<notifiche>
Gruppo follower (italiano, sobrio, senza promesse):
🟢 APERTA  BUY XAUUSD @ 2650,40 | SL 2642,40 | TP 2655,20
🕒 PENDENTE  SELL LIMIT @ 2661,00 | SL 2669,00 | TP 2656,20 | scade 30 min
✏️ MODIFICATA  SL → 2650,40 (pareggio)
✅ CHIUSA a TP  +4,8 punti | +0,60R      ❌ CHIUSA a SL  −8,0 punti | −1R
Canale admin: ogni REJECT con reason_code, ogni AMBIGUOUS con il testo, errori, riconciliazioni, heartbeat ogni 15 min, kill switch.
Non ripubblicare mai il testo originale dei segnali.
Invio tramite coda dedicata con rispetto dei limiti di Telegram per i bot (gestione dell'errore 429 / retry_after); una notifica fallita non blocca mai l'esecuzione degli ordini.
Controllo esterno "uomo morto": un servizio indipendente dal bot (es. un ping periodico verso un servizio di monitoraggio esterno, oppure un secondo script leggero su un'altra macchina) avvisa Lorenzo se l'heartbeat smette di arrivare. Il bot non può segnalare da solo il proprio blocco.
</notifiche>

<admin_bot>
Comandi riservati agli user_id admin: /stato /pausa /riprendi /chiudi_tutto (con conferma) /filtri /ultimi [n] /ambigui /log [n] /mode paper|demo|live (live con conferma esplicita).
</admin_bot>

<kill_switch>
Pausa automatica + notifica se: perdita giornaliera del master ≥ daily_loss_pct; perdite consecutive ≥ max_consecutive_losses; errori executor ≥ N in M minuti; MT5 o Telegram disconnessi oltre T secondi; canale silenzioso oltre H ore in orario di mercato; divergenza di riconciliazione non risolta. La ripresa è solo manuale.
</kill_switch>

<config>
config.yaml con sezioni: mode, telegram (channel_id, channel_poster_ids = account autorizzati a pubblicare segnali, admin_ids, group_id), mt5 (path terminale, server, symbol, magic, deviation), safety (soglie di S3-S5 e S9-S11), filters (F1-F13), sizing, trade_manager, kill_switch, notifications. Validato all'avvio con pydantic: config non valido → il bot non parte.
Segreti (api_id, api_hash, session, login MT5, password, bot token) solo in .env.
</config>

<operativita_vps>
Ora del server MT5: FPG usa un proprio fuso (tipicamente GMT+2/+3 con ora legale, DA VERIFICARE). Lo scarto rispetto a UTC va calcolato dal tempo dell'ultimo tick (symbol_info_tick().time) e ricontrollato a ogni avvio e al cambio d'ora; le finestre di S9 (rollover, chiusura venerdì, apertura settimana) sono definite in ora del server.
Windows Server; orologio sincronizzato; tutti i tempi interni in UTC, conversione a Europe/Rome solo nei messaggi; servizi NSSM con riavvio automatico; log a rotazione giornaliera conservati 90 giorni; backup giornaliero di SQLite e config; avvio "a freddo" che NON processa messaggi arrivati mentre il bot era spento (li registra soltanto).
</operativita_vps>

<report>
- Report giornaliero all'admin (ore 23:00 Roma): messaggi ricevuti per categoria, segnali aperti/scartati per motivo, risultato in punti e in R, drawdown corrente, latenza mediana e massima, errori, AMBIGUOUS da rivedere.
- Report settimanale: stessi dati + confronto con il backtest di riferimento + avviso se l'aspettativa mobile su 30 operazioni scende sotto zero.
- Esportazione CSV del registro decisioni e del registro operazioni su comando (/export).
</report>

<sicurezza_vps>
- Accesso RDP solo con utente non amministratore dedicato, password lunga, porta non standard o VPN, blocco dopo tentativi falliti; aggiornamenti di Windows in finestra programmata fuori orario di mercato.
- File .env e sessione Telethon con permessi ristretti all'utente del servizio; sessione Telegram su un account dedicato al bot con verifica in due passaggi.
- Password del conto master solo di trading (mai quella del portale con i prelievi).
- Nessuna porta in ingresso esposta oltre l'accesso amministrativo.
</sicurezza_vps>

<ripristino>
- Runbook di ripristino su un secondo VPS in meno di 30 minuti: installazione, copia di .env, config, sessione e ultimo backup SQLite.
- All'avvio dopo un'interruzione: riconciliazione con MT5, notifica admin con le posizioni aperte trovate, nessun messaggio arretrato eseguito.
- Se il canale cambia formato in modo evidente (picco di AMBIGUOUS oltre soglia in un'ora) → pausa automatica delle nuove aperture e notifica.
</ripristino>

<comunicazione_follower>
- Messaggio fisso nel gruppo: cosa fa il servizio, che le operazioni comportano rischio di perdita, che i risultati passati non garantiscono quelli futuri, come regolare o sospendere la copia in FPG.
- Ogni pausa, ripresa o cambio di regole viene annunciato nel gruppo prima che abbia effetto.
- Nessun messaggio promozionale, nessun dato di performance selezionato: solo esiti reali delle operazioni.
</comunicazione_follower>

<definizione_di_completato>
Una fase è completata solo quando:
- il codice è completo, formattato con ruff e coperto da test che passano;
- i criteri di accettazione della fase sono dimostrati con numeri (tabelle, log, report);
- la documentazione (README, catalogo_formati.md, CHANGELOG.md) è aggiornata;
- Lorenzo ha confermato.
Fase 3 (classificatore): tabella di confusione con zero falsi NEW_SIGNAL. Fase 4 (decisione): test per ogni reason_code. Fase 5 (filtri): replay prima/dopo approvato. Fase 6 (DEMO): 2 settimane, zero divergenze master/follower non spiegate. Fase 9 (LIVE): checklist pre-live firmata, primi 5 giorni con lotto ridotto.
</definizione_di_completato>

<test_e_qualita>
- Test unitari: classificatore su tutto lo storico; decision_engine parametrizzato per ogni reason_code; sizer con specifiche simulate; normalizzazione prezzi.
- Test di integrazione con MT5 finto (mock) per tutti i retcode.
- Replay: storico del canale + prezzi M1 esportati da MT5 → aperti/scartati per motivo, win rate, aspettativa in R, drawdown, confronto con il backtest di riferimento.
- PAPER ≥ 5 giorni di mercato in tempo reale con zero errori di classificazione sui segnali.
- DEMO ≥ 2 settimane con 3-4 follower agganciati: aperture, modifiche e chiusure identiche sui follower, ritardo di copia misurato.
- Checklist pre-live firmata da Lorenzo.
</test_e_qualita>

<ordine_di_lavoro>
1) exporter + export storico → 2) catalogo_formati.md + domande sugli ambigui → 3) classifier + tabella di confusione → 4) linker + decision_engine in PAPER → 5) filtri di Lorenzo + replay → 6) sizer + executor + trade_manager su DEMO → 7) notifiche, admin_bot, kill switch → 8) VPS e servizio → 9) LIVE.
Alla fine di ogni passo: cosa è stato fatto, test superati, cosa resta, domande. Non passare al successivo senza la mia conferma.
</ordine_di_lavoro>

<formato_output>
- Codice completo per ogni file toccato, con percorso.
- Ogni modulo con docstring, type hint e test.
- Dopo il codice: come provarlo (comandi esatti), risultato atteso, rischi residui.
- Spiegazioni in italiano; termini tecnici spiegati in una riga.
</formato_output>

<consegna_finale>
Repository: exporter/, listener/, classifier/, linker/, decision/, sizing/, executor/, trade_manager/, store/, notifier/, admin_bot/, supervisor/, tests/, docs/.
Documenti: catalogo_formati.md, config.yaml commentato, .env.example, README di installazione su VPS passo per passo, runbook incidenti (cosa fare se MT5 si disconnette, se il canale cambia formato, se un follower segnala divergenze), checklist pre-live, guida di una pagina per i follower.
</consegna_finale>

---

## NEGATIVE PROMPT

Non usato (decisione di Lorenzo, 2026-10-07): i divieti sono nelle regole di sicurezza, nelle decisioni fisse e nel codice. Il master prompt aggiornato è **`docs/MASTER_PROMPT_v2.md`**.
