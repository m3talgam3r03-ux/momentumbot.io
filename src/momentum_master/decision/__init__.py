"""Motore decisionale (funzioni pure). Per ora: regola di entrata sul range e scelta dei TP."""

from momentum_master.decision.entry import EntryCheck, check_range_entry
from momentum_master.decision.targets import (
    TakeProfitChoice,
    TargetsConfig,
    break_even_price,
    select_take_profit,
    should_move_to_break_even,
)

__all__ = [
    "EntryCheck",
    "TakeProfitChoice",
    "TargetsConfig",
    "break_even_price",
    "check_range_entry",
    "select_take_profit",
    "should_move_to_break_even",
]
