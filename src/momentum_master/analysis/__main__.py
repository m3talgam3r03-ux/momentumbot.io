"""Uso: python -m momentum_master.analysis --file data/storico.jsonl --out data/esplorazione.md"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from momentum_master.analysis.explore import build_report
from momentum_master.exporter.export import read_jsonl


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m momentum_master.analysis")
    parser.add_argument("--file", required=True, help="storico JSONL esportato")
    parser.add_argument("--out", required=True, help="rapporto Markdown di destinazione")
    parser.add_argument("--top-shapes", type=int, default=40)
    args = parser.parse_args(argv)

    report = build_report(read_jsonl(Path(args.file)), top_shapes=args.top_shapes)
    Path(args.out).write_text(report, encoding="utf-8")
    print(f"Rapporto scritto in {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
