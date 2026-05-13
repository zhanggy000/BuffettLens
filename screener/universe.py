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


CSI300_FALLBACK = [
    "300750.SZ", "300308.SZ", "600519.SS", "601318.SS", "601899.SS", "300502.SZ", "600036.SS", "000333.SZ",
    "688256.SS", "002475.SZ", "600900.SS", "601166.SS", "002594.SZ", "688041.SS", "603259.SS", "600030.SS",
    "300059.SZ", "601138.SS", "601398.SS", "600276.SS", "002384.SZ", "688981.SS", "002371.SZ", "603986.SS",
    "300476.SZ", "300274.SZ", "601288.SS", "688008.SS", "000858.SZ", "600150.SS", "601211.SS", "601328.SS",
    "000651.SZ", "600887.SS", "601088.SS", "000338.SZ", "600309.SS", "600919.SS", "688012.SS", "603993.SS",
    "000725.SZ", "601816.SS", "300394.SZ", "601857.SS", "002463.SZ", "603019.SS", "600089.SS", "600111.SS",
    "002415.SZ", "300124.SZ", "601601.SS", "000792.SZ", "600000.SS", "002714.SZ", "002028.SZ", "600031.SS",
    "000063.SZ", "300408.SZ", "601688.SS", "000001.SZ", "002230.SZ", "002142.SZ", "002050.SZ", "600406.SS",
    "300760.SZ", "601668.SS", "601225.SS", "603799.SS", "002460.SZ", "601012.SS", "600938.SS", "600660.SS",
    "601728.SS", "000425.SZ", "601229.SS", "600183.SS", "601600.SS", "600016.SS", "600522.SS", "300014.SZ",
    "601919.SS", "002352.SZ", "000100.SZ", "600926.SS", "300498.SZ", "600941.SS", "002709.SZ", "601939.SS",
    "002916.SZ", "603501.SS", "600176.SS", "002466.SZ", "601988.SS", "600690.SS", "601169.SS", "600028.SS",
    "600489.SS", "601985.SS", "000568.SZ", "601766.SS", "601009.SS", "300442.SZ", "601127.SS", "000977.SZ",
    "300033.SZ", "600050.SS", "000408.SZ", "600809.SS", "600989.SS", "000807.SZ", "600584.SS", "603288.SS",
    "601888.SS", "000938.SZ", "601006.SS", "002027.SZ", "600104.SS", "000776.SZ", "600547.SS", "600893.SS",
    "600010.SS", "601628.SS", "002241.SZ", "002625.SZ", "600905.SS", "688111.SS", "600999.SS", "601818.SS",
    "600426.SS", "601872.SS", "601100.SS", "601658.SS", "600019.SS", "605117.SS", "688271.SS", "601336.SS",
    "002001.SZ", "002049.SZ", "601689.SS", "601825.SS", "601390.SS", "002600.SZ", "300433.SZ", "600585.SS",
    "300015.SZ", "002938.SZ", "002648.SZ", "000630.SZ", "600160.SS", "600958.SS", "601838.SS", "601669.SS",
    "600875.SS", "600362.SS", "000625.SZ", "000538.SZ", "600066.SS", "600438.SS", "600346.SS", "002179.SZ",
    "601916.SS", "601998.SS", "600048.SS", "600015.SS", "600482.SS", "000975.SZ", "600436.SS", "300418.SZ",
    "000166.SZ", "605499.SS", "600795.SS", "601377.SS", "603296.SS", "002493.SZ", "002311.SZ", "600188.SS",
    "600570.SS", "601995.SS", "002074.SZ", "600760.SS", "300661.SZ", "688126.SS", "601868.SS", "000157.SZ",
    "601360.SS", "002422.SZ", "601077.SS", "603893.SS", "600219.SS", "601058.SS", "600233.SS", "600115.SS",
    "002236.SZ", "600415.SS", "600026.SS", "003816.SZ", "300803.SZ", "601877.SS", "000301.SZ", "601898.SS",
    "300782.SZ", "600009.SS", "600460.SS", "688047.SS", "688036.SS", "002736.SZ", "600886.SS", "000768.SZ",
    "600196.SS", "600372.SS", "601117.SS", "001979.SZ", "601698.SS", "601186.SS", "002920.SZ", "600011.SS",
    "300759.SZ", "688396.SS", "600674.SS", "601066.SS", "601901.SS", "601788.SS", "002304.SZ", "600741.SS",
    "002252.SZ", "600029.SS", "000963.SZ", "000895.SZ", "300347.SZ", "002601.SZ", "601881.SS", "000661.SZ",
    "300316.SZ", "601878.SS", "300866.SZ", "688223.SS", "000786.SZ", "000002.SZ", "601111.SS", "601633.SS",
    "601800.SS", "301236.SZ", "688169.SS", "000617.SZ", "600588.SS", "601021.SS", "601319.SS", "600023.SS",
    "600600.SS", "688506.SS", "300251.SZ", "002459.SZ", "600039.SS", "688472.SS", "601618.SS", "600515.SS",
    "603369.SS", "000983.SZ", "600027.SS", "302132.SZ", "000876.SZ", "301269.SZ", "600845.SS", "600085.SS",
    "601607.SS", "600918.SS", "001965.SZ", "300832.SZ", "600803.SS", "300628.SZ", "600930.SS", "300122.SZ",
    "600025.SS", "000596.SZ", "000999.SZ", "300896.SZ", "600061.SS", "300999.SZ", "601059.SS", "603260.SS",
    "000708.SZ", "601238.SS", "601456.SS", "603392.SS", "688082.SS", "688303.SS", "300413.SZ", "601018.SS",
    "600161.SS", "600018.SS", "688009.SS", "688187.SS", "603195.SS", "601236.SS", "601136.SS", "601808.SS",
    "300979.SZ", "601298.SS", "600377.SS", "001391.SZ",
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
    if not xls_path.exists():
        print(f"WARN CSI 300 weight file not found ({xls_path}); using fallback list.")
        return list(dict.fromkeys(CSI300_FALLBACK))

    try:
        import pandas as pd
    except ImportError as exc:
        raise ImportError("pandas is required to read CSI 300 universe files.") from exc

    try:
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
    except Exception as exc:
        print(f"WARN CSI 300 weight file read failed ({xls_path}: {exc}); using fallback list.")
        return list(dict.fromkeys(CSI300_FALLBACK))

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
