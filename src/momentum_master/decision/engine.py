"""Motore decisionale: (ClassifiedMessage, contesto, mercato, stato, config) → Decision.

Funzione PURA e deterministica: niente I/O, niente orologio di sistema (l'ora arriva dal
contesto), stesso input → stessa decisione. È il punto in cui si decide se un segnale
diventa un ordine, quindi ogni regola ha il suo reason_code e il suo test.

Ordine dei controlli (master prompt): prima le regole di sicurezza S1-S11 (sempre attive,
non disattivabili), poi i filtri di Lorenzo F1-F13. Il primo controllo che fallisce decide.

Il motore non sa se siamo in PAPER, DEMO o LIVE: decide sempre allo stesso modo.
È lo strato successivo a registrare (PAPER) o eseguire (DEMO/LIVE) la decisione.

Unità: prezzi e distanze in punti di prezzo (1,00 sull'oro).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, time, timedelta
from decimal import Decimal
from enum import StrEnum
from typing import Literal
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict

from momentum_master.classifier.models import Category, ClassifiedMessage, OrderHint, Side
from momentum_master.config import AppConfig, TimeWindow
from momentum_master.decision.entry import check_range_entry
from momentum_master.decision.targets import select_take_profit

ROME = ZoneInfo("Europe/Rome")


class Action(StrEnum):
    OPEN_MARKET = "OPEN_MARKET"
    OPEN_PENDING = "OPEN_PENDING"
    WAIT = "WAIT"
    MODIFY = "MODIFY"
    CLOSE = "CLOSE"
    CANCEL = "CANCEL"
    REJECT = "REJECT"
    IGNORE = "IGNORE"


class Reason(StrEnum):
    OK = "OK"
    NOT_A_SIGNAL = "NOT_A_SIGNAL"
    AMBIGUOUS = "AMBIGUOUS"
    S1 = "S1"  # segnale non completo
    S2 = "S2"  # SL/TP dalla parte sbagliata
    S3 = "S3"  # entrata troppo lontana dal prezzo (errore di battitura?)
    S4 = "S4"  # SL troppo vicino (stops level del broker)
    S5 = "S5"  # segnale vecchio, inoltrato o arretrato
    S6 = "S6"  # msg_id già elaborato
    S7 = "S7"  # mercato chiuso / simbolo non negoziabile
    S8 = "S8"  # modifica di un messaggio: non apre mai
    S9 = "S9"  # finestra di mercato a rischio
    S10 = "S10"  # spread di emergenza
    S11 = "S11"  # doppione dello stesso segnale
    F1 = "F1"
    F2 = "F2"
    F3 = "F3"
    F5 = "F5"
    F8 = "F8"
    F9 = "F9"
    F11 = "F11"
    F12 = "F12"


@dataclass(frozen=True)
class MessageContext:
    """Come è arrivato il messaggio."""

    received_at_utc: datetime
    event: Literal["new", "edit"] = "new"
    is_forward: bool = False
    is_live: bool = True  # False = arretrato letto all'avvio: si registra, non si esegue


@dataclass(frozen=True)
class MarketSnapshot:
    """Mercato al momento della decisione (fornito dall'adattatore MT5)."""

    bid: Decimal
    ask: Decimal
    server_time: datetime  # ora del SERVER MT5, senza fuso
    trade_allowed: bool  # S7: mercato aperto e simbolo negoziabile
    stops_level: Decimal  # trade_stops_level × point, in punti di prezzo
    # S9: minuti alla chiusura settimanale / dall'apertura settimanale.
    # None = sconosciuti → per sicurezza nessun nuovo ordine.
    minutes_to_week_close: int | None
    minutes_since_week_open: int | None

    @property
    def spread(self) -> Decimal:
        return self.ask - self.bid


@dataclass(frozen=True)
class RecentSignal:
    side: Side
    entry_min: Decimal
    sl: Decimal
    decided_at_utc: datetime


@dataclass(frozen=True)
class EngineState:
    """Stato letto dal registro prima di decidere."""

    processed_msg_ids: frozenset[int] = frozenset()
    recent_signals: tuple[RecentSignal, ...] = ()
    trades_today: int = 0
    open_positions: int = 0


class Decision(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    msg_id: int
    action: Action
    reason: Reason
    details: str
    decided_at_utc: datetime
    config_version: str
    side: Side | None = None
    order_type: Literal["MARKET", "LIMIT"] | None = None
    entry_price: Decimal | None = None  # pendente: prezzo LIMIT; mercato: prezzo atteso
    sl: Decimal | None = None
    tp: Decimal | None = None
    tp_index: int | None = None
    expiry_utc: datetime | None = None
    bid: Decimal | None = None
    ask: Decimal | None = None
    spread: Decimal | None = None

    @property
    def is_open(self) -> bool:
        return self.action in (Action.OPEN_MARKET, Action.OPEN_PENDING)


@dataclass
class _Ctx:
    msg: ClassifiedMessage
    mctx: MessageContext
    market: MarketSnapshot
    state: EngineState
    cfg: AppConfig
    tp: Decimal | None = None
    tp_index: int | None = None
    extra: dict[str, object] = field(default_factory=dict)


def _in_window(t: time, window: TimeWindow) -> bool:
    """Vero se t è nella finestra; gestisce le finestre a cavallo della mezzanotte."""
    if window.start <= window.end:
        return window.start <= t < window.end
    return t >= window.start or t < window.end


def _minutes_until(server_now: datetime, target: time) -> int:
    candidate = server_now.replace(hour=target.hour, minute=target.minute, second=0, microsecond=0)
    if candidate <= server_now:
        candidate += timedelta(days=1)
    return int((candidate - server_now).total_seconds() // 60)


# --- controlli: ognuno restituisce None (ok) oppure (Reason, dettagli) ----------------

Check = tuple[Reason, str] | None


def _s8_edit(c: _Ctx) -> Check:
    if c.mctx.event == "edit":
        return Reason.S8, "messaggio modificato: non apre mai, solo notifica admin"
    return None


def _s6_already_processed(c: _Ctx) -> Check:
    if c.msg.msg_id in c.state.processed_msg_ids:
        return Reason.S6, f"msg_id {c.msg.msg_id} già elaborato"
    return None


def _s5_age_and_origin(c: _Ctx) -> Check:
    if c.mctx.is_forward:
        return Reason.S5, "messaggio inoltrato"
    if not c.mctx.is_live:
        return Reason.S5, "messaggio arretrato (arrivato mentre il bot era spento)"
    age = (c.mctx.received_at_utc - c.msg.date_utc).total_seconds()
    if age > c.cfg.safety.max_signal_age_s:
        return Reason.S5, f"segnale vecchio di {age:.0f} s (max {c.cfg.safety.max_signal_age_s})"
    return None


def _s1_complete(c: _Ctx) -> Check:
    if c.msg.category is not Category.NEW_SIGNAL_COMPLETE:
        return Reason.S1, f"categoria {c.msg.category}: si apre solo NEW_SIGNAL_COMPLETE"
    choice = select_take_profit(list(c.msg.tps), c.cfg.targets)
    if not choice.ok:
        return Reason.S1, choice.reason
    c.tp, c.tp_index = choice.price, choice.index_used
    return None


def _s7_market(c: _Ctx) -> Check:
    if not c.market.trade_allowed:
        return Reason.S7, "mercato chiuso o simbolo non negoziabile"
    return None


def _s9_risky_windows(c: _Ctx) -> Check:
    safety = c.cfg.safety
    if _in_window(c.market.server_time.time(), safety.rollover_window):
        return Reason.S9, f"rollover ({safety.rollover_window.start}-{safety.rollover_window.end})"
    to_close, since_open = c.market.minutes_to_week_close, c.market.minutes_since_week_open
    if to_close is None or since_open is None:
        return Reason.S9, "orari di sessione sconosciuti: per sicurezza nessun ordine"
    if to_close < safety.friday_close_block_min:
        return Reason.S9, f"{to_close} min alla chiusura settimanale"
    if since_open < safety.week_open_block_min:
        return Reason.S9, f"{since_open} min dall'apertura settimanale"
    return None


def _s10_spread_emergency(c: _Ctx) -> Check:
    if c.market.spread > c.cfg.safety.spread_emergency:
        return Reason.S10, f"spread {c.market.spread} > emergenza {c.cfg.safety.spread_emergency}"
    return None


def _s2_coherence(c: _Ctx) -> Check:
    m = c.msg
    assert m.entry_min is not None and m.entry_max is not None and m.sl is not None
    tp1 = m.tps[0]
    if m.side is Side.BUY:
        ok = m.sl < m.entry_min and tp1 > m.entry_max and c.tp > m.entry_max  # type: ignore[operator]
    else:
        ok = m.sl > m.entry_max and tp1 < m.entry_min and c.tp < m.entry_min  # type: ignore[operator]
    if not ok:
        return (
            Reason.S2,
            f"{m.side}: SL {m.sl} / TP {tp1} incoerenti con entrata {m.entry_min}-{m.entry_max}",
        )
    return None


def _s3_deviation(c: _Ctx) -> Check:
    m, mid = c.msg, (c.market.bid + c.market.ask) / 2
    assert m.entry_min is not None and m.entry_max is not None
    distance = max(m.entry_min - mid, mid - m.entry_max, Decimal("0"))
    if distance > c.cfg.safety.max_entry_deviation:
        return (
            Reason.S3,
            f"entrata a {distance} dal prezzo (max {c.cfg.safety.max_entry_deviation})",
        )
    return None


def _s4_stops_level(c: _Ctx) -> Check:
    m = c.msg
    assert m.entry_min is not None and m.entry_max is not None and m.sl is not None
    reference = m.entry_min if m.side is Side.BUY else m.entry_max
    distance = abs(reference - m.sl)
    minimum = c.market.stops_level + c.cfg.safety.stops_safety_margin
    if distance < minimum:
        return Reason.S4, f"SL a {distance} dall'entrata, minimo {minimum}"
    return None


def _s11_duplicate(c: _Ctx) -> Check:
    window = timedelta(seconds=c.cfg.safety.dedup_window_s)
    for prev in c.state.recent_signals:
        if (
            prev.side is c.msg.side
            and prev.entry_min == c.msg.entry_min
            and prev.sl == c.msg.sl
            and c.mctx.received_at_utc - prev.decided_at_utc <= window
        ):
            return Reason.S11, f"doppione del segnale delle {prev.decided_at_utc:%H:%M:%S} UTC"
    return None


def _f2_direction(c: _Ctx) -> Check:
    rule = c.cfg.filters.direction
    if (rule == "buy_only" and c.msg.side is Side.SELL) or (
        rule == "sell_only" and c.msg.side is Side.BUY
    ):
        return Reason.F2, f"direzione {c.msg.side} esclusa ({rule})"
    return None


def _f1_order_type(c: _Ctx) -> Check:
    mode, hint = c.cfg.filters.order_type_mode, c.msg.order_hint
    if hint is OrderHint.LIMIT and mode == "market_only":
        return Reason.F1, "segnale LIMIT ma F1 = market_only"
    if hint is OrderHint.MARKET and mode == "pending_only":
        return Reason.F1, "segnale a mercato ma F1 = pending_only"
    if hint not in (OrderHint.LIMIT, OrderHint.MARKET):
        return Reason.F1, f"tipo di ordine {hint} non gestito"
    return None


def _f3_sl_distance(c: _Ctx) -> Check:
    f, m = c.cfg.filters, c.msg
    assert m.entry_min is not None and m.entry_max is not None and m.sl is not None
    center = (m.entry_min + m.entry_max) / 2
    distance = abs(center - m.sl)
    if f.sl_distance_min is not None and distance < f.sl_distance_min:
        return Reason.F3, f"SL a {distance} < minimo {f.sl_distance_min}"
    if f.sl_distance_max is not None and distance > f.sl_distance_max:
        return Reason.F3, f"SL a {distance} > massimo {f.sl_distance_max}"
    return None


def _f12_keywords(c: _Ctx) -> Check:
    text = c.msg.raw_text.casefold()
    for keyword in c.cfg.filters.exclude_keywords:
        if keyword.casefold() in text:
            return Reason.F12, f"parola esclusa: {keyword!r}"
    return None


def _f9_hours(c: _Ctx) -> Check:
    window = c.cfg.filters.trading_hours_rome
    if window is None:
        return None
    rome_now = c.mctx.received_at_utc.astimezone(ROME).time()
    if not _in_window(rome_now, window):
        return Reason.F9, f"fuori orario ({window.start}-{window.end} Roma)"
    return None


def _f11_limits(c: _Ctx) -> Check:
    f = c.cfg.filters
    if c.state.trades_today >= f.max_trades_per_day:
        return (
            Reason.F11,
            f"già {c.state.trades_today} operazioni oggi (max {f.max_trades_per_day})",
        )
    if c.state.open_positions >= f.max_open_positions:
        return (
            Reason.F11,
            f"già {c.state.open_positions} posizioni aperte (max {f.max_open_positions})",
        )
    return None


def _f8_spread(c: _Ctx) -> Check:
    if c.market.spread > c.cfg.filters.max_spread:
        return Reason.F8, f"spread {c.market.spread} > {c.cfg.filters.max_spread}"
    return None


def _f5_entry(c: _Ctx) -> Check:
    m, mk = c.msg, c.market
    assert m.entry_min is not None and m.entry_max is not None
    if m.order_hint is OrderHint.MARKET:
        check = check_range_entry(
            m.side,
            m.entry_min,
            m.entry_max,
            mk.bid,
            mk.ask,
            c.cfg.filters.range_entry_tolerance,  # type: ignore[arg-type]
        )
        if not check.inside:
            return Reason.F5, check.reason
        c.extra["execution_price"] = check.execution_price
        return None
    # LIMIT: il prezzo deve essere ancora "dalla parte giusta" dell'entrata, altrimenti
    # un BUY LIMIT finirebbe sopra il prezzo (il broker lo rifiuterebbe o lo eseguirebbe subito).
    entry = m.entry_min
    if m.side is Side.BUY and mk.ask <= entry:
        return Reason.F5, f"BUY LIMIT {entry}: ask {mk.ask} già sotto l'entrata"
    if m.side is Side.SELL and mk.bid >= entry:
        return Reason.F5, f"SELL LIMIT {entry}: bid {mk.bid} già sopra l'entrata"
    return None


SAFETY_CHECKS = (
    _s8_edit, _s6_already_processed, _s5_age_and_origin, _s1_complete, _s7_market,
    _s9_risky_windows, _s10_spread_emergency, _s2_coherence, _s3_deviation, _s4_stops_level,
    _s11_duplicate,
)  # fmt: skip
FILTER_CHECKS = (
    _f2_direction, _f1_order_type, _f3_sl_distance, _f12_keywords, _f9_hours, _f11_limits,
    _f8_spread, _f5_entry,
)  # fmt: skip


def _pending_expiry(c: _Ctx) -> datetime:
    minutes = c.cfg.pending.expiry_min
    if c.cfg.pending.cancel_before_rollover:
        until_rollover = _minutes_until(c.market.server_time, c.cfg.safety.rollover_window.start)
        minutes = min(minutes, until_rollover)
    return c.mctx.received_at_utc + timedelta(minutes=minutes)


def decide(
    msg: ClassifiedMessage,
    mctx: MessageContext,
    market: MarketSnapshot,
    state: EngineState,
    cfg: AppConfig,
) -> Decision:
    """Decide cosa fare di un messaggio classificato."""
    base = {
        "msg_id": msg.msg_id,
        "decided_at_utc": mctx.received_at_utc.astimezone(UTC),
        "config_version": cfg.meta.version,
        "bid": market.bid,
        "ask": market.ask,
        "spread": market.spread,
    }

    if msg.category in (Category.NOISE, Category.RESULT_ANNOUNCEMENT):
        return Decision(**base, action=Action.IGNORE, reason=Reason.NOT_A_SIGNAL, details=msg.notes)
    if msg.category is Category.AMBIGUOUS:
        return Decision(**base, action=Action.IGNORE, reason=Reason.AMBIGUOUS, details=msg.notes)
    if msg.category is not Category.NEW_SIGNAL_COMPLETE and mctx.event == "new":
        # Aggiornamenti (CANCEL, UPDATE_SL, ...): gestiti dal trade_manager, non ancora attivo.
        return Decision(
            **base,
            action=Action.IGNORE,
            reason=Reason.AMBIGUOUS,
            details=f"{msg.category}: aggiornamento non ancora gestito, notifica admin",
        )

    c = _Ctx(msg, mctx, market, state, cfg)
    for check in (*SAFETY_CHECKS, *FILTER_CHECKS):
        failed = check(c)
        if failed is not None:
            reason, details = failed
            return Decision(**base, action=Action.REJECT, reason=reason, details=details,
                            side=msg.side)  # fmt: skip

    common = {"side": msg.side, "sl": msg.sl, "tp": c.tp, "tp_index": c.tp_index}
    if msg.order_hint is OrderHint.LIMIT:
        return Decision(
            **base, **common, action=Action.OPEN_PENDING, reason=Reason.OK,
            details="pendente LIMIT approvato", order_type="LIMIT",
            entry_price=msg.entry_min, expiry_utc=_pending_expiry(c),
        )  # fmt: skip
    return Decision(
        **base, **common, action=Action.OPEN_MARKET, reason=Reason.OK,
        details="apertura a mercato approvata", order_type="MARKET",
        entry_price=c.extra["execution_price"],
    )  # fmt: skip
