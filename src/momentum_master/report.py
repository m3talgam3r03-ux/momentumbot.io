"""Rapporto giornaliero dal registro (master prompt, <report>), in italiano, ora di Roma.

Uso:
    python -m momentum_master.report data/momentum.sqlite              # oggi
    python -m momentum_master.report data/momentum.sqlite --giorno 2026-10-06

Il registro si apre in SOLA LETTURA: il rapporto non modifica nulla.
I risultati in punti e in R arriveranno con l'executor (DEMO): in PAPER non ci sono ordini.
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from collections import Counter
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

ROME = ZoneInfo("Europe/Rome")


def _day_bounds_utc(day: date) -> tuple[str, str]:
    start = datetime.combine(day, time(0), tzinfo=ROME).astimezone(UTC)
    end = datetime.combine(day + timedelta(days=1), time(0), tzinfo=ROME).astimezone(UTC)
    return start.isoformat(), end.isoformat()


def build_daily_report(db_path: Path, day: date) -> str:
    start, end = _day_bounds_utc(day)
    db = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    db.row_factory = sqlite3.Row
    try:
        rows = db.execute(
            "SELECT m.msg_id, m.event, m.date_utc, m.received_at_utc, m.raw_text, m.mode, "
            "c.category, c.notes, d.action, d.reason, d.details, d.target_msg_id "
            "FROM messages m LEFT JOIN classifications c ON c.message_row = m.id "
            "LEFT JOIN decisions d ON d.message_row = m.id "
            "WHERE m.received_at_utc >= ? AND m.received_at_utc < ? ORDER BY m.id",
            (start, end),
        ).fetchall()
    finally:
        db.close()

    out = [f"# Rapporto del {day:%d/%m/%Y} (ora di Roma)", ""]
    if not rows:
        return "\n".join([*out, "Nessun messaggio registrato in questa giornata."]) + "\n"

    modes = sorted({r["mode"] for r in rows})
    out += [f"Modalità: {', '.join(modes)}. Eventi registrati: {len(rows)}.", ""]

    categories = Counter(r["category"] or "(cancellazione)" for r in rows)
    out += ["## Messaggi per categoria", "", "| Categoria | Numero |", "|---|---|"]
    out += [f"| {k} | {v} |" for k, v in categories.most_common()]

    opens = [r for r in rows if r["action"] in ("OPEN_MARKET", "OPEN_PENDING")]
    rejects = Counter(f"{r['reason']} — {r['details'][:70]}" for r in rows
                      if r["action"] == "REJECT")  # fmt: skip
    out += ["", "## Segnali", "", f"- Aperture approvate: **{len(opens)}**"]
    out += [f"  - msg {r['msg_id']}: {r['action']} — {r['details']}" for r in opens]
    out += [f"- Scartati: **{sum(rejects.values())}**"]
    out += [f"  - {n} × {k}" for k, n in rejects.most_common()]

    actions = [r for r in rows if r["action"] in ("CANCEL", "CLOSE", "MODIFY")]
    if actions:
        out += ["", "## Azioni sugli aggiornamenti", ""]
        out += [f"- msg {r['msg_id']} → {r['action']} sul segnale {r['target_msg_id']}: "
                f"{r['details']}" for r in actions]  # fmt: skip

    latencies = sorted(
        (
            datetime.fromisoformat(r["received_at_utc"]) - datetime.fromisoformat(r["date_utc"])
        ).total_seconds()
        for r in rows
        if r["event"] == "new" and r["reason"] != "S5"
    )
    if latencies:
        p95 = latencies[min(len(latencies) - 1, round(0.95 * (len(latencies) - 1)))]
        out += ["", "## Latenza (pubblicazione → ricezione)", "",
                f"Mediana {latencies[len(latencies) // 2]:.2f} s · 95° percentile {p95:.2f} s · "
                f"massima {latencies[-1]:.2f} s (obiettivo: mediana < 1 s, 95° < 2 s)"]  # fmt: skip

    ambiguous = [r for r in rows if r["reason"] == "AMBIGUOUS"]
    out += ["", f"## AMBIGUOUS da rivedere ({len(ambiguous)})", ""]
    if not ambiguous:
        out.append("Nessuno.")
    for r in ambiguous:
        received = datetime.fromisoformat(r["received_at_utc"]).astimezone(ROME)
        text = (r["raw_text"] or "").replace("\n", " ⏎ ")[:200]
        out.append(f"- **{r['msg_id']}** ({received:%H:%M}) {r['details']}  \n  > {text}")
    return "\n".join(out) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m momentum_master.report")
    parser.add_argument("registro", help="file SQLite, es. data/momentum.sqlite")
    parser.add_argument("--giorno", default=None, help="AAAA-MM-GG (default: oggi, Roma)")
    args = parser.parse_args(argv)
    path = Path(args.registro)
    if not path.exists():
        print(f"Registro non trovato: {path}")
        return 1
    day = date.fromisoformat(args.giorno) if args.giorno else datetime.now(ROME).date()
    print(build_daily_report(path, day))
    return 0


if __name__ == "__main__":
    sys.exit(main())
