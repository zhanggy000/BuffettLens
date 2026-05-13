"""Ticker universe helpers for BuffettLens."""

import io
import os
from pathlib import Path
from typing import List, Optional


def _try_wiki_table(url: str, match: Optional[str] = None) -> List[str]:
    """Try to fetch tickers from a Wikipedia table."""
    try:
        import pandas as pd
        import requests

        resp = requests.get(
            url,
            headers={"User-Agent": "Mozilla/5.0 BuffettLens/1.0"},
            timeout=30,
        )
        resp.raise_for_status()
        html = io.StringIO(resp.text)
        tables = pd.read_html(html, match=match) if match else pd.read_html(html)
        for table in tables:
            for col in table.columns:
                col_str = str(col).lower()
                if "ticker" not in col_str and "symbol" not in col_str:
                    continue

                tickers = table[col].astype(str).str.strip().str.upper().tolist()
                tickers = [
                    t.replace(".", "-")
                    for t in tickers
                    if t and t != "NAN" and len(t) <= 8 and t.replace("-", "").replace(".", "").isalpha()
                ]
                tickers = list(dict.fromkeys(tickers))
                if len(tickers) >= 50:
                    return tickers
    except Exception as e:
        print(f"WARN online universe fetch failed ({url}): {e}")
    return []


SP500_FALLBACK = [
    "AAPL", "MSFT", "NVDA", "AMZN", "META", "GOOGL", "GOOG", "BRK-B", "TSLA", "AVGO",
    "JPM", "LLY", "V", "UNH", "XOM", "MA", "JNJ", "PG", "HD", "COST",
    "ABBV", "WMT", "BAC", "NFLX", "KO", "ORCL", "MRK", "CVX", "AMD", "TMO",
    "ADBE", "CRM", "PEP", "ACN", "LIN", "MCD", "ABT", "CSCO", "WFC", "DHR",
    "TMUS", "AXP", "DIS", "GE", "IBM", "INTU", "VZ", "PM", "PFE", "NOW",
    "QCOM", "GS", "CAT", "MS", "TXN", "AMGN", "BKNG", "RTX", "ISRG", "UBER",
    "SPGI", "T", "BLK", "NEE", "LOW", "HON", "BSX", "SYK", "DE", "PGR",
    "TJX", "VRTX", "ELV", "MDT", "AMAT", "PANW", "C", "ETN", "ADP", "ADI",
    "GILD", "CB", "REGN", "MMC", "SCHW", "LRCX", "CI", "BX", "PLD", "FI",
    "MU", "BMY", "KLAC", "SO", "ZTS", "BA", "MO", "DUK", "CMCSA", "ANET",
]

NDX100_FALLBACK = [
    "AAPL", "MSFT", "NVDA", "AMZN", "META", "GOOGL", "GOOG", "AVGO", "TSLA", "COST",
    "NFLX", "ADBE", "PEP", "AMD", "TMUS", "CSCO", "QCOM", "INTU", "TXN", "AMGN",
    "ISRG", "BKNG", "CMCSA", "AMAT", "PANW", "MU", "VRTX", "LRCX", "ADI", "GILD",
    "KLAC", "REGN", "MDLZ", "ADP", "SBUX", "CRWD", "MELI", "CTAS", "PYPL", "ABNB",
    "SNPS", "CDNS", "MAR", "ORLY", "FTNT", "WDAY", "ASML", "CSX", "ROP", "CHTR",
    "PCAR", "MNST", "PAYX", "AEP", "MRVL", "NXPI", "AZN", "ROST", "ODFL", "FAST",
    "KDP", "BKR", "EA", "VRSK", "EXC", "CTSH", "GEHC", "XEL", "KHC", "LULU",
    "CCEP", "CPRT", "IDXX", "DDOG", "TTWO", "ANSS", "DXCM", "ON", "ZS", "FANG",
    "BIIB", "TEAM", "CDW", "WBD", "TTD", "GFS", "MRNA", "ILMN", "WBA", "SIRI",
    "DLTR", "ARM", "MDB", "LIN", "TSCO", "EBAY", "ALGN", "ENPH", "SMCI",
]


REPO_ROOT = Path(__file__).resolve().parents[1]
CSI300_WEIGHT_XLS = Path(os.environ.get(
    "CSI300_WEIGHT_XLS",
    REPO_ROOT / "data" / "000300closeweight.xls",
))


def _find_col(columns, *needles: str) -> str:
    for col in columns:
        col_text = str(col).lower().replace(" ", "")
        if all(needle.lower().replace(" ", "") in col_text for needle in needles):
            return col
    raise ValueError(f"Missing expected CSI 300 column containing: {', '.join(needles)}")


def get_csi300(path: Optional[str] = None) -> List[str]:
    """Load CSI 300 tickers from the official index weight Excel file."""
    xls_path = Path(path) if path else CSI300_WEIGHT_XLS
    if not xls_path.exists() and not path:
        xls_path = Path.home() / "Downloads" / "000300closeweight.xls"
    if not xls_path.exists():
        raise FileNotFoundError(
            f"CSI 300 weight file not found: {xls_path}. "
            "Commit data/000300closeweight.xls, download it to ~/Downloads, or set CSI300_WEIGHT_XLS."
        )

    try:
        import pandas as pd
    except ImportError as exc:
        raise ImportError("pandas is required to read CSI 300 universe files.") from exc

    df = pd.read_excel(xls_path)
    code_col = _find_col(df.columns, "Constituent", "Code")
    exch_col = _find_col(df.columns, "Exchange")
    weight_col = _find_col(df.columns, "weight")

    df = df.sort_values(weight_col, ascending=False).reset_index(drop=True)
    tickers = []
    for _, row in df.iterrows():
        code = str(row[code_col]).strip().split(".")[0].zfill(6)
        exchange = str(row[exch_col])
        suffix = ".SS" if "上海" in exchange or "Shanghai" in exchange else ".SZ"
        tickers.append(f"{code}{suffix}")

    tickers = list(dict.fromkeys(tickers))
    print(f"Loaded CSI 300 from {xls_path}: {len(tickers)} tickers")
    return tickers


def get_sp500() -> List[str]:
    tickers = _try_wiki_table(
        "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies",
        match="Symbol",
    )
    if tickers:
        print(f"Loaded S&P 500 from Wikipedia: {len(tickers)} tickers")
        return tickers

    print(f"WARN using fallback S&P 500 list: {len(SP500_FALLBACK)} tickers")
    return list(dict.fromkeys(SP500_FALLBACK))


def get_ndx100() -> List[str]:
    tickers = _try_wiki_table("https://en.wikipedia.org/wiki/Nasdaq-100", match="Ticker")
    if tickers:
        print(f"Loaded NASDAQ 100 from Wikipedia: {len(tickers)} tickers")
        return tickers

    print(f"WARN using fallback NASDAQ 100 list: {len(NDX100_FALLBACK)} tickers")
    return list(dict.fromkeys(NDX100_FALLBACK))


def get_universe(name: str) -> List[str]:
    name = name.lower().strip()
    if name in ("sp500", "sp_500", "s&p500", "spx"):
        return get_sp500()
    if name in ("ndx", "ndx100", "nasdaq100", "nasdaq_100", "qqq"):
        return get_ndx100()
    if name in ("csi300", "csi_300", "000300"):
        return get_csi300()
    if name in ("all",):
        return sorted(set(get_sp500()) | set(get_ndx100()) | set(get_csi300()))
    raise ValueError(f"Unknown universe: {name}. Choose sp500, ndx100, csi300, or all.")
