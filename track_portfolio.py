"""Track a simulated BuffettLens portfolio against SPY and QQQ."""
from __future__ import annotations

import argparse
import csv
import json
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd
import yfinance as yf

from screener import fetcher


def progress(message: str) -> None:
    print(f"[progress] {message}", flush=True)


def to_date(value: str) -> date:
    return datetime.strptime(value[:10], "%Y-%m-%d").date()


def fetch_yfinance_series(ticker: str, start: date) -> pd.Series:
    end = date.today() + timedelta(days=1)
    try:
        hist = yf.Ticker(ticker).history(start=start.isoformat(), end=end.isoformat(), auto_adjust=True)
    except Exception:
        hist = pd.DataFrame()
    if hist is None or hist.empty or "Close" not in hist:
        return pd.Series(dtype=float)
    series = hist["Close"].dropna()
    series.index = pd.to_datetime(series.index).date
    return series.astype(float)


def fetch_cached_series(ticker: str, start: date) -> pd.Series:
    raw = fetcher.fetch_stock(ticker)
    if not raw:
        return pd.Series(dtype=float)
    rows = []
    for d, close in raw.get("price_history", []):
        try:
            day = to_date(str(d))
            if day >= start:
                rows.append((day, float(close)))
        except (TypeError, ValueError):
            continue
    if not rows:
        return pd.Series(dtype=float)
    return pd.Series(dict(rows), dtype=float).sort_index()


def fetch_price_series(ticker: str, start: date) -> pd.Series:
    progress(f"fetching price history: {ticker}")
    series = fetch_yfinance_series(ticker, start)
    if not series.empty:
        return series
    progress(f"yfinance empty for {ticker}; trying BuffettLens fetcher")
    return fetch_cached_series(ticker, start)


def last_on_or_before(series: pd.Series, day: date, fallback: float) -> float:
    if series.empty:
        return fallback
    eligible = series[series.index <= day]
    if eligible.empty:
        return fallback
    return float(eligible.iloc[-1])


def write_csv(path: Path, rows: List[Dict[str, object]], fields: List[str]) -> None:
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def fmt_pct(value: Optional[float]) -> str:
    if value is None:
        return "N/A"
    return f"{value * 100:.2f}%"


def build_history(portfolio: Dict[str, object]) -> tuple[List[Dict[str, object]], List[Dict[str, object]]]:
    start = to_date(str(portfolio["created_at"]))
    initial_cash = float(portfolio["initial_cash"])
    positions = list(portfolio["positions"])

    progress(f"rebuilding history from {start} to latest trading day")
    price_series: Dict[str, pd.Series] = {}
    for pos in positions:
        ticker = str(pos["ticker"])
        price_series[ticker] = fetch_price_series(ticker, start)

    benchmarks = {"SPY": fetch_price_series("SPY", start), "QQQ": fetch_price_series("QQQ", start)}
    all_days = set()
    for series in list(price_series.values()) + list(benchmarks.values()):
        all_days.update(series.index)
    all_days = sorted(day for day in all_days if day >= start)
    if start not in all_days:
        all_days.insert(0, start)
    if not all_days:
        all_days = [date.today()]

    benchmark_bases = {}
    for ticker, series in benchmarks.items():
        base = last_on_or_before(series, start, 0)
        benchmark_bases[ticker] = base if base > 0 else None

    history = []
    latest_prices = {}
    for day in all_days:
        value = 0.0
        for pos in positions:
            ticker = str(pos["ticker"])
            buy_price = float(pos["buy_price"])
            shares = float(pos["shares"])
            price = buy_price if day <= start else last_on_or_before(
                price_series.get(ticker, pd.Series(dtype=float)), day, buy_price
            )
            value += shares * price
            latest_prices[ticker] = price

        portfolio_return = (value / initial_cash) - 1 if initial_cash else None
        spy_price = last_on_or_before(benchmarks["SPY"], day, 0)
        qqq_price = last_on_or_before(benchmarks["QQQ"], day, 0)
        spy_return = (spy_price / benchmark_bases["SPY"] - 1) if benchmark_bases["SPY"] else None
        qqq_return = (qqq_price / benchmark_bases["QQQ"] - 1) if benchmark_bases["QQQ"] else None

        history.append({
            "date": day.isoformat(),
            "portfolio_value": round(value, 2),
            "portfolio_return": portfolio_return,
            "spy_value": round(initial_cash * (1 + spy_return), 2) if spy_return is not None else "",
            "spy_return": spy_return,
            "qqq_value": round(initial_cash * (1 + qqq_return), 2) if qqq_return is not None else "",
            "qqq_return": qqq_return,
            "excess_vs_spy": (portfolio_return - spy_return) if portfolio_return is not None and spy_return is not None else None,
            "excess_vs_qqq": (portfolio_return - qqq_return) if portfolio_return is not None and qqq_return is not None else None,
        })

    latest_positions = []
    for pos in positions:
        ticker = str(pos["ticker"])
        current_price = latest_prices.get(ticker, float(pos["buy_price"]))
        value = float(pos["shares"]) * current_price
        cost = float(pos["allocated_cash"])
        latest_positions.append({
            "ticker": ticker,
            "name": pos.get("name", ""),
            "score": float(pos["score"]),
            "buy_price": float(pos["buy_price"]),
            "current_price": current_price,
            "shares": float(pos["shares"]),
            "cost": cost,
            "value": value,
            "return": (value / cost - 1) if cost else None,
        })

    latest_positions.sort(key=lambda r: r["value"], reverse=True)
    return history, latest_positions


def write_latest(path: Path, portfolio: Dict[str, object], latest: Dict[str, object], positions: List[Dict[str, object]]) -> None:
    lines = [
        f"# Latest Portfolio Report: {portfolio['name']}",
        "",
        f"- Date: {latest['date']}",
        f"- Initial cash: {float(portfolio['initial_cash']):.2f}",
        f"- Portfolio value: {latest['portfolio_value']:.2f}",
        f"- Portfolio return: {fmt_pct(latest['portfolio_return'])}",
        f"- SPY return: {fmt_pct(latest['spy_return'])}",
        f"- QQQ return: {fmt_pct(latest['qqq_return'])}",
        f"- Excess vs SPY: {fmt_pct(latest['excess_vs_spy'])}",
        f"- Excess vs QQQ: {fmt_pct(latest['excess_vs_qqq'])}",
        "",
        "> Simulated fractional-share portfolio. No currency conversion is applied.",
        "",
        "| Ticker | Name | Score | Buy Price | Current Price | Shares | Value | Return |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for pos in positions:
        lines.append(
            f"| {pos['ticker']} | {pos['name']} | {pos['score']:.1f} | {pos['buy_price']:.4f} | "
            f"{pos['current_price']:.4f} | {pos['shares']:.6f} | {pos['value']:.2f} | {fmt_pct(pos['return'])} |"
        )
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Track a simulated BuffettLens portfolio.")
    parser.add_argument("--portfolio", required=True, type=Path, help="portfolio folder")
    parser.add_argument(
        "--refresh-history",
        action="store_true",
        help="force full history rebuild; default also backfills missing days",
    )
    args = parser.parse_args()

    portfolio_path = args.portfolio / "portfolio.json"
    if not portfolio_path.exists():
        parser.error(f"portfolio.json not found: {portfolio_path}")

    portfolio = json.loads(portfolio_path.read_text(encoding="utf-8"))
    history, positions = build_history(portfolio)
    if not history:
        raise SystemExit("No price history available.")

    fields = [
        "date", "portfolio_value", "portfolio_return", "spy_value", "spy_return",
        "qqq_value", "qqq_return", "excess_vs_spy", "excess_vs_qqq",
    ]
    write_csv(args.portfolio / "history.csv", history, fields)
    latest = history[-1]
    write_latest(args.portfolio / "latest.md", portfolio, latest, positions)

    print()
    print(f"Portfolio: {portfolio['name']}")
    print(f"Date: {latest['date']}")
    print(f"Value: {latest['portfolio_value']:.2f}")
    print(f"Return: {fmt_pct(latest['portfolio_return'])}")
    print(f"SPY: {fmt_pct(latest['spy_return'])}   Excess: {fmt_pct(latest['excess_vs_spy'])}")
    print(f"QQQ: {fmt_pct(latest['qqq_return'])}   Excess: {fmt_pct(latest['excess_vs_qqq'])}")
    print(f"History: {args.portfolio / 'history.csv'}")
    print(f"Latest report: {args.portfolio / 'latest.md'}")


if __name__ == "__main__":
    main()
