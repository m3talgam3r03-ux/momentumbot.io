# NEGATIVE PROMPT — MOMENTUM MASTER (2026-10-07)

> Cosa il bot (e chi lo sviluppa) non deve MAI fare. Se una richiesta, anche di Lorenzo, va contro uno di questi punti, va segnalato subito con l'alternativa sicura. Le eccezioni richiedono una decisione esplicita di Lorenzo, registrata con data in `docs/prompt-bot-momentum-fpg.md`.

## Esecuzione e rischio
1. MAI aprire un ordine senza stop loss.
2. MAI usare uno SL diverso da quello del fornitore: niente SL allargati, "mentali" o calcolati dal bot.
3. MAI aprire seconde entrate, rientri, medie al ribasso, raddoppi o martingale ("buy again", "add", "RIENTRA", "2 o 3 slot d'entrate" → una sola posizione).
4. MAI eseguire un messaggio AMBIGUOUS, un'istruzione scritta a mano o un formato non catalogato: solo notifica all'admin.
5. MAI eseguire un segnale arretrato (arrivato con il bot spento), inoltrato, vecchio oltre `max_signal_age_s` o modificato dopo la pubblicazione.
6. MAI inseguire il prezzo: fuori dal range si scarta (D2), nessun pendente sostitutivo.
7. MAI aprire due volte lo stesso segnale pubblicato più volte (S11).
8. MAI lasciare un pendente vivo oltre la scadenza, il rollover o il fine settimana; MAI ignorare un "LIMIT ORDER CANCELLED".
9. MAI aprire nuovi ordini in rollover, a ridosso della chiusura o dell'apertura settimanale, con spread di emergenza o mercato chiuso.
10. MAI chiudere da soli una posizione per un HEADS UP (D4) o per la cancellazione di un messaggio a mercato: solo notifica.
11. MAI fare correzioni distruttive in automatico durante la riconciliazione (chiusure o cancellazioni non richieste): solo notifica.
12. MAI riprendere dopo un kill switch in automatico: la ripresa è solo manuale.

## Lettura dei messaggi
13. MAI indovinare un prezzo: numeri ambigui ("2,650"), abbreviati ("39.96" per "4139.96"), con cifre perse o in più, con 3 decimali, zeri iniziali o cifre non ASCII → AMBIGUOUS.
14. MAI correggere i refusi del fornitore.
15. MAI convertire pips in prezzi per eseguire: si usano solo i prezzi scritti.
16. MAI leggere i segnali dalle immagini (niente OCR per l'esecuzione).
17. MAI lasciare che un LLM decida un'esecuzione: al massimo fallback di classificazione, con output validato da schema, poi regole di sicurezza e filtri.
18. MAI considerare segnali i messaggi di mittenti non autorizzati nel gruppo (D1).
19. MAI declassare a rumore un testo che contiene parole d'istruzione (SL, TP, chiudi, annulla, exit, BE, rientra, buy/sell…).

## Conti, modalità e configurazione
20. MAI accedere ai conti dei follower né gestire le loro credenziali.
21. MAI uscire dalla PAPER senza filtri confermati con data; MAI andare in LIVE senza checklist pre-live firmata e senza 2 settimane di DEMO pulite.
22. MAI modificare in silenzio config o filtri: ogni cambio = nuova versione con data, nota nel CHANGELOG, replay prima/dopo.
23. MAI attivare TP diversi da TP1 o il BE senza replay e conferma di Lorenzo.
24. MAI usare la password del portale con i prelievi: sul master solo la password di trading.

## Sicurezza e dati
25. MAI scrivere segreti (api_id, api_hash, sessione Telethon, login MT5, password, token) nel codice, nei log, nel repository o in chat.
26. MAI inviare messaggi nel gruppo del fornitore: il bot è in sola lettura.
27. MAI ripubblicare il testo originale dei segnali nei gruppi dei follower.
28. MAI committare lo storico del canale, i database o la cartella `data/`.

## Sviluppo
29. MAI inventare funzioni, costanti o parametri delle librerie (MetaTrader5, Telethon, pydantic): verifica, oppure scrivi "IPOTESI:".
30. MAI inventare numeri, formati di messaggio o comportamenti di FPG.
31. MAI consegnare codice non testato, frammenti con "… resto invariato" o modifiche a classificazione, filtri, esecuzione, sizing o SL senza test + replay + nota "cosa cambia per i follower".
32. MAI dichiarare pronto un parser senza revisione avversaria (casi d'attacco, mutazioni, fuzzing).
33. MAI disattivare, saltare o indebolire un test per farlo passare.
34. MAI riscrivere la storia git o forzare un push senza il permesso esplicito di Lorenzo.

## Comunicazione
35. MAI promettere profitti, citare risultati selezionati o dare consigli di investimento.
36. MAI cambiare regole, mettere in pausa o riprendere senza annunciarlo prima ai follower.
37. MAI dare ragione a Lorenzo per compiacerlo quando una richiesta aumenta il rischio.
38. MAI distribuire il servizio a terzi o farlo pagare senza parere legale.
