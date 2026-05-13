"""Create a simulated portfolio from a BuffettLens report folder."""
from __future__ import annotations

import argparse
import csv
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List

import yfinance as yf


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


def infer_price_currency(ticker: str, row: Dict[str, str]) -> str:
    currency = (row.get("currency") or "").strip().upper()
    if currency:
        return currency
    ticker = ticker.upper()
    if ticker.endswith(".SS") or ticker.endswith(".SZ"):
        return "CNY"
    return "USD"


def fetch_fx_to_base(price_currency: str, base_currency: str) -> float:
    """Return how much one unit of price_currency is worth in base_currency."""
    price_currency = price_currency.upper()
    base_currency = base_currency.upper()
    if price_currency == base_currency:
        return 1.0

    direct = f"{price_currency}{base_currency}=X"
    inverse = f"{base_currency}{price_currency}=X"
    for symbol, invert in ((direct, False), (inverse, True)):
        try:
            hist = yf.Ticker(symbol).history(period="5d")
            if hist is not None and not hist.empty:
                rate = float(hist["Close"].dropna().iloc[-1])
                if rate > 0:
                    fx = (1.0 / rate) if invert else rate
                    progress(f"FX {price_currency}->{base_currency}: {fx:.6f} ({symbol})")
                    return fx
        except Exception:
            pass
    raise RuntimeError(f"Could not fetch FX rate for {price_currency}->{base_currency}")


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
        f"- Cash: {portfolio['initial_cash']:.2f} {portfolio['base_currency']}",
        f"- Allocation method: {portfolio['method']}",
        f"- Positions: {len(positions)}",
        "",
        "> This is a simulated portfolio for evaluating BuffettLens signals. It is not investment advice.",
        "",
        "| Ticker | Name | Score | Price CCY | Buy Price | FX to Base | Shares | Allocated Base | Weight |",
        "|---|---|---:|---|---:|---:|---:|---:|---:|",
    ]
    for p in positions:
        lines.append(
            f"| {p['ticker']} | {p['name']} | {p['score']:.1f} | {p['price_currency']} | "
            f"{p['buy_price']:.4f} | {p['buy_fx_to_base']:.6f} | {p['shares']:.6f} | "
            f"{p['allocated_cash_base']:.2f} | {p['weight'] * 100:.2f}% |"
        )
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a simulated portfolio from BuffettLens results.")
    parser.add_argument("--report-dir", required=True, type=Path, help="BuffettLens report folder")
    parser.add_argument("--min-score", type=float, required=True, help="minimum score to include")
    parser.add_argument("--cash", type=float, required=True, help="initial cash amount")
    parser.add_argument("--currency", default="USD", help="base cash currency, e.g. USD or CNY")
    parser.add_argument(
        "--method",
        choices=["equal", "score_weighted", "top_heavy"],
        default="equal",
        help="allocation method",
    )
    args = parser.parse_args()

    if args.cash <= 0:
        parser.error("--cash must be greater than 0")
    base_currency = args.currency.strip().upper()
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
        f"cash{int(args.cash) if args.cash.is_integer() else args.cash}{base_currency}_{args.method}"
    )
    out_dir = PORTFOLIOS_DIR / name
    out_dir.mkdir(parents=True, exist_ok=True)

    positions = []
    fx_cache: Dict[str, float] = {}
    for row, weight in zip(candidates, weights):
        ticker = (row.get("ticker") or "").strip().upper()
        price = to_float(row.get("current_price"), 0)
        price_currency = infer_price_currency(ticker, row)
        if price_currency not in fx_cache:
            fx_cache[price_currency] = fetch_fx_to_base(price_currency, base_currency)
        fx_to_base = fx_cache[price_currency]
        allocated_base = args.cash * weight
        allocated_price_currency = allocated_base / fx_to_base if fx_to_base > 0 else 0
        shares = allocated_price_currency / price if price > 0 else 0
        positions.append({
            "ticker": ticker,
            "name": row.get("name") or "",
            "score": to_float(row.get("total_score"), 0),
            "buy_price": price,
            "price_currency": price_currency,
            "base_currency": base_currency,
            "buy_fx_to_base": fx_to_base,
            "allocated_cash_base": allocated_base,
            "allocated_cash_price_currency": allocated_price_currency,
            "shares": shares,
            "weight": weight,
            "buy_date": created_at,
        })

    portfolio = {
        "name": name,
        "created_at": created_at,
        "source_report_dir": str(args.report_dir),
        "min_score": args.min_score,
        "initial_cash": args.cash,
        "base_currency": base_currency,
        "method": args.method,
        "benchmarks": ["SPY", "QQQ"],
        "positions": positions,
        "notes": "Simulated fractional-share portfolio. FX is converted to the base currency.",
    }

    (out_dir / "portfolio.json").write_text(json.dumps(portfolio, indent=2), encoding="utf-8")
    write_csv(
        out_dir / "positions.csv",
        positions,
        [
            "ticker", "name", "score", "price_currency", "base_currency", "buy_price",
            "buy_fx_to_base", "shares", "allocated_cash_base",
            "allocated_cash_price_currency", "weight", "buy_date",
        ],
    )
    write_report(out_dir / "report.md", portfolio, positions)

    progress(f"portfolio created: {out_dir}")
    print(f"Positions: {len(positions)}")
    print(f"Initial cash: {args.cash:.2f} {base_currency}")
    print(f"Next: python track_portfolio.py --portfolio {out_dir}")


if __name__ == "__main__":
    main()
