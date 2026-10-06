# CHANGELOG

## [0.1.0] - 2026-10-06
### Aggiunto
- Base del progetto (pyproject, ruff, pytest, requirements con versioni fissate, `.env.example`).
- `exporter`: esporta in sola lettura lo storico del canale in JSONL (id, data UTC, testo invariato, reply_to, citazione, data di modifica, tipo di media, inoltro, firma, messaggi di servizio), con ripresa e riepilogo statistico.
- `classifier.normalize`: NFKC, emoji trasformate in token descrittivi, spazi e righe uniformati.
- `classifier.numbers`: numeri con virgola o punto; i casi ambigui ("2,650") vengono segnalati, mai scelti.
- `docs/prompt-bot-momentum-fpg.md`: master prompt v1.

### Impatto sui follower
Nessuno. Non esiste ancora codice di esecuzione.
