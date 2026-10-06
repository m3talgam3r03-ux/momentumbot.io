"""Modello ClassifiedMessage (vedi <schema_classificazione> nel master prompt).

Scelta deliberata: i prezzi sono ``Decimal`` e non ``float``, per evitare errori di
arrotondamento (4158.16 in float non è esattamente 4158.16). La conversione a float
avverrà solo nell'executor, insieme alla normalizzazione a trade_tick_size.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Category(StrEnum):
    NEW_SIGNAL_COMPLETE = "NEW_SIGNAL_COMPLETE"
    NEW_SIGNAL_INCOMPLETE = "NEW_SIGNAL_INCOMPLETE"
    COMPLETION = "COMPLETION"
    UPDATE_SL = "UPDATE_SL"
    UPDATE_TP = "UPDATE_TP"
    MOVE_BE = "MOVE_BE"
    CLOSE_FULL = "CLOSE_FULL"
    CLOSE_PARTIAL = "CLOSE_PARTIAL"
    CANCEL = "CANCEL"
    RESULT_ANNOUNCEMENT = "RESULT_ANNOUNCEMENT"
    NOISE = "NOISE"
    AMBIGUOUS = "AMBIGUOUS"


class Side(StrEnum):
    BUY = "BUY"
    SELL = "SELL"


class OrderHint(StrEnum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP = "STOP"
    UNSPECIFIED = "UNSPECIFIED"


class Method(StrEnum):
    REGEX = "REGEX"
    LLM = "LLM"


class ClassifiedMessage(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    msg_id: int
    date_utc: datetime
    edited: bool
    raw_text: str
    category: Category
    side: Side | None = None
    order_hint: OrderHint | None = None
    entry_min: Decimal | None = None
    entry_max: Decimal | None = None
    sl: Decimal | None = None
    tps: list[Decimal] = Field(default_factory=list)
    tp_open: bool = False  # il messaggio contiene un TP "OPEN" (senza prezzo)
    ref_msg_id: int | None = None
    close_fraction: float | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    method: Method = Method.REGEX
    notes: str = ""

    @model_validator(mode="after")
    def _signal_fields_consistent(self) -> ClassifiedMessage:
        if self.category is Category.NEW_SIGNAL_COMPLETE:
            missing = [
                name
                for name, value in (
                    ("side", self.side),
                    ("order_hint", self.order_hint),
                    ("entry_min", self.entry_min),
                    ("entry_max", self.entry_max),
                    ("sl", self.sl),
                )
                if value is None
            ]
            if missing or not self.tps:
                raise ValueError(f"NEW_SIGNAL_COMPLETE senza: {missing or ['tps']}")
            if self.entry_min > self.entry_max:  # type: ignore[operator]
                raise ValueError("entry_min > entry_max")
        return self
