# CHANGELOG

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
