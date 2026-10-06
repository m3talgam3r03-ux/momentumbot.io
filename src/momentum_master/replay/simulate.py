"""Simulazione dell'esito di un'operazione sulle barre M1 (prezzi BID + spread).

Regole (prudenti, dichiarate):
- l'esito si valuta dalle barre SUCCESSIVE al minuto della decisione;
- BUY esce al BID: SL se low ≤ SL, TP se high ≥ TP;
  SELL esce all'ASK (bid + spread): SL se high + spread ≥ SL, TP se low + spread ≤ TP;
- SL e TP nella stessa barra → conta lo SL;
- pendente BUY LIMIT eseguito se ask ≤ entrata (low + spread ≤ entry), SELL LIMIT se
  bid ≥ entrata (high ≥ entry); nella barra di esecuzione si controlla solo lo SL;
- uscita a SL/TP al prezzo esatto (lo slittamento non è simulato);
- CLOSE/CANCEL del fornitore: si esce all'apertura della prima barra dopo il messaggio;
- pendente non eseguito entro la scadenza, CANCEL o CLOSE → nessuna operazione.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from momentum_master.classifier.models import Side
from momentum_master.replay.prices import MINUTE, PriceSeries


class Outcome(StrEnum):
    TP = "TP"
    SL = "SL"
    CLOSED_BY_PROVIDER = "CLOSED_BY_PROVIDER"
    NOT_FILLED = "NOT_FILLED"
    OPEN_AT_END = "OPEN_AT_END"


@dataclass(frozen=True)
class TradeSpec:
    signal_msg_id: int
    side: Side
    order_type: str  # MARKET | LIMIT
    entry: Decimal
    sl: Decimal
    tp: Decimal
    decided_at: datetime
    expiry: datetime | None = None  # solo LIMIT


@dataclass(frozen=True)
class TradeResult:
    spec: TradeSpec
    outcome: Outcome
    filled_at: datetime | None = None
    exit_at: datetime | None = None
    exit_price: Decimal | None = None

    @property
    def is_closed(self) -> bool:
        return self.outcome in (Outcome.TP, Outcome.SL, Outcome.CLOSED_BY_PROVIDER)

    @property
    def points(self) -> Decimal | None:
        if not self.is_closed or self.exit_price is None:
            return None
        diff = self.exit_price - self.spec.entry
        return diff if self.spec.side is Side.BUY else -diff

    @property
    def r(self) -> Decimal | None:
        """Risultato in R: guadagno ÷ rischio iniziale (distanza entrata-SL)."""
        pts = self.points
        risk = abs(self.spec.entry - self.spec.sl)
        return None if pts is None or risk == 0 else pts / risk

    def active_at(self, t: datetime) -> bool:
        """Esposizione (pendente o posizione) all'istante t, per il limite F11."""
        return self.spec.decided_at <= t and (self.exit_at is None or t < self.exit_at)


def simulate(spec: TradeSpec, series: PriceSeries, cutoff: datetime | None = None) -> TradeResult:
    """Esito di un'operazione. ``cutoff`` = istante di un CANCEL/CLOSE del fornitore."""
    buy = spec.side is Side.BUY
    filled_at: datetime | None = spec.decided_at if spec.order_type == "MARKET" else None

    for bar in series.bars_after(spec.decided_at):
        if cutoff is not None and bar.time_utc >= cutoff:
            if filled_at is None:
                return TradeResult(spec, Outcome.NOT_FILLED, exit_at=cutoff)
            price = bar.open if buy else bar.open + bar.spread
            return TradeResult(spec, Outcome.CLOSED_BY_PROVIDER, filled_at, bar.time_utc, price)

        if filled_at is None:  # pendente in attesa
            if spec.expiry is not None and bar.time_utc >= spec.expiry:
                return TradeResult(spec, Outcome.NOT_FILLED, exit_at=spec.expiry)
            fills = (bar.low + bar.spread <= spec.entry) if buy else (bar.high >= spec.entry)
            if not fills:
                continue
            filled_at = bar.time_utc
            sl_in_fill_bar = bar.low <= spec.sl if buy else bar.high + bar.spread >= spec.sl
            if sl_in_fill_bar:
                return TradeResult(spec, Outcome.SL, filled_at, bar.time_utc + MINUTE, spec.sl)
            continue

        if buy:
            sl_hit, tp_hit = bar.low <= spec.sl, bar.high >= spec.tp
        else:
            sl_hit = bar.high + bar.spread >= spec.sl
            tp_hit = bar.low + bar.spread <= spec.tp
        if sl_hit:  # anche se nella stessa barra è toccato il TP: prudenza
            return TradeResult(spec, Outcome.SL, filled_at, bar.time_utc + MINUTE, spec.sl)
        if tp_hit:
            return TradeResult(spec, Outcome.TP, filled_at, bar.time_utc + MINUTE, spec.tp)

    if filled_at is None:
        return TradeResult(spec, Outcome.NOT_FILLED, exit_at=spec.expiry)
    return TradeResult(spec, Outcome.OPEN_AT_END, filled_at)
