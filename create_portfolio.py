"""Create a simulated portfolio from a BuffettLens report folder."""
from __future__ import annotations

import argparse
import csv
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List


PORTFOLIOS_DIR = Path(__file__).resolve().parent / "portfolios"


def progress(message: str) -> None:
    print(f"[progress] {message}", flush=True)


def safe_part(value: str) -> str:
    value = re.sub(r"[^A-Za-z0-9_.+-]+", "-", value.strip())
    return value.strip("-") or "portfolio"


def read_summary(report_dir: Path) -> List[Dict[str, str]]:
    summaries = sorted(report_dir.glob("*_summary.csv"))
    if not summaries:
        raise FileNotFoundError(f"No *_summary.csv found in {report_dir}")
    summary_path = summaries[0]
    progress(f"reading summary: {summary_path}")
    with summary_path.open("r", newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def to_float(value, default=None):
    try:
        if value in (None, ""):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def select_candidates(rows: List[Dict[str, str]], min_score: float) -> List[Dict[str, str]]:
    selected = []
    for row in rows:
        score = to_float(row.get("total_score"))
        price = to_float(row.get("current_price"))
        ticker = (row.get("ticker") or "").strip().upper()
        if not ticker or score is None or price is None or price <= 0:
            continue
        if score >= min_score:
            selected.append(row)
    selected.sort(key=lambda r: to_float(r.get("total_score"), 0), reverse=True)
    return selected


def weights_for(rows: List[Dict[str, str]], method: str) -> List[float]:
    if not rows:
        return []
    if method == "equal":
        return [1.0 / len(rows)] * len(rows)

    scores = [to_float(r.get("total_score"), 0) for r in rows]
    if method == "score_weighted":
        raw = scores
    elif method == "top_heavy":
        raw = [s * s for s in scores]
    else:
        raise ValueError("method must be equal, score_weighted, or top_heavy")

    total = sum(raw)
    if total <= 0:
        return [1.0 / len(rows)] * len(rows)
    return [v / total for v in raw]


def write_csv(path: Path, rows: List[Dict[str, object]], fields: List[str]) -> None:
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_report(path: Path, portfolio: Dict[str, object], positions: List[Dict[str, object]]) -> None:
    lines = [
        f"# Portfolio {portfolio['name']}",
        "",
        f"- Created: {portfolio['created_at']}",
        f"- Report folder: `{portfolio['source_report_dir']}`",
        f"- Min score: {portfolio['min_score']}",
        f"- Cash: {portfolio['initial_cash']:.2f}",
        f"- Allocation method: {portfolio['method']}",
        f"- Positions: {len(positions)}",
        "",
        "> This is a simulated portfolio for evaluating BuffettLens signals. It is not investment advice.",
        "",
        "| Ticker | Name | Score | Buy Price | Shares | Allocated Cash | Weight |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for p in positions:
        lines.append(
            f"| {p['ticker']} | {p['name']} | {p['score']:.1f} | "
            f"{p['buy_price']:.4f} | {p['shares']:.6f} | "
            f"{p['allocated_cash']:.2f} | {p['weight'] * 100:.2f}% |"
        )
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a simulated portfolio from BuffettLens results.")
    parser.add_argument("--report-dir", required=True, type=Path, help="BuffettLens report folder")
    parser.add_argument("--min-score", type=float, required=True, help="minimum score to include")
    parser.add_argument("--cash", type=float, required=True, help="initial cash amount")
    parser.add_argument(
        "--method",
        choices=["equal", "score_weighted", "top_heavy"],
        default="equal",
        help="allocation method",
    )
    args = parser.parse_args()

    if args.cash <= 0:
        parser.error("--cash must be greater than 0")
    if not args.report_dir.exists():
        parser.error(f"--report-dir does not exist: {args.report_dir}")

    rows = read_summary(args.report_dir)
    candidates = select_candidates(rows, args.min_score)
    if not candidates:
        raise SystemExit(f"No stocks found with total_score >= {args.min_score}")

    progress(f"selected {len(candidates)} stocks with score >= {args.min_score}")
    weights = weights_for(candidates, args.method)
    created_at = datetime.now().strftime("%Y-%m-%d")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    name = (
        f"{timestamp}_{safe_part(args.report_dir.name)}_"
        f"score{int(args.min_score) if args.min_score.is_integer() else args.min_score}_"
        f"cash{int(args.cash) if args.cash.is_integer() else args.cash}_{args.method}"
    )
    out_dir = PORTFOLIOS_DIR / name
    out_dir.mkdir(parents=True, exist_ok=True)

    positions = []
    for row, weight in zip(candidates, weights):
        price = to_float(row.get("current_price"), 0)
        allocated = args.cash * weight
        shares = allocated / price if price > 0 else 0
        positions.append({
            "ticker": (row.get("ticker") or "").strip().upper(),
            "name": row.get("name") or "",
            "score": to_float(row.get("total_score"), 0),
            "buy_price": price,
            "shares": shares,
            "allocated_cash": allocated,
            "weight": weight,
            "buy_date": created_at,
        })

    portfolio = {
        "name": name,
        "created_at": created_at,
        "source_report_dir": str(args.report_dir),
        "min_score": args.min_score,
        "initial_cash": args.cash,
        "method": args.method,
        "benchmarks": ["SPY", "QQQ"],
        "positions": positions,
        "notes": "Simulated fractional-share portfolio. No currency conversion is applied.",
    }

    (out_dir / "portfolio.json").write_text(json.dumps(portfolio, indent=2), encoding="utf-8")
    write_csv(
        out_dir / "positions.csv",
        positions,
        ["ticker", "name", "score", "buy_price", "shares", "allocated_cash", "weight", "buy_date"],
    )
    write_report(out_dir / "report.md", portfolio, positions)

    progress(f"portfolio created: {out_dir}")
    print(f"Positions: {len(positions)}")
    print(f"Initial cash: {args.cash:.2f}")
    print(f"Next: python track_portfolio.py --portfolio {out_dir}")


if __name__ == "__main__":
    main()
