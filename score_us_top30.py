"""Fetch the 30 largest US-listed stocks, refresh data, and score them.

This script intentionally uses the project's existing BuffettLens pipeline:
`screener.fetcher.fetch_stock(..., force_refresh=True)` -> metrics -> scorer.
"""

from __future__ import annotations

import html
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))

from screener import fetcher, metrics as M, scorer as S

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


SOURCE_URL = "https://stockanalysis.com/list/biggest-companies/"


@dataclass(frozen=True)
class RankedStock:
    rank: int
    symbol: str
    yf_symbol: str
    name: str
    market_cap: float


def _parse_market_cap(value: str) -> float:
    text = value.replace(",", "").strip().upper()
    if not text:
        return 0.0
    unit = text[-1]
    number = float(text[:-1]) if unit in {"T", "B", "M"} else float(text)
    multiplier = {"T": 1e12, "B": 1e9, "M": 1e6}.get(unit, 1.0)
    return number * multiplier


def fetch_top_us_listed(limit: int = 30) -> list[RankedStock]:
    """Fetch the largest US-listed stocks by market cap from StockAnalysis."""
    resp = requests.get(
        SOURCE_URL,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
            )
        },
        timeout=30,
    )
    resp.raise_for_status()

    pattern = re.compile(
        r"<tr[^>]*>.*?"
        r"<td[^>]*>\s*(?P<rank>\d+)\s*</td>.*?"
        r'<td[^>]*class="sym[^"]*"[^>]*>.*?<a[^>]*>(?P<symbol>[^<]+)</a>.*?</td>.*?'
        r'<td[^>]*class="slw[^"]*"[^>]*>(?P<name>.*?)</td>.*?'
        r"<td[^>]*>\s*(?P<market_cap>[\d.,]+[TBM])\s*</td>",
        re.IGNORECASE | re.DOTALL,
    )

    stocks: list[RankedStock] = []
    for match in pattern.finditer(resp.text):
        rank = int(match.group("rank"))
        symbol = html.unescape(match.group("symbol")).strip()
        name = re.sub(r"<.*?>", "", match.group("name"))
        name = html.unescape(name).strip()
        market_cap = _parse_market_cap(match.group("market_cap"))
        yf_symbol = symbol.replace(".", "-")
        stocks.append(RankedStock(rank, symbol, yf_symbol, name, market_cap))
        if len(stocks) >= limit:
            break

    if len(stocks) < limit:
        raise RuntimeError(f"Only parsed {len(stocks)} stocks from {SOURCE_URL}")
    return stocks


def _fmt_number(value: float | None, digits: int = 1) -> str:
    if value is None:
        return "NA"
    return f"{value:.{digits}f}"


def _fmt_pct(value: float | None) -> str:
    if value is None:
        return "NA"
    return f"{value * 100:.1f}%"


def score_stocks(stocks: Iterable[RankedStock]) -> list[dict]:
    treasury = fetcher.get_10y_treasury_yield()
    print(f"\nUS 10Y Treasury used: {treasury:.2f}%")
    print("\nRefreshing yfinance data through project fetcher...")

    rows: list[dict] = []
    stocks = list(stocks)
    for i, stock in enumerate(stocks, 1):
        print(f"  [{i:02d}/{len(stocks)}] {stock.yf_symbol:<6} {stock.name[:42]:<42}", end=" ", flush=True)
        try:
            raw = fetcher.fetch_stock(stock.yf_symbol, force_refresh=True)
            if raw is None:
                print("FETCH FAIL")
                continue

            metrics = M.compute_metrics(raw, treasury_10y=treasury)
            score = S.score(metrics)
            passed, reasons = S.hard_gates(metrics)
            refreshed_market_cap = metrics.get("market_cap")
            market_cap = refreshed_market_cap or stock.market_cap
            row = {
                "rank": stock.rank,
                "symbol": stock.symbol,
                "yf_symbol": stock.yf_symbol,
                "name": metrics.get("name") or stock.name,
                "market_cap": market_cap,
                "source_market_cap": stock.market_cap,
                "market_cap_source": "project_fetcher" if refreshed_market_cap else "ranking_source",
                "total_score": score["total"],
                "passed": passed,
                "fail_reasons": "; ".join(reasons),
                "pe_ttm": metrics.get("pe_ttm"),
                "pe_forward": metrics.get("pe_forward"),
                "roe_avg": metrics.get("roe_avg"),
                "categories": [c["score"] for c in score["categories"]],
            }
            rows.append(row)
            print(f"{score['total']:5.1f}")
        except Exception as exc:
            print(f"ERROR {type(exc).__name__}: {str(exc)[:120]}")
        time.sleep(0.2)

    return rows


def print_qualified(rows: list[dict]) -> None:
    qualified = [r for r in rows if r["total_score"] >= 60]
    qualified.sort(key=lambda r: r["market_cap"] or 0, reverse=True)

    print("\n" + "=" * 112)
    print(f"US-listed market-cap Top 30 with BuffettLens score >= 60: {len(qualified)}")
    print("=" * 112)
    print(
        f"{'#':>2} {'Rank':>4} {'Ticker':<7} {'Name':<38} {'MktCap($B)':>11} "
        f"{'Score':>6} {'PE':>7} {'FwdPE':>7} {'ROE':>8}  ABCDEF"
    )
    print("-" * 112)
    for i, row in enumerate(qualified, 1):
        cats = "/".join(f"{x:.0f}" for x in row["categories"])
        print(
            f"{i:>2} {row['rank']:>4} {row['yf_symbol']:<7} {row['name'][:38]:<38} "
            f"{(row['market_cap'] or 0) / 1e9:>11.0f} {row['total_score']:>6.1f} "
            f"{_fmt_number(row['pe_ttm']):>7} {_fmt_number(row['pe_forward']):>7} "
            f"{_fmt_pct(row['roe_avg']):>8}  {cats}"
        )


def main() -> None:
    print(f"Fetching Top 30 US-listed stock candidates by market cap from {SOURCE_URL}")
    top30 = fetch_top_us_listed(30)
    print("\nCandidate list from ranking source; final table uses refreshed project market_cap:")
    for stock in top30:
        print(f"  {stock.rank:>2}. {stock.yf_symbol:<6} {stock.name:<48} ${stock.market_cap / 1e9:,.0f}B")

    rows = score_stocks(top30)
    print_qualified(rows)


if __name__ == "__main__":
    main()
