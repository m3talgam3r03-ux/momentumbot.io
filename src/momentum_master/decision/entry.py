"""Regola di entrata per i segnali a mercato con range (F-RANGE). Funzione pura.

Decisione di Lorenzo (2026-10-06, D2): se all'arrivo del segnale il prezzo è FUORI dal
range → il segnale si scarta. Nessun inseguimento, nessun pendente sostitutivo.

Prezzo usato: BUY si compra all'ask, SELL si vende al bid (è il prezzo a cui l'ordine
verrebbe davvero eseguito). La tolleranza (default 0) è configurabile, ma ogni modifica
va rigiocata sullo storico prima di attivarla.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from momentum_master.classifier.models import Side


@dataclass(frozen=True)
class EntryCheck:
    inside: bool
    execution_price: Decimal
    reason: str


def check_range_entry(
    side: Side,
    entry_min: Decimal,
    entry_max: Decimal,
    bid: Decimal,
    ask: Decimal,
    tolerance: Decimal = Decimal("0"),
) -> EntryCheck:
    """Verifica se il prezzo di esecuzione è dentro [entry_min, entry_max] ± tolleranza."""
    if entry_min > entry_max:
        raise ValueError("entry_min > entry_max")
    if tolerance < 0:
        raise ValueError("tolleranza negativa")
    if bid > ask:
        raise ValueError("bid > ask: quotazione non valida")

    price = ask if side is Side.BUY else bid
    low, high = entry_min - tolerance, entry_max + tolerance
    if low <= price <= high:
        return EntryCheck(True, price, f"{side} a {price} dentro il range {low}-{high}")
    where = "sopra" if price > high else "sotto"
    return EntryCheck(False, price, f"{side} a {price} {where} il range {low}-{high}: scartato")
