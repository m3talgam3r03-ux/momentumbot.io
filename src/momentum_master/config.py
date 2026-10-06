"""Configurazione di MOMENTUM MASTER: modello pydantic + caricamento da YAML.

Regole (master prompt, <config> e <decisioni_fisse>):
- config non valido → il bot NON parte (ogni errore viene elencato);
- chiavi sconosciute rifiutate: un errore di battitura non diventa un default silenzioso;
- nessun segreto nel config: api_id, api_hash, sessione, login MT5, password e token
  stanno solo nel .env;
- senza filtri confermati si resta in PAPER: DEMO e LIVE vengono rifiutati;
- i dati che dipendono da FPG (simbolo, fuso orario del server) possono restare vuoti
  solo in PAPER.

Unità: tutti i prezzi e le distanze sono in PUNTI di prezzo (1 punto = 1,00 sull'oro).
Mai in pips: per WDT MOMENTUM 1 pip = 0,10, e la conversione è una fonte di errori.
"""

from __future__ import annotations

from datetime import date, time
from decimal import Decimal
from enum import StrEnum
from pathlib import Path
from typing import Annotated, Any, Literal

import yaml
from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    ValidationError,
    model_validator,
)

from momentum_master.decision.targets import TargetsConfig


def _require_quoted_time(value: Any) -> Any:
    """YAML legge 23:50 senza virgolette come il numero 1430 (base 60), che pydantic
    trasformerebbe in silenzio in 00:23:50. Si accettano solo stringhe "HH:MM"."""
    if isinstance(value, time):
        return value
    if not isinstance(value, str):
        raise ValueError(f'orario da scrivere tra virgolette, es. "23:50" (letto: {value!r})')
    return value


ClockTime = Annotated[time, BeforeValidator(_require_quoted_time)]


class Mode(StrEnum):
    PAPER = "paper"
    DEMO = "demo"
    LIVE = "live"


class _Strict(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class ConfigMeta(_Strict):
    version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    date: date
    note: str = ""


class TelegramConfig(_Strict):
    group_id: int | None = None
    # Mittenti autorizzati a pubblicare segnali (D1). None = nessun filtro: ammesso SOLO
    # in PAPER finché l'export non rivela l'id dell'account MOMENTUM.
    channel_poster_ids: list[int] | None = None
    admin_ids: list[int] = Field(default_factory=list)
    admin_chat_id: int | None = None
    followers_group_id: int | None = None


class Mt5Config(_Strict):
    terminal_path: str | None = None
    server: str | None = None
    symbol: str | None = None  # da symbol_info sul conto FPG (es. XAUUSD-e)
    magic: int = Field(default=20261006, ge=1)
    deviation_points: int = Field(default=20, ge=0, le=500)  # in "point" MT5 (unità del broker)
    # Scarto ora server − UTC in ore. None = da misurare all'avvio dall'ultimo tick.
    server_utc_offset_hours: int | None = Field(default=None, ge=-12, le=14)


class TimeWindow(_Strict):
    """Finestra in ora del SERVER MT5."""

    start: ClockTime
    end: ClockTime


class SafetyConfig(_Strict):
    """Regole S1-S11: sempre attive, non disattivabili. Qui solo le soglie."""

    max_entry_deviation: Decimal = Field(default=Decimal("15"), gt=0)  # S3
    stops_safety_margin: Decimal = Field(default=Decimal("0.50"), ge=0)  # S4
    max_signal_age_s: int = Field(default=30, ge=1, le=600)  # S5
    rollover_window: TimeWindow = TimeWindow(start=time(23, 50), end=time(0, 15))  # S9
    friday_close_block_min: int = Field(default=30, ge=0, le=240)  # S9
    week_open_block_min: int = Field(default=30, ge=0, le=240)  # S9
    spread_emergency: Decimal = Field(default=Decimal("1.50"), gt=0)  # S10
    dedup_window_s: int = Field(default=600, ge=1, le=86_400)  # S11


class FiltersConfig(_Strict):
    """Filtri F1-F13 di Lorenzo. Finché ``confirmed`` è False il bot resta in PAPER."""

    confirmed: bool = False
    confirmed_on: date | None = None
    order_type_mode: Literal["market_only", "pending_only", "both"] = "both"  # F1
    direction: Literal["both", "buy_only", "sell_only"] = "both"  # F2
    sl_distance_min: Decimal | None = None  # F3
    sl_distance_max: Decimal | None = None  # F3
    # F4 (R:R minimo) NON usato: decisione di Lorenzo del 2026-10-06.
    range_entry_tolerance: Decimal = Field(default=Decimal("0"), ge=0)  # F5 (D2: fuori → scarto)
    max_wait_completion_min: int = Field(default=0, ge=0)  # F7 (WDT pubblica segnali completi)
    max_spread: Decimal = Field(default=Decimal("0.50"), gt=0)  # F8 (IPOTESI, da tarare)
    trading_hours_rome: TimeWindow | None = None  # F9 (None = sempre, salvo S9)
    news_blackout_min: int | None = None  # F10 (fonte da definire: disattivo)
    max_trades_per_day: int = Field(default=10, ge=1)  # F11
    max_open_positions: int = Field(default=2, ge=1)  # F11
    exclude_keywords: list[str] = Field(default_factory=list)  # F12

    @model_validator(mode="after")
    def _check(self) -> FiltersConfig:
        if self.confirmed and self.confirmed_on is None:
            raise ValueError("filters.confirmed = true richiede filters.confirmed_on (data)")
        if (
            self.sl_distance_min is not None
            and self.sl_distance_max is not None
            and self.sl_distance_min > self.sl_distance_max
        ):
            raise ValueError("filters.sl_distance_min > sl_distance_max")
        return self


class PendingConfig(_Strict):
    """Ordini pendenti (F-LIMIT). D3: proposta 90 min, in attesa di conferma."""

    expiry_min: int = Field(default=90, ge=1, le=24 * 60)
    cancel_before_rollover: bool = True
    allow_over_weekend: bool = False
    # D4: messaggio HEADS UP → solo notifica, cancellazione manuale.
    heads_up_policy: Literal["notify_only"] = "notify_only"


class SizingConfig(_Strict):
    lot_mode: Literal["fixed", "risk_pct"] = "fixed"
    master_lot: Decimal = Field(default=Decimal("0.01"), gt=0)
    risk_pct: Decimal | None = Field(default=None, gt=0, le=5)
    max_lot: Decimal = Field(default=Decimal("1.00"), gt=0)
    max_risk_pct: Decimal = Field(default=Decimal("2"), gt=0, le=10)

    @model_validator(mode="after")
    def _check(self) -> SizingConfig:
        if self.lot_mode == "risk_pct" and self.risk_pct is None:
            raise ValueError("sizing.lot_mode = risk_pct richiede sizing.risk_pct")
        if self.master_lot > self.max_lot:
            raise ValueError("sizing.master_lot > sizing.max_lot")
        return self


class TradeManagerConfig(_Strict):
    close_partial_enabled: bool = False  # finché FPG non conferma la replica delle parziali
    reconcile_interval_min: int = Field(default=5, ge=1, le=60)


class KillSwitchConfig(_Strict):
    daily_loss_pct: Decimal = Field(default=Decimal("3"), gt=0, le=50)
    max_consecutive_losses: int = Field(default=4, ge=1)
    executor_errors_max: int = Field(default=3, ge=1)
    executor_errors_window_min: int = Field(default=10, ge=1)
    disconnect_max_s: int = Field(default=30, ge=5)
    channel_silence_max_h: int = Field(default=24, ge=1)
    ambiguous_spike_per_hour: int = Field(default=5, ge=1)


class NotificationsConfig(_Strict):
    heartbeat_min: int = Field(default=15, ge=1)
    daily_report_rome: ClockTime = time(23, 0)
    language: Literal["it"] = "it"


class AppConfig(_Strict):
    meta: ConfigMeta
    mode: Mode = Mode.PAPER
    telegram: TelegramConfig = TelegramConfig()
    mt5: Mt5Config = Mt5Config()
    safety: SafetyConfig = SafetyConfig()
    filters: FiltersConfig = FiltersConfig()
    targets: TargetsConfig = TargetsConfig()
    pending: PendingConfig = PendingConfig()
    sizing: SizingConfig = SizingConfig()
    trade_manager: TradeManagerConfig = TradeManagerConfig()
    kill_switch: KillSwitchConfig = KillSwitchConfig()
    notifications: NotificationsConfig = NotificationsConfig()

    @model_validator(mode="after")
    def _mode_requirements(self) -> AppConfig:
        if self.mode is Mode.PAPER:
            return self
        missing: list[str] = []
        if not self.filters.confirmed:
            missing.append("filters.confirmed (i filtri di Lorenzo non sono confermati)")
        if not self.telegram.channel_poster_ids:
            missing.append("telegram.channel_poster_ids (mittenti autorizzati)")
        for name, value in (
            ("telegram.group_id", self.telegram.group_id),
            ("telegram.admin_chat_id", self.telegram.admin_chat_id),
            ("mt5.symbol", self.mt5.symbol),
            ("mt5.server", self.mt5.server),
            ("mt5.terminal_path", self.mt5.terminal_path),
        ):
            if value is None:
                missing.append(name)
        if not self.telegram.admin_ids:
            missing.append("telegram.admin_ids")
        if missing:
            raise ValueError(
                f"mode = {self.mode.value} non consentito, mancano: " + "; ".join(missing)
            )
        return self


class ConfigError(Exception):
    """Config non valido: il messaggio elenca tutti i problemi in italiano."""


def _format_errors(exc: ValidationError) -> str:
    lines = []
    for err in exc.errors():
        where = ".".join(str(p) for p in err["loc"]) or "(radice)"
        lines.append(f"- {where}: {err['msg']}")
    return "\n".join(lines)


def parse_config(data: Any) -> AppConfig:
    if not isinstance(data, dict):
        raise ConfigError("il config deve essere una mappa YAML (chiave: valore)")
    try:
        return AppConfig.model_validate(data)
    except ValidationError as exc:
        raise ConfigError("Config non valido, il bot non parte:\n" + _format_errors(exc)) from exc


def load_config(path: Path) -> AppConfig:
    """Carica e valida il config. Solleva ``ConfigError`` se qualcosa non va."""
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ConfigError(f"file di config non trovato: {path}") from exc
    except yaml.YAMLError as exc:
        raise ConfigError(f"YAML non valido in {path}: {exc}") from exc
    return parse_config(data)


def main(argv: list[str] | None = None) -> int:
    """Uso: python -m momentum_master.config config/config.yaml"""
    import sys

    args = sys.argv[1:] if argv is None else argv
    path = Path(args[0]) if args else Path("config/config.yaml")
    try:
        cfg = load_config(path)
    except ConfigError as exc:
        print(exc)
        return 1
    print(
        f"Config OK: versione {cfg.meta.version} del {cfg.meta.date}, modalità {cfg.mode.value}, "
        f"filtri {'CONFERMATI' if cfg.filters.confirmed else 'NON confermati (solo PAPER)'}, "
        f"TP{cfg.targets.tp_index}, pendenti {cfg.pending.expiry_min} min."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
