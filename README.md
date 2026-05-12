# BuffettLens

A Python toolkit for stock lookup and value-investing screening with free Yahoo Finance data.

**[中文 README](./README_zh.md)**

BuffettLens has two entry points:

- `stock_info.py`: quick single-stock or multi-stock lookup with a simple 7-point Buffett-style scorecard.
- `screener/`: a 100-point batch screening system that scans a universe and generates Markdown reports.

> Disclaimer: This project is a research helper, not investment advice.

---

## Install

Python 3.10+ is recommended.

```bash
pip install -r requirements.txt
```

Dependencies:

- `yfinance`
- `pandas`
- `lxml`

---

## Quick Lookup: `stock_info.py`

```bash
# Single stock
python stock_info.py NVDA

# Multiple stocks
python stock_info.py NVDA GOOGL MSFT

# Show the 7-point Buffett scorecard
python stock_info.py NVDA --buffett

# Save JSON
python stock_info.py NVDA GOOGL --save
```

On Windows, if your console cannot print emoji, set:

```powershell
$env:PYTHONIOENCODING="utf-8"
python stock_info.py NVDA --buffett
```

---

## 100-Point Screener

The 100-point system lives under `screener/`.

```bash
# Custom tickers
python -m screener.run_screener --tickers NVDA,GOOGL,MSFT,AVGO,TSM

# NASDAQ 100
python -m screener.run_screener --universe ndx100

# S&P 500
python -m screener.run_screener --universe sp500

# Both universes
python -m screener.run_screener --universe both
```

Useful options:

```bash
--delay 3          # request delay; default is 2 seconds
--force-refresh   # refresh yfinance cache
--limit 10        # process only the first N tickers
--min-score 70    # default is 60
--all-reports     # generate reports even for low-score / failed-gate stocks
```

Reports are written to:

```text
reports/
```

Outputs:

- `_summary_YYYY-MM-DD.csv` or `_summary_YYYY-MM-DD_HHMMSS.csv`
- `{score}_{TICKER}_{company}.md`

The screener clears old per-stock Markdown reports before each run so different runs do not mix.

---

## Scoring Model

The score is 100 points across six groups:

| Group | Name | Max | Focus |
|---|---|---:|---|
| A | Buffett core quality | 35 | ROE, ROIC, margins, FCF quality, gross margin trend |
| B | Financial strength | 15 | debt, D/E, interest coverage, current ratio |
| C | Growth | 15 | net income CAGR, revenue CAGR, loss years, share count |
| D | Valuation | 20 | Forward PE, PEG, FCF Yield, P/FCF, earnings yield vs 10Y Treasury |
| E | Munger moat | 10 | operating margin level, margin stability, goodwill/assets |
| F | Technical reference | 5 | price vs 200-day moving average, RSI |

Technical indicators are intentionally capped at 5 points.

Hard gates are applied before report generation:

- market cap above $500M
- ROE above 8%
- latest annual net income positive
- D/E below 3.0
- at least 2 years of financial history
- not too many recent loss years

---

## Report Contents

Each Markdown report includes:

- total score and rating
- recommendation summary
- price-action context: YTD, 1-year, 3-year returns, drawdown, 52-week position
- likely decline reasons when available; otherwise "unknown reason"
- high-score strong-price-action alerts
- business summary from Yahoo Finance
- detailed A-F scoring table
- key metrics snapshot
- technical reference
- source label explanations

---

## Currency Handling

For ADRs and non-US companies, Yahoo Finance may return market data in one currency and financial statements in another. When `currency` and `financialCurrency` differ, BuffettLens avoids calculating `FCF Yield` and `P/FCF` to prevent false cheapness from currency mismatch.

---

## Project Structure

```text
BuffettLens/
├── stock_info.py
├── screener/
│   ├── universe.py
│   ├── fetcher.py
│   ├── metrics.py
│   ├── scorer.py
│   ├── reporter.py
│   └── run_screener.py
├── reports/
├── requirements.txt
├── README.md
└── README_zh.md
```
