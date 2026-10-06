"""Scelta del take profit e calcolo del pareggio (BE). Funzioni pure.

Decisione di Lorenzo (2026-10-06, D5): oggi si usa TP1 per tutti e il BE NON si applica.
Le funzioni restano pronte per poter cambiare in futuro SOLO da configurazione
(``tp_index``, ``be_after_tp``), con una nuova versione del config: mai modifiche silenziose.

Cosa cambia per i follower se un giorno si cambia:
- ``tp_index`` > 1: operazioni più lunghe, TP più lontano, meno operazioni chiuse in profitto.
- ``be_after_tp``: lo SL del master viene spostato; FPG deve replicare le modifiche di SL
  (punto ancora aperto con FPG).
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from momentum_master.classifier.models import Side


class TargetsConfig(BaseModel):
    """Sezione di config per take profit e pareggio. Modificabile solo dall'admin."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    tp_index: int = Field(default=1, ge=1, le=5)
    # Se il segnale non ha il TP richiesto (es. tp_index=4 ma il messaggio ne ha 3):
    # "reject" = non si apre; "use_last_available" = si usa l'ultimo TP con prezzo.
    on_missing_tp: Literal["reject", "use_last_available"] = "reject"
    # Dopo quale TP del FORNITORE spostare lo SL a pareggio. None = mai (decisione attuale).
    be_after_tp: int | None = Field(default=None, ge=1, le=5)
    # Margine oltre il prezzo di apertura ("in leggero profitto"), in punti di prezzo.
    be_offset: Decimal = Field(default=Decimal("0"), ge=0)


@dataclass(frozen=True)
class TakeProfitChoice:
    price: Decimal | None
    index_used: int | None
    reason: str

    @property
    def ok(self) -> bool:
        return self.price is not None


def select_take_profit(tps: list[Decimal], cfg: TargetsConfig) -> TakeProfitChoice:
    """Sceglie il TP da mettere sull'ordine del master. ``tps`` = solo TP con prezzo, in ordine."""
    if not tps:
        return TakeProfitChoice(None, None, "nessun TP con prezzo nel segnale")
    if cfg.tp_index <= len(tps):
        return TakeProfitChoice(tps[cfg.tp_index - 1], cfg.tp_index, f"TP{cfg.tp_index}")
    if cfg.on_missing_tp == "use_last_available":
        return TakeProfitChoice(
            tps[-1], len(tps), f"TP{cfg.tp_index} assente: uso TP{len(tps)} (ultimo disponibile)"
        )
    return TakeProfitChoice(None, None, f"TP{cfg.tp_index} assente nel segnale ({len(tps)} TP)")


def should_move_to_break_even(provider_tp_hit: int, cfg: TargetsConfig) -> bool:
    """True se il TP colpito dal fornitore fa scattare lo spostamento a pareggio."""
    return cfg.be_after_tp is not None and provider_tp_hit >= cfg.be_after_tp


def break_even_price(side: Side, open_price: Decimal, cfg: TargetsConfig) -> Decimal:
    """Nuovo SL a pareggio, calcolato sul NOSTRO prezzo di apertura (non sul centro del range
    del fornitore): pareggio vero per il master, più l'eventuale margine in profitto."""
    return open_price + cfg.be_offset if side is Side.BUY else open_price - cfg.be_offset
