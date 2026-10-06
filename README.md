# MOMENTUM MASTER

Legge il canale Telegram WDT MOMENTUM, classifica ogni messaggio, decide con regole deterministiche e i filtri di Lorenzo, ed esegue su **un solo** conto master FPG (MT5). La replica ai follower la fa il copy trading di FPG.

- Specifica completa: [`docs/prompt-bot-momentum-fpg.md`](docs/prompt-bot-momentum-fpg.md)
- Stato del progetto: [`STATO_PROGETTO.md`](STATO_PROGETTO.md)

> Stato attuale: **passo 1 (esportazione dello storico)**. Non esiste ancora codice che invii ordini.

## Installazione (sviluppo)

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate    Linux/macOS: source .venv/bin/activate
pip install -r requirements-dev.txt
pip install -e .
pytest            # tutti i test devono passare
ruff check src tests
```

## Passo 1: esportare lo storico del canale

L'exporter usa da Telegram **solo lettura**: niente messaggi inviati, niente conferme di lettura, nessuna iscrizione.

1. Con l'account Telegram **dedicato al bot** (iscritto a WDT MOMENTUM, con verifica in due passaggi attiva) vai su <https://my.telegram.org> → *API development tools* e crea un'app. Annota `api_id` e `api_hash`.
2. Copia `.env.example` in `.env` e compila `TG_API_ID` e `TG_API_HASH`. **Non incollarli mai in chat né nel repository.**
3. Prova con 50 messaggi:
   ```bash
   python -m momentum_master.exporter export --channel @USERNAME_CANALE --out data/prova.jsonl --limit 50
   ```
   Al primo avvio Telethon chiede numero di telefono, codice ricevuto su Telegram e password 2FA. Crea il file di sessione in `data/`: **proteggilo**, perché chi lo possiede controlla l'account.
   Se il canale non ha username, usa l'id numerico (es. `-1001234567890`).
4. Export completo:
   ```bash
   python -m momentum_master.exporter export --channel @USERNAME_CANALE --out data/storico.jsonl
   ```
   Se si interrompe, rilancia lo stesso comando: riprende da dove era arrivato e non crea duplicati.
5. Il riepilogo viene stampato e salvato in `data/storico.summary.json`. Per rigenerarlo:
   ```bash
   python -m momentum_master.exporter stats --file data/storico.jsonl
   ```

### Limiti noti dell'export
- Per i messaggi modificati Telegram restituisce solo la **versione finale**. Un replay basato sullo storico può quindi risultare più favorevole della realtà.
- I messaggi **cancellati** non ci sono. Il riepilogo stima quanti sono dai buchi negli id.
- Gli screenshot vengono registrati come media: non vengono letti e non saranno mai eseguiti.

## Struttura

```
src/momentum_master/
  exporter/     passo 1: storico → JSONL
  classifier/   passo 1.1b: normalize.py, numbers.py  (regole: passo 3)
tests/
docs/
```
