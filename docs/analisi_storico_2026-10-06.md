# Analisi dello storico WDT MOMENTUM — export del 2026-10-06

**Fonte:** export HTML di Telegram Desktop fornito da Lorenzo (`messages.html` + `messages2.html`), letto con `exporter/desktop_html.py`.
**Periodo:** 26/08/2026 → 06/10/2026 (circa 6 settimane). **Messaggi:** 1976, tutti pubblicati da "🌪️MOMENTUM 🌪️".
I dati grezzi restano fuori dal repository (`data/`); qui ci sono solo i risultati.

> ⚠️ Gli esiti dei segnali qui sotto sono quelli **dichiarati dal fornitore** nelle sue risposte (TP1 HIT, SL HIT…), **non** verificati sui prezzi del broker. Non è un consiglio di investimento né una stima di profitto.

## 1. Classificatore su tutto lo storico

| Risultato | Numero |
|---|---|
| Aperture riconosciute (NEW_SIGNAL_COMPLETE) | **399** (F-RANGE 302, F-LIMIT 97) |
| Verifica indipendente delle 399 (direzione, entrata, SL, TP1, tipo di ordine) | **0 discordanze** |
| Aperture vere NON riconosciute | **2** (vedi sotto) |
| Falsi segnali (non aperture classificate come aperture) | **0** |

Le 2 aperture non riconosciute, entrambe in AMBIGUOUS (quindi notifica, nessun ordine):
- **msg 917** (15/09): `ENTRY RANGE: 4274-4280`, prezzi senza decimali, range largo **6,00**, oltre il limite di sicurezza di 3,00. Unico caso in 6 settimane.
- **msg 1128** (20/09, 23:31 UTC): formato manuale mai visto (`BUY XAU / PE 4375 / SL 4370 / Tp1 4378,5`).

**Varianti di formato** trovate e già lette correttamente:
- `ENTRY RANGE: a - b` su una riga sua, senza "PREZZO D'ENTRATA" (182 messaggi, il formato delle prime settimane);
- `… :   %0A ➡️ ENTRY RANGE:: a - b` (74);
- `… :    \n➡️ ENTRY RANGE:: a - b` con "\n" **scritto letteralmente** (46);
- `ENTRY: x` per i LIMIT (97).

Tutti i prezzi hanno 2 decimali (399 su 399).

## 2. Doppioni

**263 segnali distinti** su 399 aperture: **130 pubblicati due volte, 3 tre volte**. Senza la regola S11 (anti-doppione), in 6 settimane il bot avrebbe aperto **136 posizioni in più**.

## 3. Messaggi che non sono aperture

| Tipo | Numero | Note per il bot |
|---|---|---|
| TP HIT | 514 | Risultato. Noi chiudiamo a TP1 sul broker |
| TP HIT + "Porta lo STOP LOSS al prezzo d'entrata" | 68 | BE: spento per decisione D5 |
| Foto/GIF con didascalia (grafici, meme) | 345 | Rumore |
| Pre-annunci ("PREPARA IL TUO MT5", "PREPARATI STA PER ARRIVARE…", "PREP \|") | 150 | **Mai** aprire |
| SL HIT | 103 | Risultato |
| TRADE COMPLETE | 92 | Chiusura (per noi già chiusa a TP1) |
| LIMIT ORDER FILLED | 61 | Verifica del pendente |
| **OUT OF TRADE** ("TP1 secured — exiting now") | 50 | Chiusura del fornitore, **sempre** in risposta al segnale; nei 4 casi esaminati dopo TP1 |
| Riepiloghi giornalieri e settimanali | 29+ | Rumore |
| **LIMIT ORDER CANCELLED** | 21 | **Cancellare il pendente** (19 su 21 in risposta) |
| HEADS UP | 18 | D4: solo notifica |
| Saluti, motivazionali, regole di trading | ~100 | Rumore |

## 4. Esiti dichiarati dal fornitore (281 segnali raggruppati)

| Esito | Segnali |
|---|---|
| TP1 prima dello SL | 161 |
| SL prima di TP1 | 74 |
| Pendente annullato | 19 |
| **Nessun esito pubblicato** | **23** |
| Uscita del fornitore prima di TP1/SL | 4 |

Sui 235 segnali con esito TP1/SL, prezzo di riferimento = centro dell'entrata:

| Misura | Valore |
|---|---|
| TP1 colpito per primo | **68,5%** |
| TP1 medio / SL medio | 4,17 / 7,17 punti |
| Win rate di pareggio con questo rapporto | 63,6% |
| Aspettativa a TP1 | **+0,077 R per operazione** (+18,2 R in totale) |
| Drawdown massimo | −6,2 R |
| Settimane | 6 positive su 7 (W40: −0,1 R) |

Confronto con `analisi-canali-segnali-oro.md` (16 giorni): TP1 4,8 / SL 8,0, pareggio 62,5%, ≈ +0,04 R, drawdown −6,9 R. Questi numeri sono **coerenti**: margine sottile, positivo, non conclusivo.

### Perché il margine è fragile
1. **I 23 segnali senza esito pubblicato:** se fossero tutti SL, l'aspettativa scenderebbe a circa **−4,8 R** in totale, cioè negativa. Va verificato sui prezzi del broker.
2. **Spread e slittamento non inclusi:** con uno spread di 0,25 il costo è circa 0,035 R per operazione, cioè circa −8 R sul periodo. Resterebbero circa +10 R.
3. **La regola D2 (fuori range = scarto)** cambia il campione: alcuni segnali non verrebbero mai aperti. Si misura solo con il replay sui prezzi M1.
4. Un riepilogo settimanale del fornitore stesso ("PTM Momentum — Weekly Summary", 24-30 ago) riporta **Net −575 pips**, mentre la "Weekly Performance Review" della stessa settimana elenca solo i TP: i due riepiloghi contano cose diverse.

## 5. Prossimi passi
- Replay con i prezzi M1 di FPG: verificare gli esiti (in particolare i 23 senza esito), misurare l'effetto di spread e regola D2.
- Implementare `LIMIT ORDER CANCELLED` (CANCEL) e collegarlo al segnale tramite la risposta (19 su 21 sono risposte).
- Decisione di Lorenzo sul segnale 917 (range largo 6) e sul formato manuale 1128.
