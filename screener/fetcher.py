"""Data fetching and SQLite caching for BuffettLens."""

import json
import sqlite3
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Optional

import yfinance as yf

CACHE_DIR = Path(__file__).resolve().parent / "cache"
CACHE_DIR.mkdir(exist_ok=True)
CACHE_DB = CACHE_DIR / "data.db"
CACHE_TTL_HOURS = 24


def _init_db() -> None:
    conn = sqlite3.connect(CACHE_DB)
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS stock_cache (
                ticker TEXT PRIMARY KEY,
                data TEXT NOT NULL,
                fetched_at TEXT NOT NULL
            )
            """
        )
        conn.commit()
    finally:
        conn.close()


_init_db()


def _cache_get(ticker: str, max_age_hours: int = CACHE_TTL_HOURS) -> Optional[Dict[str, Any]]:
    conn = sqlite3.connect(CACHE_DB)
    try:
        row = conn.execute(
            "SELECT data, fetched_at FROM stock_cache WHERE ticker = ?",
            (ticker,),
        ).fetchone()
        if not row:
            return None

        data_str, fetched_at = row
        try:
            ts = datetime.fromisoformat(fetched_at)
        except ValueError:
            return None

        if datetime.now() - ts > timedelta(hours=max_age_hours):
            return None
        return json.loads(data_str)
    finally:
        conn.close()


def _cache_set(ticker: str, data: Dict[str, Any]) -> None:
    conn = sqlite3.connect(CACHE_DB)
    try:
        conn.execute(
            "INSERT OR REPLACE INTO stock_cache(ticker, data, fetched_at) VALUES(?,?,?)",
            (ticker, json.dumps(data, default=str), datetime.now().isoformat()),
        )
        conn.commit()
    finally:
        conn.close()


def _df_to_dict(df) -> Dict[str, Dict[str, float]]:
    """Convert a yfinance statement DataFrame to {date: {row_name: value}}."""
    if df is None or df.empty:
        return {}

    out: Dict[str, Dict[str, float]] = {}
    for col in df.columns:
        col_key = str(col.date()) if hasattr(col, "date") else str(col)
        col_data: Dict[str, float] = {}
        for idx in df.index:
            val = df.loc[idx, col]
            try:
                if val is None or (isinstance(val, float) and val != val):
                    continue
                col_data[str(idx)] = float(val)
            except (TypeError, ValueError):
                continue
        out[col_key] = col_data
    return out


def _series_to_list(series) -> list:
    """Convert a price Series to [(date_str, close), ...]."""
    if series is None or series.empty:
        return []

    out = []
    for idx, val in series.items():
        try:
            if val is None or (isinstance(val, float) and val != val):
                continue
            date_str = str(idx.date()) if hasattr(idx, "date") else str(idx)
            out.append((date_str, float(val)))
        except (TypeError, ValueError):
            continue
    return out


def _news_to_list(news) -> list:
    """Keep a compact, JSON-safe subset of yfinance news items."""
    if not news:
        return []

    out = []
    for item in news[:10]:
        if not isinstance(item, dict):
            continue
        content = item.get("content") if isinstance(item.get("content"), dict) else {}
        title = item.get("title") or content.get("title")
        publisher = item.get("publisher") or content.get("provider", {}).get("displayName")
        link = item.get("link") or content.get("canonicalUrl", {}).get("url")
        published = item.get("providerPublishTime") or content.get("pubDate")
        if title:
            out.append({
                "title": str(title),
                "publisher": str(publisher) if publisher else "",
                "link": str(link) if link else "",
                "published": str(published) if published else "",
            })
    return out


def fetch_stock(ticker: str, force_refresh: bool = False) -> Optional[Dict[str, Any]]:
    """Fetch one stock's profile, statements, and price history."""
    if not force_refresh:
        cached = _cache_get(ticker)
        if cached is not None and len(cached.get("price_history", [])) >= 500 and "news" in cached:
            return cached

    last_error = None
    for attempt in range(1, 4):
        try:
            tk = yf.Ticker(ticker)
            info = tk.info or {}

            if not info.get("marketCap") and not info.get("totalRevenue"):
                return None

            data = {
                "ticker": ticker,
                "info": {
                    k: (v if isinstance(v, (int, float, str, bool, type(None))) else str(v))
                    for k, v in info.items()
                },
                "financials": _df_to_dict(tk.financials),
                "balance_sheet": _df_to_dict(tk.balance_sheet),
                "cashflow": _df_to_dict(tk.cashflow),
                "quarterly_financials": _df_to_dict(tk.quarterly_financials),
            }

            try:
                hist = tk.history(period="5y", auto_adjust=True)
                data["price_history"] = _series_to_list(hist["Close"]) if not hist.empty else []
            except Exception:
                data["price_history"] = []

            try:
                data["news"] = _news_to_list(tk.news)
            except Exception:
                data["news"] = []

            _cache_set(ticker, data)
            return data

        except Exception as e:
            last_error = e
            msg = str(e)
            if "Quote not found" in msg or "404" in msg:
                break
            if attempt < 3:
                time.sleep(1.5 * attempt)

    print(f"  WARN fetch failed {ticker}: {last_error}")
    return None


def fetch_batch(tickers: list, delay: float = 2.0, force_refresh: bool = False) -> Dict[str, Optional[Dict]]:
    """Fetch multiple tickers with a delay between cache misses."""
    results: Dict[str, Optional[Dict]] = {}
    total = len(tickers)
    for i, ticker in enumerate(tickers, 1):
        cached = None if force_refresh else _cache_get(ticker)
        if cached is not None:
            results[ticker] = cached
            print(f"[{i}/{total}] {ticker}: cache hit")
            continue

        print(f"[{i}/{total}] {ticker}: fetching...", end="", flush=True)
        data = fetch_stock(ticker, force_refresh=force_refresh)
        results[ticker] = data
        print(" OK" if data else " FAIL")

        if i < total:
            time.sleep(delay)
    return results


def get_10y_treasury_yield() -> float:
    """Fetch 10-year Treasury yield; return 4.0% as a conservative fallback."""
    try:
        cached = _cache_get("__TNX__", max_age_hours=12)
        if cached and "value" in cached:
            return cached["value"]

        tk = yf.Ticker("^TNX")
        hist = tk.history(period="5d")
        if not hist.empty:
            value = float(hist["Close"].iloc[-1])
            _cache_set("__TNX__", {"value": value})
            return value
    except Exception:
        pass
    return 4.0
