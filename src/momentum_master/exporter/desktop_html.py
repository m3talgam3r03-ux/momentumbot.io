"""Lettura dell'export HTML di Telegram Desktop (messages.html, messages2.html, ...).

Alternativa all'exporter Telethon quando Lorenzo esporta da Telegram Desktop in HTML.
Solo libreria standard (html.parser), nessun codice eseguito dal file: si leggono
soltanto tag e testo.

Cosa contiene l'HTML e cosa no:
- SÌ: id del messaggio, data con fuso (title="16.09.2026 20:22:05 UTC+01:00"), nome del
  mittente (solo sul primo di una serie: i messaggi "joined" ereditano il precedente),
  risposta a (href "#go_to_message996"), testo, presenza di foto/GIF/video;
- NO: id numerico del mittente (→ ``sender_id`` None, nome in ``post_author``), date di
  modifica, versione originale dei messaggi modificati.
"""

from __future__ import annotations

import html
import re
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta, timezone
from html.parser import HTMLParser
from pathlib import Path

from momentum_master.exporter.models import ExportedMessage

_DATE = re.compile(
    r"^(?P<d>\d{2})\.(?P<m>\d{2})\.(?P<y>\d{4}) (?P<H>\d{2}):(?P<M>\d{2}):(?P<S>\d{2}) "
    r"UTC(?P<sign>[+-])(?P<oh>\d{2}):(?P<om>\d{2})$"
)
_REPLY = re.compile(r"go_to_message(\d+)")
_MSG_ID = re.compile(r"^message(-?\d+)$")


def parse_desktop_date(title: str) -> datetime:
    """'16.09.2026 20:22:05 UTC+01:00' → datetime UTC."""
    m = _DATE.match(title.strip())
    if not m:
        raise ValueError(f"data non riconosciuta: {title!r}")
    offset = timedelta(hours=int(m["oh"]), minutes=int(m["om"]))
    tz = timezone(offset if m["sign"] == "+" else -offset)
    local = datetime(
        int(m["y"]), int(m["m"]), int(m["d"]), int(m["H"]), int(m["M"]), int(m["S"]), tzinfo=tz
    )
    return local.astimezone(UTC)


class _Parser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.records: list[dict] = []
        self._cur: dict | None = None
        self._stack: list[str] = []  # classi dei div aperti
        self._capture: str | None = None  # "text" | "from_name" | "service"
        self._buf: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = dict(attrs)
        classes = (a.get("class") or "").split()
        if self._cur is not None and self._cur["media"] in (None, "media"):
            # Le foto/GIF/video sono <a> o <div> con queste classi, dentro "media_wrap".
            for css, kind in (
                ("photo_wrap", "photo"),
                ("animated_wrap", "animation"),
                ("video_file_wrap", "video"),
            ):
                if css in classes:
                    self._cur["media"] = kind
        if tag == "div":
            self._stack.append(" ".join(classes))
            if "message" in classes and a.get("id") and _MSG_ID.match(a["id"] or ""):
                self._cur = {
                    "msg_id": int(_MSG_ID.match(a["id"])[1]),  # type: ignore[index]
                    "service": "service" in classes,
                    "joined": "joined" in classes,
                    "text": None, "from_name": None, "date": None, "reply_to": None,
                    "media": None, "service_text": None,
                }  # fmt: skip
                self.records.append(self._cur)
                if self._cur["service"]:
                    self._capture = None
            elif self._cur is not None:
                if "date" in classes and "details" in classes and a.get("title"):
                    self._cur["date"] = a["title"]
                elif classes == ["text"] or classes == ["text", "bold"]:
                    self._start_capture("text")
                elif "from_name" in classes:
                    self._start_capture("from_name")
                elif "body" in classes and "details" in classes and self._cur["service"]:
                    self._start_capture("service")
                elif "media_wrap" in classes and self._cur["media"] is None:
                    self._cur["media"] = "media"
        elif tag == "br" and self._capture:
            self._buf.append("\n")
        elif tag == "a" and self._cur is not None and self._stack and "reply_to" in self._stack[-1]:
            m = _REPLY.search(a.get("href") or "")
            if m:
                self._cur["reply_to"] = int(m[1])

    def _start_capture(self, kind: str) -> None:
        self._capture = kind
        self._capture_depth = len(self._stack)
        self._buf = []

    def handle_endtag(self, tag: str) -> None:
        if tag != "div" or not self._stack:
            return
        if self._capture and len(self._stack) == self._capture_depth:
            text = "".join(self._buf)
            # Telegram rientra il contenuto del div: si tolgono solo a capo/spazi esterni.
            text = text.strip("\n").strip()
            assert self._cur is not None
            key = {"text": "text", "from_name": "from_name", "service": "service_text"}
            self._cur[key[self._capture]] = text
            self._capture = None
        self._stack.pop()

    def handle_data(self, data: str) -> None:
        if self._capture:
            # Gli a capo veri nel sorgente HTML sono solo indentazione: quelli del messaggio
            # sono <br>. Si eliminano quindi gli a capo del sorgente.
            self._buf.append(data.replace("\n", ""))


def parse_desktop_html(paths: Iterable[Path], channel_id: int = 0) -> list[ExportedMessage]:
    """Legge uno o più file messages*.html, nell'ordine dato. Mittente ereditato nei 'joined'."""
    raw: list[dict] = []
    for path in paths:
        parser = _Parser()
        parser.feed(path.read_text(encoding="utf-8"))
        parser.close()
        raw.extend(parser.records)

    exported_at = datetime.now(UTC)
    out: list[ExportedMessage] = []
    last_sender: str | None = None
    last_date: datetime | None = None
    for r in raw:
        if r["msg_id"] < 0:
            continue  # id negativi = separatori di data inseriti da Telegram ("6 ottobre")
        if r["from_name"]:
            last_sender = r["from_name"]
        if r["date"]:
            last_date = parse_desktop_date(r["date"])
        if last_date is None:
            continue  # messaggio di servizio iniziale senza data: non utile
        if r["service"]:
            out.append(
                ExportedMessage(
                    channel_id=channel_id,
                    msg_id=r["msg_id"],
                    date_utc=last_date,
                    text="",
                    is_service=True,
                    service_action=html.unescape(r["service_text"] or "")[:200] or None,
                    exported_at_utc=exported_at,
                )
            )
            continue
        out.append(
            ExportedMessage(
                channel_id=channel_id,
                msg_id=r["msg_id"],
                date_utc=last_date,
                text=r["text"] or "",
                reply_to_msg_id=r["reply_to"],
                media_type=r["media"],
                post_author=last_sender,
                exported_at_utc=exported_at,
            )
        )
    return out


def main(argv: list[str] | None = None) -> int:
    """Uso: python -m momentum_master.exporter.desktop_html <cartella ChatExport> <out.jsonl>"""
    import sys

    args = sys.argv[1:] if argv is None else argv
    if len(args) != 2:
        print("Uso: python -m momentum_master.exporter.desktop_html <cartella> <out.jsonl>")
        return 2
    folder, out = Path(args[0]), Path(args[1])
    pages = sorted(
        folder.glob("messages*.html"),
        key=lambda p: int(re.sub(r"\D", "", p.stem) or "1"),
    )
    if not pages:
        print(f"Nessun file messages*.html in {folder}")
        return 1
    messages = parse_desktop_html(pages)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("".join(m.model_dump_json() + "\n" for m in messages), encoding="utf-8")
    print(f"{len(messages)} messaggi da {len(pages)} file → {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
