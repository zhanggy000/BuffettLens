# BuffettLens

A Python toolkit for value-investing screening across **US and A-share markets**, with auto-routed data sources.

**[中文 README](./README_zh.md)**

> Disclaimer: BuffettLens is a research helper, not investment advice.

---

## What it does

| Scenario | Script |
|---|---|
| Quick fundamentals for one or a few US stocks | `stock_info.py` |
| Batch-score a list of US tickers / NASDAQ 100 / S&P 500 / CSI 300 | `screener.run_screener` |
| Batch-score **mixed US + A-share** tickers in one run | `screener.run_screener` |
| Batch-score multiple universes together | `screener.run_screener --universe ndx100 sp500 csi300` |
| Fetch the largest 30 US-listed companies and list scores >= 60 | `score_us_top30.py` |

**Auto data routing** (you do nothing — the ticker format decides):

| Ticker format | Primary source | Fallback | 10Y bond used |
|---|---|---|---|
| `600519.SS` / `300502.SZ` (A-shares) | **Snowball** (xueqiu.com) | akshare (Sina/Baidu) | China 10Y ≈ 1.7% |
| `AAPL` / `MSFT` (US) | **yfinance** (Yahoo Finance) | — | US 10Y (^TNX live) |

Each generated report shows which data source was used.

---

## Install

Python 3.10+ recommended.

**Windows (PowerShell)**

```powershell
pip install -r requirements.txt
# or with explicit interpreter:
& "C:\Users\EDY\AppData\Local\Python\bin\python.exe" -m pip install -r requirements.txt
```

**macOS / Linux (bash/zsh)**

```bash
pip install -r requirements.txt
```

Dependencies: `yfinance` (US), `requests` (Snowball HTTP), `akshare` (A-share fallback), `pandas`, `lxml`, `xlrd`.

---

## Scenario 1 — Quick lookup of one US stock

`stock_info.py` prints fundamentals + a 7-point Buffett scorecard. US tickers only.

**Windows**
```powershell
python stock_info.py NVDA
python stock_info.py NVDA GOOGL MSFT --buffett
python stock_info.py NVDA --save
```

**macOS / Linux**
```bash
python stock_info.py NVDA
python stock_info.py NVDA GOOGL MSFT --buffett
python stock_info.py NVDA --save
```

If Windows console can't render emoji:
```powershell
$env:PYTHONIOENCODING="utf-8"
python stock_info.py NVDA --buffett
```

---

## Scenario 2 — Score a custom watchlist (US-only, A-share-only, or **mixed**)

This is the main entry point: `screener.run_screener`. Mixed input auto-routes.

**Windows (PowerShell)**
```powershell
# US only
python -m screener.run_screener --tickers "NVDA,GOOGL,MSFT,AVGO"

# A-share only
python -m screener.run_screener --tickers "600519.SS,300502.SZ,000651.SZ"

# Mixed in one run — bond rate is picked per ticker (CN vs US 10Y)
python -m screener.run_screener --tickers "AAPL,MSFT,600519.SS,300502.SZ,NVDA"
```

**macOS / Linux**
```bash
python -m screener.run_screener --tickers "NVDA,GOOGL,MSFT,AVGO"
python -m screener.run_screener --tickers "600519.SS,300502.SZ,000651.SZ"
python -m screener.run_screener --tickers "AAPL,MSFT,600519.SS,300502.SZ,NVDA"
```

Console will show e.g.:
```
US 10Y: 4.46%   CN 10Y: 1.70%

[1/5] AAPL      → 56.0  ⭐
[2/5] MSFT      → 68.0  ⭐⭐
[3/5] 600519.SS → 68.0  ⭐⭐  贵州茅台
...
```

---

## Scenario 3 — Score universes (NASDAQ 100 / S&P 500 / CSI 300)

**Windows**
```powershell
python -m screener.run_screener --universe ndx100
python -m screener.run_screener --universe sp500
python -m screener.run_screener --universe csi300
python -m screener.run_screener --universe ndx100 sp500
python -m screener.run_screener --universe ndx100 sp500 csi300
python -m screener.run_screener --universe all
python -m screener.run_screener --universe ndx100 --limit 50
```

**macOS / Linux**
```bash
python -m screener.run_screener --universe ndx100
python -m screener.run_screener --universe sp500
python -m screener.run_screener --universe csi300
python -m screener.run_screener --universe ndx100 sp500
python -m screener.run_screener --universe ndx100 sp500 csi300
python -m screener.run_screener --universe all
```

When multiple universes are passed, BuffettLens keeps the first occurrence of each ticker and skips duplicates. A duplicate audit file is written inside that run's report folder.

Common flags:
```text
--delay 3            request interval seconds (default 2; only matters for cache misses)
--force-refresh      ignore SQLite cache
--limit 10           process only first N (for testing)
--min-score 70       reports only for stocks >= this (default 60)
--all-reports        generate reports even for failed-gate / low-score
```

---

## Scenario 4 — Legacy top-N CSI 300 driver

The main entry point now supports full CSI 300 directly:

```powershell
python -m screener.run_screener --universe csi300
```

CSI 300 uses `data/000300closeweight.xls` by default. Optionally, set `CSI300_WEIGHT_XLS` to point at a different CSI 300 weight file for one run. If the Excel file is missing or unreadable, BuffettLens falls back to the hard-coded `CSI300_FALLBACK` ticker list.

`run_csi300.py` is a convenience helper for top-N CSI 300 runs. It reads `data/000300closeweight.xls`, keeps index-weight order, and then applies `--limit N`.

**Windows**
```powershell
python run_csi300.py --limit 50
python run_csi300.py --limit 80
```

**macOS / Linux**

Run the same commands from the repo root:
```bash
python run_csi300.py --limit 50
python run_csi300.py --limit 80
```

Snowball is fast: 50 stocks finish in ~45 seconds.

---

## Scenario 5 — Largest 30 US-listed stocks

`score_us_top30.py` is a dedicated root-level helper for the current US mega-cap screen. It first fetches candidate companies from a public market-cap ranking, then refreshes every stock through the existing project pipeline:

```text
screener.fetcher.fetch_stock(..., force_refresh=True)
→ screener.metrics.compute_metrics(...)
→ screener.scorer.score(...)
```

Run it from the repository root:

```powershell
python score_us_top30.py
```

The final table lists only companies with `BuffettLens` total score `>= 60`, sorted by the refreshed `market_cap` returned by the project fetcher. For ADRs and non-US issuers, Yahoo may use USD for market data and another currency for statements; the scoring logic skips `FCF Yield` and `P/FCF` when currencies differ.

This helper does not replace or rename the normal entry points: `stock_info.py`, `screener.run_screener`, and `run_csi300.py` keep their existing usage.

---

## Output files

All scripts write into a new run folder under `reports/`. Existing reports are not deleted.

```
reports/
└── 20260513_150501_ndx100_limit80_score60/
    ├── 20260513_150501_ndx100_limit80_score60_summary.csv
    ├── 085.0_ADBE_Adobe_Inc.md
    └── ...
```

Each Markdown report has a footer line indicating data source:
```
*Data source: Snowball xueqiu.com (A-share primary) | akshare → Sina/Baidu (A-share fallback) | Yahoo Finance via yfinance (US/HK)*
```

Each run gets its own folder, so old Markdown reports and summary CSVs are preserved.

---

## Portfolio Tracking

Create a simulated portfolio from any BuffettLens report folder:

```powershell
python create_portfolio.py --report-dir reports/20260513_150501_ndx100_limit80_score60 --min-score 75 --cash 100000 --currency USD --method equal
python create_portfolio.py --report-dir reports/20260513_150501_ndx100_limit80_score60 --min-score 75 --cash 100000 --currency USD --method score_weighted
```

Allocation methods:

```text
equal           equal cash per stock
score_weighted  higher scores get larger weights
top_heavy       higher scores get much larger weights (score squared)
```

Track the portfolio later. The tracker backfills history from the buy date to the latest trading day, so it works whether you run it daily or after missing several days:

```powershell
python track_portfolio.py --portfolio portfolios/20260513_183000_ndx100_score75_cash100000_equal
```

Portfolio outputs:

```text
portfolios/{portfolio_name}/portfolio.json
portfolios/{portfolio_name}/positions.csv
portfolios/{portfolio_name}/report.md
portfolios/{portfolio_name}/history.csv
portfolios/{portfolio_name}/latest.md
```

`history.csv` compares portfolio return with SPY and QQQ. This is a simulated fractional-share portfolio.
`--currency` is the base cash currency and defaults to `USD`. A-shares are treated as `CNY`, US stocks as `USD`; FX rates are fetched from Yahoo Finance and recorded in the portfolio tables.

---

## Scoring model

100 points across six categories:

| Group | Max | Focus |
|---|---:|---|
| A — Buffett core quality | 35 | ROE, ROIC, margins, FCF/NI, gross margin trend |
| B — Financial strength | 15 | LT-debt/NI, D/E, interest coverage, current ratio |
| C — Growth | 15 | NI CAGR, revenue CAGR, loss years, share dilution |
| D — Valuation | 20 | Forward PE, PEG, FCF Yield, P/FCF, E/P vs 10Y |
| E — Munger moat | 10 | OpMargin level + stability (CV), goodwill ratio |
| F — Technical reference | 5 | price vs 200MA, RSI |

**Hard gates** (must pass to generate a report by default):
- Market cap ≥ ~$500M (in CNY for A-shares ≈ ¥3.5B)
- 4-year average ROE ≥ 8%
- Latest annual net income > 0
- D/E ≤ 3.0  *(banks fail this by design — known limitation, see below)*
- ≥ 2 years of financial history
- < 3 loss years in the available history

**ROE is computed China-GAAP style**: NI / weighted-average equity ((beginning + ending) / 2), using **parent-company equity** (归属于母公司股东权益) to match the 归母净利润 numerator. This matches what Snowball / Wind display.

---

## A-share data quality notes

- **Primary source is Snowball** because it provides Chinese-standard 加权 ROE, full three statements (income / balance / cash flow), and live PE/PB in a single coherent API.
- **akshare (Sina/Baidu) fallback** — used when Snowball fails (cookie expiry / rate limit). One known issue: Sina's pre-computed `净资产收益率(ROE)` field has occasional bugs (e.g., 紫金矿业 2024 returns 21.66 instead of 25.89). BuffettLens does **not** trust this field; ROE is always recomputed from NI/equity.
- **Banks and brokers underscored**: D/E is computed as interest-bearing debt / equity. Banks have 10x+ leverage by accounting nature — the hard gate flags them but final scores are still computed. Use them as relative comparison within sector.
- **CapEx is real, not approximated**: Snowball provides `cash_paid_for_assets` directly, so FCF = OCF − CapEx is accurate (unlike the previous akshare-only approximation FCF ≈ OCF).

---

## US-stock currency edge case

For ADRs and non-US issuers, Yahoo may return market data in one currency (USD) and statements in another (TWD, EUR…). When they differ, BuffettLens skips `FCF Yield` and `P/FCF` to avoid false cheapness.

---

## Project structure

```
BuffettLens/
├── stock_info.py                # Quick US-stock fundamentals + 7-pt scorecard
├── score_us_top30.py            # Fetch US market-cap Top 30 and list scores >= 60
├── run_csi300.py                # Top-N CSI 300 by weight driver
├── data/
│   └── 000300closeweight.xls    # CSI 300 constituent weight file
├── screener/
│   ├── run_screener.py          # Main CLI (mixed input supported)
│   ├── fetcher.py               # Routing + SQLite cache + treasury fetch
│   ├── xueqiu_fetcher.py        # Snowball v5 client (A-share primary)
│   ├── ashare_fetcher.py        # akshare adapter (A-share fallback)
│   ├── metrics.py               # Indicator computation (weighted ROE, ROIC, etc.)
│   ├── scorer.py                # 100-point scoring + hard gates
│   ├── reporter.py              # Markdown + CSV output
│   └── universe.py              # NDX100 / SP500 / CSI300 ticker lists
├── reports/                     # Run outputs (gitignored)
├── requirements.txt
├── README.md
└── README_zh.md
```

---

## Common questions

**Why does a high-scoring stock drop a lot?** Could be margin-of-safety compression, or genuine business decay. Reports show price-action context for context, not causation.

**Why are banks scored low?** D/E gate is calibrated for industrials/tech. Banks are a known structural mis-fit; their core ratios (NIM, CAR, NPL) aren't in the model.

**Snowball is rate-limited — what happens?** First failure triggers the akshare fallback automatically. You'll see `→ 回退 akshare` in the console.

**Why does ETN-type quality compounder score low?** Most likely valuation is rich (PE / PEG / FCF Yield all fail thresholds), pulling D-group down.
