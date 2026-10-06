# ruff: noqa: E501  (righe di dati reali, più leggibili su una riga)
"""Messaggi di apertura REALI di WDT MOMENTUM, forniti da Lorenzo il 2026-10-06.

ATTENZIONE: trascritti a mano da screenshot. Possibili differenze col testo vero:
- l'emoji dell'intestazione F-RANGE (riquadro verde con stella) è stata trascritta come ❇️;
- apostrofi (’ o '), trattini (— o -), spazi multipli;
- "%0A" compare letteralmente nel messaggio (probabile a capo codificato dallo strumento
  di pubblicazione del canale).
Vanno sostituiti col testo esatto dell'export JSONL appena disponibile.

Ogni voce: testo + estrazione attesa. Se uno di questi test fallisce, il rilascio è bloccato.
"""

from decimal import Decimal as D

GOLDEN_OPENINGS = [
    {
        "id": "limit_buy_1",
        "text": (
            "⏳ LIMIT ORDER — BUY XAUUSD (GOLD) ⏳\n\n"
            "the market flew through this level like it wasnt even there — now it should "
            "hold the other way. classic break and retest 📚😎\n\n"
            "ENTRY: 4158.16\n\n"
            "SL ❌: 4153.16\n\n"
            "TP1 (valuta il BE)✅: 4160.66\n"
            "TP2 (metti a BE)✅: 4163.16\n"
            "TP3✅: 4168.16\n"
            "TP4✅: 4173.16"
        ),
        "side": "BUY",
        "order_hint": "LIMIT",
        "entry": (D("4158.16"), D("4158.16")),
        "sl": D("4153.16"),
        "tps": [D("4160.66"), D("4163.16"), D("4168.16"), D("4173.16")],
        "tp_open": False,
    },
    {
        "id": "limit_buy_2",
        "text": (
            "⏳ LIMIT ORDER — BUY XAUUSD (GOLD) ⏳\n\n"
            "the market flew through this level like it wasnt even there — now it should "
            "hold the other way. classic break and retest 📚😎\n\n"
            "ENTRY: 4148.32\n\n"
            "SL ❌: 4143.32\n\n"
            "TP1 (valuta il BE)✅: 4150.82\n"
            "TP2 (metti a BE)✅: 4153.32\n"
            "TP3✅: 4158.32\n"
            "TP4✅: 4163.32"
        ),
        "side": "BUY",
        "order_hint": "LIMIT",
        "entry": (D("4148.32"), D("4148.32")),
        "sl": D("4143.32"),
        "tps": [D("4150.82"), D("4153.32"), D("4158.32"), D("4163.32")],
        "tp_open": False,
    },
    {
        "id": "limit_sell_1",
        "text": (
            "⏳ LIMIT ORDER — SELL XAUUSD (GOLD) ⏳\n\n"
            "patience play here — the market owes this level another visit 👈\n\n"
            "ENTRY: 4148.25\n\n"
            "SL ❌: 4153.25\n\n"
            "TP1 (valuta il BE)✅: 4145.75\n"
            "TP2 (metti a BE)✅: 4143.25\n"
            "TP3✅: 4138.25\n"
            "TP4✅: 4133.25"
        ),
        "side": "SELL",
        "order_hint": "LIMIT",
        "entry": (D("4148.25"), D("4148.25")),
        "sl": D("4153.25"),
        "tps": [D("4145.75"), D("4143.25"), D("4138.25"), D("4133.25")],
        "tp_open": False,
    },
]


# Chiusura presente in quasi tutte le aperture (dal video del 2026-10-06).
FOOTER = (
    "❇️ INPULSE XAU | L'impulso per i profitti è appena iniziato, mi raccomando mantieni il "
    "giusto management, non rischiare più del dovuto e ricordati che investire è sempre "
    "pericoloso e bisogna farlo con la testa 🧠 Trade Ideas\n\n"
    "⚠️ Questo è solo a scopo educativo. Non è un consiglio finanziario. Il trading comporta "
    "rischi, opera solo con fondi che puoi permetterti di perdere."
)


def _limit(side: str, entry: str, sl: str, tps: list[str]) -> str:
    return (
        f"⏳ LIMIT ORDER — {side} XAUUSD (GOLD) ⏳\n\n"
        "the market flew through this level like it wasnt even there — now it should hold "
        "the other way. classic break and retest 📚😎\n\n"
        f"ENTRY: {entry}\n\n"
        f"SL ❌: {sl}\n\n"
        f"TP1 (valuta il BE)✅: {tps[0]}\n"
        f"TP2 (metti a BE)✅: {tps[1]}\n"
        f"TP3✅: {tps[2]}\n"
        f"TP4✅: {tps[3]}\n\n"
        f"⏳ This is a {side} LIMIT ORDER — it only fills if price pulls back to the entry. "
        "Place it as a pending order on your broker, or approve it on the ATE within 10 "
        "minutes.\n\n"
        "no chasing, no stress — the order does the work 😌\n\n" + FOOTER
    )


def _range(side: str, a: str, b: str, sl: str, tps: list[str]) -> str:
    tp_lines = [
        f"TP1 (valuta il BE)✅: {tps[0]}",
        f"TP2 (metti a BE)✅: {tps[1]}",
        f"TP3✅: {tps[2]}",
        f"TP4✅: {tps[3]}",
        "TP5✅: OPEN",
    ]
    return (
        f"❇️ {side} XAUUSD (GOLD) ❇️\n\n"
        "PREZZO D'ENTRATA (ricordo che tra questi 2 prezzi puoi fare 2 o 3 slot d'entrate) :"
        f"   %0A ➡️ ENTRY RANGE:: {a} - {b}\n\n"
        f"SL ❌: {sl}\n\n" + "\n".join(tp_lines) + "\n\n" + FOOTER
    )


_RANGES = [
    ("range_sell_1", "SELL", "4138.96", "4139.96", "4147.96", ["4134.36", "4130.96", "4126.71", "4122.46"]),
    ("range_sell_2", "SELL", "4128.05", "4129.05", "4137.05", ["4123.45", "4120.05", "4115.80", "4111.55"]),
    ("range_sell_3", "SELL", "4133.64", "4134.64", "4142.64", ["4129.04", "4125.64", "4121.39", "4117.14"]),
    ("range_buy_1", "BUY", "4159.65", "4160.65", "4155.15", ["4163.15", "4165.15", "4167.65", "4170.15"]),
    ("range_buy_2", "BUY", "4160.16", "4161.16", "4155.66", ["4163.66", "4165.66", "4168.16", "4170.66"]),
    # dal video
    ("range_sell_4", "SELL", "4151.49", "4152.49", "4156.99", ["4148.99", "4146.99", "4144.49", "4141.99"]),
    ("range_sell_5", "SELL", "4145.59", "4146.59", "4153.55", ["4141.61", "4138.63", "4134.90", "4131.17"]),
]  # fmt: skip

_LIMITS = [
    ("limit_sell_2", "SELL", "4151.02", "4156.02", ["4148.52", "4146.02", "4141.02", "4136.02"]),
    ("limit_sell_3", "SELL", "4130.28", "4135.28", ["4127.78", "4125.28", "4120.28", "4115.28"]),
]  # fmt: skip

for _id, _side, _e, _sl, _tps in _LIMITS:
    GOLDEN_OPENINGS.append(
        {
            "id": _id,
            "text": _limit(_side, _e, _sl, _tps),
            "side": _side, "order_hint": "LIMIT",
            "entry": (D(_e), D(_e)), "sl": D(_sl),
            "tps": [D(t) for t in _tps], "tp_open": False,
        }
    )  # fmt: skip

for _id, _side, _a, _b, _sl, _tps in _RANGES:
    GOLDEN_OPENINGS.append(
        {
            "id": _id,
            "text": _range(_side, _a, _b, _sl, _tps),
            "side": _side, "order_hint": "MARKET",
            "entry": (D(_a), D(_b)), "sl": D(_sl),
            "tps": [D(t) for t in _tps], "tp_open": True,
        }
    )  # fmt: skip


# Messaggi REALI che NON sono aperture (dal video del 2026-10-06).
# "future" = categoria che il classificatore dovrà assegnare quando i formati di
# aggiornamento saranno implementati. Oggi il test verifica solo che non diventino segnali.
NON_OPENINGS_REAL = [
    {
        "id": "pre_annuncio",
        "future": "NOISE",
        "text": (
            "❇️ PREPARA IL TUO MT5 per l'operazione che manderemo tra poco %0A il segnale "
            "probabilmente sarà un ➡️ ... 🔸 | SELL XAUUSD ❇️\n\n"
            "Timeframe: 1m\nSto guardando questa zona: 4148.34-4149.34\n\n"
            "Preparing for potential SELL retest setup\n\n" + FOOTER
        ),
    },
    {
        "id": "tp1_hit",
        "future": "RESULT_ANNOUNCEMENT",
        "text": (
            "TP1 (valuta il BE) ✅ HIT\nPrice: 4163.66\n(+30.0 pips)\n\n"
            "First blood to us 🩸😤 TP1 (valuta il BE) done"
        ),
    },
    {
        "id": "tp2_hit_be",
        "future": "MOVE_BE",
        "text": (
            "TP2 (metti a BE) ✅ HIT\nPrice: 4165.66\n(+50.0 pips)\n\n"
            "➡️ Porta lo STOP LOSS al Prezzo d'entrata o in leggero profitto (Break Even)\n\n"
            "TP2 (metti a BE) ✅ this is the comfiest seat in trading 😌"
        ),
    },
    {
        "id": "tp3_hit",
        "future": "RESULT_ANNOUNCEMENT",
        "text": (
            "TP3 ✅ HIT\nPrice: 4168.16\n(+75.0 pips)\n\n"
            "TP3 done — this is the stuff dreams are made of 😍🙌"
        ),
    },
    {
        "id": "trade_complete",
        "future": "CLOSE_FULL",
        "text": "TRADE COMPLETE ✅\nPrice: 4160.66\nClosed at Break Even — TPs banked",
    },
    {
        "id": "sl_hit",
        "future": "RESULT_ANNOUNCEMENT",
        "text": "SL ❌ HIT - Non rientrare aspetta il prossimo.\nPrice: 4156.99\n(-50.0 pips)",
    },
    {
        "id": "limit_cancelled",
        "future": "CANCEL",
        "text": (
            "❌ LIMIT ORDER CANCELLED\n\nno fill on this one — price kept flying and never "
            "revisited the zone. thats the game with limits.. remove it from your broker and "
            "we go again 💜"
        ),
    },
    {
        "id": "limit_filled",
        "future": "RESULT_ANNOUNCEMENT",
        "text": (
            "🎯 LIMIT ORDER FILLED\nPrice: 4130.28\n\nour pending order just got picked up "
            "🛒 we are live from the zone — targets as posted above, lets ride 🔥"
        ),
    },
    {
        "id": "heads_up",
        "future": "AMBIGUOUS",
        "text": (
            "⚠️ HEADS UP — price is approaching this BUY limit level while the SELL Momentum "
            "trade is still running.\n\nwe dont fight ourselves 😅 if you placed this pending "
            "order, think about removing it while the live trade plays out. those on ATE "
            "auto-remove are handled automatically 💜"
        ),
    },
    {
        "id": "risultati_giornalieri",
        "future": "NOISE",
        "text": (
            "RISULTATI GIORNALIERI DI MEMENTUM 😱👈🚀\nMon 05 Oct\n8 IDEE DI TRADING CONDIVISE 🎯\n\n"
            "✅TP1 (valuta il BE): 4 POSITIONS\n✅TP2 (metti a BE): 3 POSITIONS\n"
            "✅TP3: 2 POSITIONS\n✅TP4: 0 POSITIONS\n❌SL: 3 POSITIONS\n\n"
            "🏆NET PERFORMANCE:\n9 WINS / 3 Loss\n\n✅Pips Gains: 502\n❌Pips Lost: 235\n\n"
            "🏆 TOTALE PROFITTO 267 PIPS TODAY!\n\n" + FOOTER
        ),
    },
    {
        "id": "grafico_in_risposta",
        "future": "NOISE",
        "text": (
            "Patience rewarded — XAUUSD finally came to our level 🎣\n"
            "Every dip getting bought quicker than the last 👀⚡\n"
            "We take what the market gives, nothing more 🙏📊"
        ),
    },
    {
        "id": "motivazionale",
        "future": "NOISE",
        "text": "🧠 Green days feel good, disciplined days build careers 💜",
    },
]
