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

### Modo più semplice: export di Telegram Desktop
Telegram Desktop → gruppo → ⋮ → **Esporta cronologia chat** (senza media; HTML o JSON). Per l'HTML:
```bash
python -m momentum_master.exporter.desktop_html "C:\percorso\ChatExport_2026-10-06" data/storico.jsonl
```
Limite: l'HTML non contiene l'id numerico del mittente né le date di modifica.

### Modo rapido (Windows, doppio clic)
Nella cartella `scripts\windows\`, in ordine:
1. `1_installa.bat`: crea l'ambiente, lancia i test (devono passare tutti) e apre `.env` da compilare.
2. `2_esporta_prova.bat`: prova con i primi 50 messaggi.
3. `3_esporta_tutto.bat`: export completo + rapporto `data\esplorazione.md`. Se si interrompe, rilancialo.

Prima servono Python 3.12 (con "Add python.exe to PATH") e `api_id`/`api_hash` (punto 1 qui sotto).

### Modo manuale

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

## Configurazione

Il file è `config/config.yaml`, commentato riga per riga. Per controllarlo:
```bash
python -m momentum_master.config config/config.yaml
```
- Se il config non è valido, il bot **non parte** e l'errore indica il campo sbagliato.
- `demo` e `live` vengono rifiutati finché i filtri non sono confermati e mancano i dati di FPG (simbolo, server, mittenti autorizzati, admin).
- Le chiavi sconosciute vengono rifiutate, quindi un errore di battitura non passa inosservato.
- Gli orari vanno sempre tra virgolette (`"23:50"`).
- Nessun segreto nel config: i segreti vanno solo nel `.env`.

## Decisioni e registro (PAPER)

Per ogni messaggio: **classifica → decide → registra** (`pipeline.process_message`).
- Il motore decisionale (`decision/engine.py`) è una funzione pura: prima le regole di sicurezza S1-S11, poi i filtri F del config. Ogni scarto ha il suo codice (S5, F5…).
- Il registro (`data/momentum.sqlite`) conserva testo originale, categoria, decisione, motivo, prezzi e versione del config.
- Per ricostruire una decisione:
  ```bash
  python -m momentum_master.store data/momentum.sqlite <msg_id>
  ```

## PAPER in tempo reale (listener)

1. Trova l'id del gruppo: doppio clic su `scripts\windows\4_trova_id_gruppo.bat` (oppure `python -m momentum_master.listener --trova-gruppo MOMENTUM`) e mettilo in `config/config.yaml` → `telegram.group_id`.
2. Avvia: doppio clic su `scripts\windows\5_avvia_paper.bat` (oppure `python -m momentum_master.listener`).

Il listener legge **solo** il gruppo configurato, in sola lettura:
- nuovi messaggi → classifica → collega → decide → registra in `data/momentum.sqlite`;
- messaggi modificati → registrati, non aprono mai (S8);
- messaggi cancellati → pendente collegato: CANCEL; posizione a mercato: notifica;
- all'avvio, i messaggi arrivati mentre era spento vengono registrati e **mai** eseguiti;
- heartbeat nel log ogni 15 minuti, con la latenza.

Senza una fonte di prezzi (MT5 non ancora collegato), le aperture vengono registrate con il motivo S7 "prezzo non disponibile". In PAPER non parte comunque nessun ordine.

## Esplorazione dello storico (supporto al passo 2)

```bash
python -m momentum_master.analysis --file data/storico.jsonl --out data/esplorazione.md
```
Raggruppa i messaggi per "forma" (numeri sostituiti da `N`) e conta parole, emoji, risposte, modifiche e grandezza dei numeri. Non classifica nulla: è la base per scrivere `catalogo_formati.md` partendo dai messaggi reali.

## Struttura

```
src/momentum_master/
  exporter/     passo 1: storico → JSONL
  classifier/   passo 1.1b: normalize.py, numbers.py  (regole: passo 3)
  decision/     motore decisionale, regole di entrata (range), scelta TP/BE
  listener/     ascolto del gruppo in tempo reale (core testabile + Telethon)
  store.py      registro SQLite + comando "spiega"
  pipeline.py   classifica → decide → registra
  config.py     modello e validazione del config
  analysis/     esplorazione dello storico per il catalogo dei formati
config/       config.yaml commentato
scripts/windows/  installazione ed export con doppio clic
tests/
docs/
```
