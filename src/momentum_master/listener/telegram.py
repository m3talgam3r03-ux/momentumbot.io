"""Collegamento Telethon del listener (sessione utente, SOLA LETTURA del gruppo).

Usa da Telethon solo: ``start``, ``get_entity``, ``iter_messages`` (arretrati all'avvio),
gli eventi ``NewMessage``/``MessageEdited``/``MessageDeleted`` filtrati sul solo gruppo
configurato, ``run_until_disconnected``. Nessun messaggio inviato al gruppo.

Uso:
    python -m momentum_master.listener --config config/config.yaml --db data/momentum.sqlite
    python -m momentum_master.listener --trova-gruppo MOMENTUM   # elenca gruppi e id
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from momentum_master.config import ConfigError, load_config
from momentum_master.exporter.__main__ import prepare_session_path
from momentum_master.exporter.export import message_to_record
from momentum_master.listener.core import ListenerCore, log_decision
from momentum_master.store import Store, StoreError

logger = logging.getLogger("momentum_master.listener")
HEARTBEAT_S = 15 * 60
RECONNECT_WAIT_S = 30


async def _catch_up(client, entity, core: ListenerCore, group_id: int) -> None:
    """Messaggi arrivati mentre il bot era spento: registrati, MAI eseguiti."""
    last = core.store.last_msg_id()
    if last == 0:
        logger.info("Registro vuoto: nessun recupero di arretrati (si parte da adesso)")
        return
    async for msg in client.iter_messages(entity, min_id=last, reverse=True):
        core.on_backlog_message(message_to_record(msg, group_id, core.clock()))
    logger.info("Arretrati registrati (non eseguiti): %s", core.stats.backlog)


async def _heartbeat(core: ListenerCore) -> None:
    while True:
        await asyncio.sleep(HEARTBEAT_S)
        logger.info(core.heartbeat())


def _client_from_env():
    from telethon import TelegramClient

    load_dotenv()
    try:
        api_id = int(os.environ["TG_API_ID"])
        api_hash = os.environ["TG_API_HASH"]
        session = prepare_session_path(os.environ["TG_SESSION_PATH"])
    except (KeyError, ValueError):
        return None
    return TelegramClient(session, api_id, api_hash, connection_retries=None,
                          retry_delay=5, auto_reconnect=True)  # fmt: skip


async def find_groups(text: str) -> int:
    """Elenca gruppi e canali il cui nome contiene ``text``, con l'id da mettere nel config."""
    client = _client_from_env()
    if client is None:
        print("Variabili TG_API_ID, TG_API_HASH, TG_SESSION_PATH mancanti nel .env")
        return 2
    await client.start()
    try:
        found = 0
        async for dialog in client.iter_dialogs():
            if (dialog.is_group or dialog.is_channel) and text.casefold() in dialog.name.casefold():
                found += 1
                print(f"{dialog.id:>16}  {dialog.name}")
        if not found:
            print(f"Nessun gruppo con '{text}' nel nome.")
    finally:
        await client.disconnect()
    return 0


async def run(config_path: Path, db_path: Path) -> int:
    from telethon import events

    cfg = load_config(config_path)
    if cfg.telegram.group_id is None:
        print("Manca telegram.group_id nel config. Trovalo con: "
              "python -m momentum_master.listener --trova-gruppo MOMENTUM")  # fmt: skip
        return 2
    client = _client_from_env()
    if client is None:
        print("Variabili TG_API_ID, TG_API_HASH, TG_SESSION_PATH mancanti nel .env")
        return 2

    store = Store(db_path)
    core = ListenerCore(cfg, store, on_decision=log_decision)
    group = cfg.telegram.group_id
    client.flood_sleep_threshold = 120

    @client.on(events.NewMessage(chats=group))
    async def _new(event) -> None:
        core.on_new_message(message_to_record(event.message, group, core.clock()))

    @client.on(events.MessageEdited(chats=group))
    async def _edited(event) -> None:
        core.on_edited_message(message_to_record(event.message, group, core.clock()))

    @client.on(events.MessageDeleted())
    async def _deleted(event) -> None:
        # Nei supergruppi Telethon fornisce chat_id; altrove può mancare: si ignora.
        if event.chat_id == group:
            core.on_deleted_messages(list(event.deleted_ids))

    logger.info("Modalità %s, config %s, registro %s", cfg.mode.value, cfg.meta.version, db_path)
    await client.start()
    try:
        entity = await client.get_entity(group)
        await _catch_up(client, entity, core, group)
        beat = asyncio.create_task(_heartbeat(core))
        while True:
            try:
                await client.run_until_disconnected()
            except (ConnectionError, OSError) as exc:  # rete persa oltre i tentativi interni
                logger.error("Disconnesso da Telegram (%s): nuovo tentativo tra %s s",
                             exc, RECONNECT_WAIT_S)  # fmt: skip
                await asyncio.sleep(RECONNECT_WAIT_S)
                await client.connect()
                await _catch_up(client, entity, core, group)
                continue
            break
        beat.cancel()
    finally:
        await client.disconnect()
        store.close()
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m momentum_master.listener")
    parser.add_argument("--config", default="config/config.yaml")
    parser.add_argument("--db", default="data/momentum.sqlite")
    parser.add_argument("--trova-gruppo", metavar="TESTO", help="elenca gruppi e id, poi esce")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    if args.trova_gruppo:
        return asyncio.run(find_groups(args.trova_gruppo))
    try:
        return asyncio.run(run(Path(args.config), Path(args.db)))
    except (ConfigError, StoreError) as exc:
        print(exc)
        return 1
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    sys.exit(main())
