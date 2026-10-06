"""Riga di comando dell'exporter.

Esempi:
    python -m momentum_master.exporter export --channel -1001234567890 --out data/storico.jsonl
    python -m momentum_master.exporter export --channel @canale --out data/prova.jsonl --limit 50
    python -m momentum_master.exporter stats --file data/storico.jsonl
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from momentum_master.exporter.export import dump_json, export_channel, read_jsonl
from momentum_master.exporter.stats import format_summary, summarize

logger = logging.getLogger("momentum_master.exporter")


def parse_channel(value: str) -> int | str:
    """Id numerico (anche negativo, formato -100...) oppure username."""
    stripped = value.strip()
    if stripped.lstrip("-").isdigit():
        return int(stripped)
    return stripped


def _require_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise SystemExit(f"Variabile {name} mancante nel file .env (vedi .env.example)")
    return value


async def _run_export(args: argparse.Namespace) -> int:
    # Import locale: i test e il comando "stats" non richiedono Telethon.
    from telethon import TelegramClient

    load_dotenv()
    api_id = int(_require_env("TG_API_ID"))
    api_hash = _require_env("TG_API_HASH")
    session_path = _require_env("TG_SESSION_PATH")

    client = TelegramClient(session_path, api_id, api_hash)
    # FloodWait fino a questa soglia (secondi) viene atteso automaticamente da Telethon.
    client.flood_sleep_threshold = args.flood_sleep_threshold
    # Al primo avvio chiede numero di telefono, codice e password 2FA da tastiera.
    await client.start()
    try:
        channel = parse_channel(args.channel)
        try:
            await client.get_entity(channel)
        except ValueError:
            # Id non ancora in cache: carico i dialoghi (sola lettura) e riprovo.
            await client.get_dialogs()
        result = await export_channel(
            client,
            channel,
            Path(args.out),
            resume=not args.no_resume,
            limit=args.limit,
            wait_time=args.wait_time,
        )
    finally:
        await client.disconnect()

    print(
        f"Canale {result.channel_id}: {result.new_messages} nuovi messaggi "
        f"(ripresa da id {result.resumed_from_msg_id}, duplicati saltati "
        f"{result.skipped_duplicates}) → {result.out_path}"
    )
    _print_stats(Path(args.out))
    return 0


def _print_stats(path: Path) -> dict:
    summary = summarize(read_jsonl(path))
    print(format_summary(summary))
    summary_path = path.with_suffix(".summary.json")
    dump_json(summary, summary_path)
    print(f"Riepilogo salvato in {summary_path}")
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m momentum_master.exporter")
    sub = parser.add_subparsers(dest="command", required=True)

    exp = sub.add_parser("export", help="esporta lo storico del canale (sola lettura)")
    exp.add_argument("--channel", required=True, help="id numerico (-100...) o @username")
    exp.add_argument("--out", required=True, help="file JSONL di destinazione")
    exp.add_argument("--limit", type=int, default=None, help="massimo messaggi (prova)")
    exp.add_argument("--wait-time", type=float, default=None, help="pausa tra richieste (s)")
    exp.add_argument("--flood-sleep-threshold", type=int, default=120)
    exp.add_argument("--no-resume", action="store_true", help="rifiuta un file esistente")

    st = sub.add_parser("stats", help="riepilogo di un file già esportato")
    st.add_argument("--file", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    args = build_parser().parse_args(argv)
    if args.command == "export":
        return asyncio.run(_run_export(args))
    _print_stats(Path(args.file))
    return 0


if __name__ == "__main__":
    sys.exit(main())
