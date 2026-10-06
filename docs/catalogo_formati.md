# catalogo_formati.md — WDT MOMENTUM

> **Versione 0.1 — 2026-10-06.** Fonte: 8 screenshot e una registrazione dello schermo di 52 s (5-6 ottobre 2026, circa una giornata di canale) fornite da Lorenzo.
> **Campione piccolo:** le frequenze sono indicative. Il catalogo va ricontrollato sull'export completo (`storico.jsonl`), che darà anche il testo esatto: emoji, apostrofi e trattini qui sono trascritti da immagini.

## Sintesi

| Formato | Categoria | Come si riconosce | Azione del bot |
|---|---|---|---|
| **F-RANGE** | NEW_SIGNAL_COMPLETE, **MERCATO** | Prima riga `BUY/SELL XAUUSD (GOLD)`, poi riga con `ENTRY RANGE:: a - b` | Apre a mercato (con le regole su prezzo e range ancora da decidere, vedi D2) |
| **F-LIMIT** | NEW_SIGNAL_COMPLETE, **PENDENTE LIMIT** | Prima riga `LIMIT ORDER — BUY/SELL XAUUSD (GOLD)`, poi `ENTRY: x` | Piazza un ordine pendente |
| Pre-annuncio | NOISE | `PREPARA IL TUO MT5 … SELL XAUUSD … Sto guardando questa zona` | **Mai** aprire |
| TPn HIT | RESULT_ANNOUNCEMENT | Risposta che inizia con `TPn … ✅ HIT`, `Price:`, `(+xx pips)` | Nessuna (noi chiudiamo a TP1 sul broker) |
| TP2 HIT + BE | MOVE_BE | Come sopra + `Porta lo STOP LOSS al Prezzo d'entrata … (Break Even)` | Per noi irrilevante: a TP2 la posizione è già chiusa a TP1 |
| TRADE COMPLETE | CLOSE_FULL | `TRADE COMPLETE ✅ Price: … Closed at Break Even — TPs banked` | Chiudere eventuali residui (con TP1 normalmente è già chiusa) |
| SL HIT | RESULT_ANNOUNCEMENT | `SL ❌ HIT - Non rientrare aspetta il prossimo.` | Nessuna (SL già sul broker) |
| **LIMIT ORDER CANCELLED** | **CANCEL** | Risposta a un F-LIMIT: `❌ LIMIT ORDER CANCELLED` | **Cancellare il pendente**: è critico per i follower |
| LIMIT ORDER FILLED | RESULT_ANNOUNCEMENT | `🎯 LIMIT ORDER FILLED Price: …` | Solo verifica: il nostro pendente dovrebbe essere già eseguito |
| HEADS UP | AMBIGUOUS | `⚠️ HEADS UP — price is approaching this BUY limit level while the SELL … still running` | Solo notifica all'admin; il pendente resta; cancellazione manuale (D4) |
| Risultati giornalieri | NOISE | `RISULTATI GIORNALIERI DI MEMENTUM` | Nessuna |
| Grafico/GIF in risposta, motivazionali, info lotti/account | NOISE | Immagine con didascalia o testo in prosa | Nessuna |

## F-RANGE (apertura a mercato su zona)

```
❇️ SELL XAUUSD (GOLD) ❇️

PREZZO D'ENTRATA (ricordo che tra questi 2 prezzi puoi fare 2 o 3 slot d'entrate) :   %0A ➡️ ENTRY RANGE:: 4138.96 - 4139.96

SL ❌: 4147.96

TP1 (valuta il BE)✅: 4134.36
TP2 (metti a BE)✅: 4130.96
TP3✅: 4126.71
TP4✅: 4122.46
TP5✅: OPEN

❇️ INPULSE XAU | L'impulso per i profitti è appena iniziato, … Trade Ideas
⚠️ Questo è solo a scopo educativo. …
```
Esempi reali: `range_sell_1..5`, `range_buy_1..2` in `tests/golden_messages.py`.

Osservazioni:
- Il range è sempre largo **1,00** (7/7).
- `%0A` compare **letteralmente**: probabilmente uno strumento di pubblicazione che codifica l'a capo come in un URL. Il parser lo ignora.
- `ENTRY RANGE::` ha i **due punti doppi**.
- "puoi fare 2 o 3 slot d'entrate": il bot ne fa **una sola** (regola: niente seconde entrate).
- **Pubblicato due volte**, identico, nello stesso minuto (osservato su più segnali). Il dedup (S11) è obbligatorio.
- Dopo l'apertura arriva spesso una **risposta con grafico** e una didascalia in prosa ("Patience rewarded — XAUUSD finally came to our level").

## F-LIMIT (ordine pendente)

```
⏳ LIMIT ORDER — SELL XAUUSD (GOLD) ⏳

the market flew through this level like it wasnt even there — …

ENTRY: 4151.02

SL ❌: 4156.02

TP1 (valuta il BE)✅: 4148.52
TP2 (metti a BE)✅: 4146.02
TP3✅: 4141.02
TP4✅: 4136.02

⏳ This is a SELL LIMIT ORDER — it only fills if price pulls back to the entry. Place it as a pending order on your broker, or approve it on the ATE within 10 minutes.
```
Esempi reali: `limit_buy_1..2`, `limit_sell_1..3`.

Osservazioni:
- Il canale stesso dice "Place it as a **pending order**": conferma che F-LIMIT è un **pendente**.
- 4 TP, nessun TP OPEN.
- Il ciclo di vita del pendente è comunicato in risposta: `LIMIT ORDER FILLED` (eseguito) oppure `LIMIT ORDER CANCELLED` (annullato, "this one timed out"). **La scadenza del pendente non è scritta nel segnale** (D3).
- "approve it on the ATE within 10 minutes": ATE sembra uno strumento di copia del fornitore. Il significato dei "10 minuti" va chiarito (D3).

## Controlli di plausibilità della lettura (2026-10-06)
Un messaggio di apertura viene accettato solo se:
- ogni prezzo è un numero ASCII positivo, senza zero iniziale e con al massimo 2 decimali;
- il range (F-RANGE) è largo più di 0 e al massimo **3,00** (osservato: sempre 1,00);
- SL e tutti i TP sono entro **30,00** dal centro dell'entrata (osservato: SL ≤ 8,50, TP4 ≤ 16,50);
- SL e TP sono dalla parte giusta per la direzione;
- l'intestazione contiene una sola direzione e un solo simbolo;
- ogni riga che inizia con ENTRY/SL/TP e contiene ":" è letta per intero.
Altrimenti → AMBIGUOUS con il motivo. Se il canale cambia le sue distanze abituali, i limiti vanno rivisti qui e in `classifier/opening.py`.

## Unità: pips e prezzo di riferimento

| Verifica | Calcolo | Esito |
|---|---|---|
| TP1 HIT 4163.66 "(+30.0 pips)", range 4160.16-4161.16 | 4163.66 − 4160.66 = 3,00 | **1 pip = 0,10** |
| TP2 HIT 4165.66 "(+50.0 pips)" | 4165.66 − 4160.66 = 5,00 | conferma |
| TRADE COMPLETE "Closed at Break Even" Price 4160.66 | = centro del range | il pareggio è il **centro** del range |
| SL HIT 4156.99 "(-50.0 pips)", range 4151.49-4152.49 | 4156.99 − 4151.99 = 5,00 | conferma |
| TP1 HIT 4141.61 "(+44.8 pips)", range 4145.59-4146.59 | 4146.09 − 4141.61 = 4,48 | conferma |

Conclusione, verificata su 5 casi: per WDT MOMENTUM **1 pip = 0,10 di prezzo** e i pips si contano dal **centro del range**. Il bot comunque non converte mai i pips: usa i prezzi scritti.

## Distanze SL/TP (solo osservazione, nessuna regola)
Le distanze **non sono fisse** tra un segnale e l'altro. Distanza dello SL dall'entrata (F-LIMIT) o dal centro del range (F-RANGE), in punti di prezzo:
- F-LIMIT: 5,00 su 5 segnali su 5;
- F-RANGE: tra 5,00 e 8,50 (5,00 · 5,00 · 5,00 · 7,46 · 8,50).

Non vengono usate come controllo automatico. Lo SL resta esattamente quello del fornitore.

## Risposte di Lorenzo (2026-10-06)
- **D1** È un **gruppo**: solo i mittenti autorizzati.
- **D2** Prezzo fuori dal range → **scarto**.
- **D3** Consiglio richiesto: proposta in STATO_PROGETTO.md (scadenza lato broker di 90 min, IPOTESI da 2 casi del video).
- **D4** Il pendente resta aperto: solo notifica all'admin; l'eventuale cancellazione è manuale.
- **D5** Niente BE per ora; TP configurabile già nel codice.

## Domande originali (D1-D5)
- **D1** Il canale è un **gruppo** o un **canale**? Il nome "MOMENTUM" colorato sopra ogni messaggio fa pensare a un gruppo. Se è un gruppo: pubblica solo MOMENTUM, o anche altri utenti?
- **D2** F-RANGE: quando arriva il segnale, se il prezzo è **fuori dal range**, cosa si fa? (a) si apre comunque a mercato; (b) si scarta; (c) si mette un pendente al bordo o al centro del range.
- **D3** F-LIMIT: quanto deve durare il pendente sul master, se non arriva "LIMIT ORDER CANCELLED"? I "10 minuti" dell'ATE c'entrano?
- **D4** HEADS UP (pendente BUY mentre è aperto un SELL): il bot cancella il pendente da solo o avvisa soltanto te?
- **D5** TRADE COMPLETE "Closed at Break Even": il fornitore chiude a pareggio dopo TP2. Noi siamo già fuori a TP1. Confermi che **non** applichiamo il BE (che con TP1 per tutti non serve)?
