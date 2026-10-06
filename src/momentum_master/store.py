"""Registro SQLite: messaggi, classificazioni, decisioni.

Obiettivo (master prompt): ogni decisione ricostruibile in meno di un minuto,
messaggio → categoria → decisione → (ordine → esito, quando ci sarà l'executor).

- modalità WAL; scritture serializzate da un lock (una sola connessione);
- idempotenza: lo stesso messaggio (msg_id + evento + data di modifica) si salva una volta;
- i prezzi sono salvati come TESTO (Decimal esatto), le date in ISO 8601 UTC;
- il testo originale del messaggio è salvato invariato.
"""

from __future__ import annotations

import sqlite3
import threading
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from momentum_master.classifier.models import ClassifiedMessage, Side
from momentum_master.decision.engine import Action, Decision, EngineState, RecentSignal
from momentum_master.exporter.models import ExportedMessage

SCHEMA = """
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    msg_id INTEGER NOT NULL,
    event TEXT NOT NULL,                  -- new | edit
    edit_date_utc TEXT NOT NULL DEFAULT '',
    date_utc TEXT NOT NULL,
    received_at_utc TEXT NOT NULL,
    sender_id INTEGER,
    reply_to_msg_id INTEGER,
    raw_text TEXT NOT NULL,
    mode TEXT NOT NULL,                   -- paper | demo | live
    UNIQUE (msg_id, event, edit_date_utc)
);
CREATE TABLE IF NOT EXISTS classifications (
    message_row INTEGER PRIMARY KEY REFERENCES messages(id),
    category TEXT NOT NULL,
    side TEXT, order_hint TEXT,
    entry_min TEXT, entry_max TEXT, sl TEXT, tps TEXT,
    confidence REAL NOT NULL, method TEXT NOT NULL, notes TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS decisions (
    message_row INTEGER PRIMARY KEY REFERENCES messages(id),
    msg_id INTEGER NOT NULL,
    action TEXT NOT NULL, reason TEXT NOT NULL, details TEXT NOT NULL,
    decided_at_utc TEXT NOT NULL, config_version TEXT NOT NULL,
    side TEXT, order_type TEXT, entry_price TEXT, sl TEXT, tp TEXT, tp_index INTEGER,
    expiry_utc TEXT, bid TEXT, ask TEXT, spread TEXT
);
CREATE INDEX IF NOT EXISTS ix_decisions_time ON decisions(decided_at_utc);
CREATE INDEX IF NOT EXISTS ix_messages_msg ON messages(msg_id);
"""


def _s(value: object) -> str | None:
    return None if value is None else str(value)


def _iso(value: datetime | None) -> str | None:
    return None if value is None else value.astimezone(UTC).isoformat()


class Store:
    def __init__(self, path: Path | str) -> None:
        if str(path) != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._db = sqlite3.connect(str(path), check_same_thread=False, isolation_level=None)
        self._db.row_factory = sqlite3.Row
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.execute("PRAGMA foreign_keys=ON")
        self._db.executescript(SCHEMA)

    def close(self) -> None:
        with self._lock:
            self._db.close()

    # --- scrittura ---------------------------------------------------------------------

    def record(
        self,
        msg: ExportedMessage,
        classified: ClassifiedMessage,
        decision: Decision,
        *,
        event: str,
        received_at_utc: datetime,
        mode: str,
    ) -> bool:
        """Salva messaggio + classificazione + decisione in una transazione.

        Restituisce False se lo stesso evento era già registrato (nessuna scrittura).
        """
        with self._lock:
            self._db.execute("BEGIN IMMEDIATE")
            try:
                cur = self._db.execute(
                    "INSERT OR IGNORE INTO messages (msg_id, event, edit_date_utc, date_utc, "
                    "received_at_utc, sender_id, reply_to_msg_id, raw_text, mode) "
                    "VALUES (?,?,?,?,?,?,?,?,?)",
                    (
                        msg.msg_id, event, _iso(msg.edit_date_utc) or "", _iso(msg.date_utc),
                        _iso(received_at_utc), msg.sender_id, msg.reply_to_msg_id, msg.text, mode,
                    ),
                )  # fmt: skip
                if cur.rowcount == 0:
                    self._db.execute("ROLLBACK")
                    return False
                row = cur.lastrowid
                self._db.execute(
                    "INSERT INTO classifications VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        row, classified.category.value, _s(classified.side),
                        _s(classified.order_hint), _s(classified.entry_min),
                        _s(classified.entry_max), _s(classified.sl),
                        ",".join(str(t) for t in classified.tps), classified.confidence,
                        classified.method.value, classified.notes,
                    ),
                )  # fmt: skip
                d = decision
                self._db.execute(
                    "INSERT INTO decisions VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        row, d.msg_id, d.action.value, d.reason.value, d.details,
                        _iso(d.decided_at_utc), d.config_version, _s(d.side), d.order_type,
                        _s(d.entry_price), _s(d.sl), _s(d.tp), d.tp_index, _iso(d.expiry_utc),
                        _s(d.bid), _s(d.ask), _s(d.spread),
                    ),
                )  # fmt: skip
                self._db.execute("COMMIT")
                return True
            except Exception:
                self._db.execute("ROLLBACK")
                raise

    # --- lettura -----------------------------------------------------------------------

    def engine_state(self, now_utc: datetime, dedup_window_s: int) -> EngineState:
        """Stato per il motore: id elaborati, segnali recenti (S11), aperture di oggi (UTC).

        ``open_positions`` resta 0 finché non c'è l'executor: in PAPER non esistono posizioni.
        """
        since = _iso(now_utc - timedelta(seconds=dedup_window_s))
        day_start = _iso(now_utc.astimezone(UTC).replace(hour=0, minute=0, second=0, microsecond=0))
        opens = (Action.OPEN_MARKET.value, Action.OPEN_PENDING.value)
        with self._lock:
            ids = {r[0] for r in self._db.execute("SELECT DISTINCT msg_id FROM messages")}
            # S11: confronto con QUALSIASI segnale già visto (aperto o scartato): la seconda
            # copia di un segnale è lo stesso segnale, non una nuova occasione.
            recent = self._db.execute(
                "SELECT c.side, c.entry_min, c.sl, d.decided_at_utc FROM decisions d "
                "JOIN classifications c USING (message_row) "
                "JOIN messages m ON m.id = d.message_row "
                "WHERE c.category = 'NEW_SIGNAL_COMPLETE' AND m.event = 'new' "
                "AND d.decided_at_utc >= ?",
                (since,),
            ).fetchall()
            today = self._db.execute(
                "SELECT COUNT(*) FROM decisions WHERE action IN (?,?) AND decided_at_utc >= ?",
                (*opens, day_start),
            ).fetchone()[0]
        return EngineState(
            processed_msg_ids=frozenset(ids),
            recent_signals=tuple(
                RecentSignal(
                    Side(r["side"]),
                    Decimal(r["entry_min"]),
                    Decimal(r["sl"]),
                    datetime.fromisoformat(r["decided_at_utc"]),
                )
                for r in recent
            ),
            trades_today=today,
        )

    def explain(self, msg_id: int) -> str:
        """Ricostruzione leggibile di tutto ciò che è successo a un messaggio."""
        with self._lock:
            rows = self._db.execute(
                "SELECT m.*, c.category, c.side AS c_side, c.order_hint, c.entry_min, "
                "c.entry_max, c.sl AS c_sl, c.tps, c.notes, d.action, d.reason, d.details, "
                "d.decided_at_utc, d.config_version, d.order_type, d.entry_price, d.sl AS d_sl, "
                "d.tp, d.tp_index, d.expiry_utc, d.bid, d.ask, d.spread "
                "FROM messages m LEFT JOIN classifications c ON c.message_row = m.id "
                "LEFT JOIN decisions d ON d.message_row = m.id WHERE m.msg_id = ? ORDER BY m.id",
                (msg_id,),
            ).fetchall()
        if not rows:
            return f"Nessun evento registrato per il messaggio {msg_id}."
        out: list[str] = []
        for r in rows:
            out += [
                f"=== Messaggio {r['msg_id']} ({r['event']}, modalità {r['mode']}) ===",
                f"Pubblicato: {r['date_utc']}  Ricevuto: {r['received_at_utc']}  "
                f"Mittente: {r['sender_id']}  Risposta a: {r['reply_to_msg_id']}",
                "Testo originale:",
                *(f"  | {line}" for line in r["raw_text"].splitlines() or [""]),
                f"Categoria: {r['category']}  {r['c_side'] or ''} {r['order_hint'] or ''}  "
                f"entrata {r['entry_min']}-{r['entry_max']}  SL {r['c_sl']}  TP [{r['tps']}]",
                f"Note classificatore: {r['notes']}",
                f"Decisione: {r['action']} ({r['reason']}) — {r['details']}",
                f"  alle {r['decided_at_utc']}, config {r['config_version']}, "
                f"bid {r['bid']} ask {r['ask']} spread {r['spread']}",
            ]
            if r["action"] in (Action.OPEN_MARKET.value, Action.OPEN_PENDING.value):
                out.append(
                    f"  Ordine: {r['order_type']} @ {r['entry_price']}  SL {r['d_sl']}  "
                    f"TP{r['tp_index']} {r['tp']}  scadenza {r['expiry_utc'] or '-'}"
                )
            out.append("")
        return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    """Uso: python -m momentum_master.store data/momentum.sqlite <msg_id>"""
    import sys

    args = sys.argv[1:] if argv is None else argv
    if len(args) != 2 or not args[1].isdigit():
        print("Uso: python -m momentum_master.store <file.sqlite> <msg_id>")
        return 2
    if not Path(args[0]).exists():
        print(f"Registro non trovato: {args[0]}")
        return 1
    store = Store(args[0])
    try:
        print(store.explain(int(args[1])))
    finally:
        store.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
