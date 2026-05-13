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


def fetch_fx_series(price_currency: str, base_currency: str, start: date) -> pd.Series:
    """Return daily FX: one unit of price_currency in base_currency."""
    price_currency = price_currency.upper()
    base_currency = base_currency.upper()
    if price_currency == base_currency:
        return pd.Series({start: 1.0}, dtype=float)

    direct = f"{price_currency}{base_currency}=X"
    inverse = f"{base_currency}{price_currency}=X"
    direct_series = fetch_yfinance_series(direct, start)
    if not direct_series.empty:
        progress(f"loaded FX {price_currency}->{base_currency}: {direct}")
        return direct_series
    inverse_series = fetch_yfinance_series(inverse, start)
    if not inverse_series.empty:
        progress(f"loaded FX {price_currency}->{base_currency}: inverse {inverse}")
        return 1.0 / inverse_series
    progress(f"FX history unavailable for {price_currency}->{base_currency}; using portfolio buy FX fallback")
    return pd.Series(dtype=float)


def last_on_or_before(series: pd.Series, day: date, fallback: float) -> float:
    if series.empty:
        return fallback
    eligible = series[series.index <= day]
    if eligible.empty:
        return fallback
    return float(eligible.iloc[-1])


def write_csv(path: Path, rows: List[Dict[str, object]], fields: List[str]) -> None:
    try:
        f = path.open("w", newline="", encoding="utf-8-sig")
    except PermissionError:
        fallback = path.with_name(f"{path.stem}_{datetime.now().strftime('%H%M%S')}{path.suffix}")
        progress(f"{path.name} is locked; writing {fallback.name} instead")
        f = fallback.open("w", newline="", encoding="utf-8-sig")
    with f:
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
    base_currency = str(portfolio.get("base_currency") or "USD").upper()
    positions = list(portfolio["positions"])

    if date.today() <= start:
        progress("portfolio was created today; using buy prices and buy FX for the initial snapshot")
        latest_positions = []
        for pos in positions:
            buy_price = float(pos["buy_price"])
            shares = float(pos["shares"])
            fx_to_base = float(pos.get("buy_fx_to_base") or 1.0)
            cost = float(pos.get("allocated_cash_base") or pos.get("allocated_cash") or 0)
            value = shares * buy_price * fx_to_base
            latest_positions.append({
                "ticker": str(pos["ticker"]),
                "name": pos.get("name", ""),
                "score": float(pos["score"]),
                "buy_price": buy_price,
                "current_price": buy_price,
                "price_currency": str(pos.get("price_currency") or "USD").upper(),
                "base_currency": base_currency,
                "current_fx_to_base": fx_to_base,
                "shares": shares,
                "cost": cost,
                "value": value,
                "return": (value / cost - 1) if cost else None,
            })
        latest_positions.sort(key=lambda r: r["value"], reverse=True)
        return ([{
            "date": start.isoformat(),
            "portfolio_value": round(initial_cash, 2),
            "portfolio_return": 0.0,
            "spy_value": round(initial_cash, 2),
            "spy_return": 0.0,
            "qqq_value": round(initial_cash, 2),
            "qqq_return": 0.0,
            "excess_vs_spy": 0.0,
            "excess_vs_qqq": 0.0,
        }], latest_positions)

    progress(f"rebuilding history from {start} to latest trading day")
    price_series: Dict[str, pd.Series] = {}
    fx_series: Dict[str, pd.Series] = {}
    for pos in positions:
        ticker = str(pos["ticker"])
        price_series[ticker] = fetch_price_series(ticker, start)
        price_currency = str(pos.get("price_currency") or "USD").upper()
        if price_currency not in fx_series:
            fx_series[price_currency] = fetch_fx_series(price_currency, base_currency, start)

    benchmarks = {"SPY": fetch_price_series("SPY", start), "QQQ": fetch_price_series("QQQ", start)}
    if "USD" not in fx_series:
        fx_series["USD"] = fetch_fx_series("USD", base_currency, start)
    all_days = set()
    for series in list(price_series.values()) + list(benchmarks.values()) + list(fx_series.values()):
        all_days.update(series.index)
    all_days = sorted(day for day in all_days if day >= start)
    if start not in all_days:
        all_days.insert(0, start)
    if not all_days:
        all_days = [date.today()]

    benchmark_bases = {}
    for ticker, series in benchmarks.items():
        base = last_on_or_before(series, start, 0) * last_on_or_before(fx_series["USD"], start, 1.0)
        benchmark_bases[ticker] = base if base > 0 else None

    history = []
    latest_prices = {}
    for day in all_days:
        value = 0.0
        for pos in positions:
            ticker = str(pos["ticker"])
            buy_price = float(pos["buy_price"])
            shares = float(pos["shares"])
            price_currency = str(pos.get("price_currency") or "USD").upper()
            buy_fx = float(pos.get("buy_fx_to_base") or 1.0)
            price = buy_price if day <= start else last_on_or_before(
                price_series.get(ticker, pd.Series(dtype=float)), day, buy_price
            )
            fx_to_base = buy_fx if day <= start else last_on_or_before(fx_series.get(price_currency, pd.Series(dtype=float)), day, buy_fx)
            value += shares * price * fx_to_base
            latest_prices[ticker] = price

        portfolio_return = (value / initial_cash) - 1 if initial_cash else None
        usd_fx = last_on_or_before(fx_series["USD"], day, 1.0)
        spy_price = last_on_or_before(benchmarks["SPY"], day, 0) * usd_fx
        qqq_price = last_on_or_before(benchmarks["QQQ"], day, 0) * usd_fx
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
        price_currency = str(pos.get("price_currency") or "USD").upper()
        current_price = latest_prices.get(ticker, float(pos["buy_price"]))
        current_fx = last_on_or_before(fx_series.get(price_currency, pd.Series(dtype=float)), all_days[-1], float(pos.get("buy_fx_to_base") or 1.0))
        value = float(pos["shares"]) * current_price * current_fx
        cost = float(pos.get("allocated_cash_base") or pos.get("allocated_cash") or 0)
        latest_positions.append({
            "ticker": ticker,
            "name": pos.get("name", ""),
            "score": float(pos["score"]),
            "buy_price": float(pos["buy_price"]),
            "current_price": current_price,
            "price_currency": price_currency,
            "base_currency": base_currency,
            "current_fx_to_base": current_fx,
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
        f"- Base currency: {portfolio.get('base_currency') or 'USD'}",
        f"- Initial cash: {float(portfolio['initial_cash']):.2f} {portfolio.get('base_currency') or 'USD'}",
        f"- Portfolio value: {latest['portfolio_value']:.2f} {portfolio.get('base_currency') or 'USD'}",
        f"- Portfolio return: {fmt_pct(latest['portfolio_return'])}",
        f"- SPY return: {fmt_pct(latest['spy_return'])}",
        f"- QQQ return: {fmt_pct(latest['qqq_return'])}",
        f"- Excess vs SPY: {fmt_pct(latest['excess_vs_spy'])}",
        f"- Excess vs QQQ: {fmt_pct(latest['excess_vs_qqq'])}",
        "",
        "> Simulated fractional-share portfolio. Values are converted to the base currency using FX rates from Yahoo Finance.",
        "",
        "| Ticker | Name | Score | CCY | Buy Price | Current Price | FX to Base | Shares | Value | Return |",
        "|---|---|---:|---|---:|---:|---:|---:|---:|---:|",
    ]
    for pos in positions:
        lines.append(
            f"| {pos['ticker']} | {pos['name']} | {pos['score']:.1f} | {pos['price_currency']} | "
            f"{pos['buy_price']:.4f} | {pos['current_price']:.4f} | {pos['current_fx_to_base']:.6f} | "
            f"{pos['shares']:.6f} | {pos['value']:.2f} | {fmt_pct(pos['return'])} |"
        )
    lines.append("")
    try:
        path.write_text("\n".join(lines), encoding="utf-8")
    except PermissionError:
        fallback = path.with_name(f"{path.stem}_{datetime.now().strftime('%H%M%S')}{path.suffix}")
        progress(f"{path.name} is locked; writing {fallback.name} instead")
        fallback.write_text("\n".join(lines), encoding="utf-8")


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
    print(f"Base currency: {portfolio.get('base_currency') or 'USD'}")
    print(f"Value: {latest['portfolio_value']:.2f} {portfolio.get('base_currency') or 'USD'}")
    print(f"Return: {fmt_pct(latest['portfolio_return'])}")
    print(f"SPY: {fmt_pct(latest['spy_return'])}   Excess: {fmt_pct(latest['excess_vs_spy'])}")
    print(f"QQQ: {fmt_pct(latest['qqq_return'])}   Excess: {fmt_pct(latest['excess_vs_qqq'])}")
    print(f"History: {args.portfolio / 'history.csv'}")
    print(f"Latest report: {args.portfolio / 'latest.md'}")


if __name__ == "__main__":
    main()
