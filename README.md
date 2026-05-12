# 🔍 BuffettLens

> A Python CLI tool that fetches real-time stock data and scores companies through Warren Buffett & Charlie Munger's value investing lens.

**[中文版 README](./README_zh.md)**

![Python](https://img.shields.io/badge/python-3.10+-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)
![Data](https://img.shields.io/badge/data-Yahoo%20Finance-purple.svg)

---

## ✨ Features

- 📊 **Real-time market data** via Yahoo Finance (no API key needed)
- 💰 **30+ key metrics**: Forward PE, PEG, ROE, FCF, margins, debt ratios
- 📋 **Last 4 quarters financials**: revenue, gross profit, operating income, net income
- 👔 **Analyst consensus**: ratings, price targets, upside potential
- 🎯 **Buffett Scorecard**: 7-point quality screen based on value investing principles
- 💾 **JSON export** for historical tracking and analysis
- 🌐 **Cross-platform**: works on macOS, Linux, and Windows

---

## 📦 Installation

### Prerequisites
- Python 3.10 or higher
- pip (Python package manager)

### Install dependencies

```bash
pip install yfinance
```

Or using `requirements.txt`:

```bash
pip install -r requirements.txt
```

---

## 🚀 Usage

### macOS / Linux (Terminal)

```bash
# Single stock
python3 stock_info.py NVDA

# Multiple stocks
python3 stock_info.py NVDA GOOGL MSFT

# With Buffett scorecard (recommended)
python3 stock_info.py NVDA --buffett

# Save data to JSON
python3 stock_info.py NVDA GOOGL --save

# Interactive mode (no arguments)
python3 stock_info.py
```

### Windows (PowerShell)

```powershell
# Single stock
python stock_info.py NVDA

# Multiple stocks with Buffett scorecard
python stock_info.py NVDA GOOGL MSFT --buffett

# Save to JSON
python stock_info.py NVDA --save
```

### Windows (CMD / Command Prompt)

```cmd
python stock_info.py NVDA --buffett
```

### If `python` is not in your PATH

**macOS/Linux:**
```bash
/usr/local/bin/python3 stock_info.py NVDA
```

**Windows (specify full path):**
```powershell
& "C:\Users\YOUR_USERNAME\AppData\Local\Programs\Python\Python311\python.exe" stock_info.py NVDA
```

---

## 📋 Sample Output

```
======================================================================
  🔍 NVDA
======================================================================

📊 Company: NVIDIA Corporation
🏢 Industry: Semiconductors | Sector: Technology
🌍 Country: United States
👥 Employees: 42,000

💰 Price
  Current:    $219.44 🔺 +1.96%
  52W High:   $222.30
  52W Low:    $124.47
  50D MA:     $189.50
  200D MA:    $184.96

📈 Valuation
  Market Cap:  $5.33T
  TTM PE:      44.88
  Forward PE:  19.44
  PEG:         0.68
  P/B:         33.91
  EV/EBITDA:   39.64

💵 Profitability
  EPS (TTM):    $4.89
  Gross Margin: 71.07%
  Net Margin:   55.60%
  ROE:          101.48%
  ROA:          51.19%

📊 Growth (YoY)
  Revenue:    73.20%
  Earnings:   95.60%

💸 Cash Flow
  Operating:  $102.72B
  Free CF:    $58.13B

🎯 Buffett Scorecard
  ❌ PE 44.9 too high
  ✅ ROE 101.5% > 15%
  ✅ Net Margin 55.6% > 10%
  ✅ Debt/Equity 7% < 100%
  ✅ Free Cash Flow positive
  ✅ Revenue Growth 73.2% > 5%
  ✅ Not overheated vs 200D MA

  📊 Score: 6/7  → 🌟 Strongly aligned with Buffett criteria
```

*Note: The actual script outputs labels in Chinese. See [README_zh.md](./README_zh.md) for Chinese output examples.*

---

## 🎯 Buffett Scorecard Explained

The script evaluates each stock against 7 Warren Buffett & Charlie Munger value investing criteria:

| # | Criterion | Threshold | Why It Matters |
|---|-----------|-----------|----------------|
| 1 | TTM PE Ratio | < 25 | Avoid overpaying for earnings |
| 2 | Return on Equity | > 15% | Quality businesses earn high returns on capital |
| 3 | Net Profit Margin | > 10% | Pricing power and operational efficiency |
| 4 | Debt-to-Equity | < 100% | Financial resilience |
| 5 | Free Cash Flow | > 0 | The company actually generates cash |
| 6 | Revenue Growth | > 5% | Business is expanding, not stagnating |
| 7 | Price vs 200D MA | < 120% | Avoid buying at frothy peaks |

**Score Interpretation:**
- 🌟 **6-7 / 7**: Strongly aligned with Buffett standards
- 👍 **4-5 / 7**: Partial fit, worth monitoring
- ⚠️ **< 4 / 7**: Does not meet Buffett's criteria

> ⚠️ **Disclaimer**: The Buffett Scorecard is a quantitative starting point, not a complete analysis. Buffett emphasizes qualitative factors (moat, management, predictability) that no script can fully capture. Always do your own research.

---

## 📊 All Metrics Output

<details>
<summary>Click to expand full metric list</summary>

### Company Info
- Long name, industry, sector, country, employees

### Price Data
- Current price, daily change %
- 52-week high/low
- 50-day & 200-day moving averages

### Valuation Ratios
- Market Cap, Enterprise Value
- TTM PE, Forward PE
- PEG Ratio
- Price-to-Book (P/B)
- Price-to-Sales (P/S)
- EV/EBITDA
- EV/Revenue

### Profitability
- EPS (TTM, Forward)
- Gross margin, Operating margin, Net margin
- ROE (Return on Equity)
- ROA (Return on Assets)

### Growth (YoY)
- Quarterly revenue growth
- Quarterly earnings growth
- EPS growth

### Dividends (if applicable)
- Dividend yield (calculated from rate/price)
- Annual dividend
- Payout ratio
- 5-year average yield

### Balance Sheet
- Total cash, Total debt
- Debt-to-equity ratio
- Current ratio, Quick ratio
- Book value per share

### Cash Flow
- Operating cash flow
- Free cash flow

### Analyst Coverage
- Consensus recommendation
- Mean / High / Low target price
- Upside potential vs current
- Number of analysts covering

### Financial Statements
- Last 4 quarters of: Revenue, Gross Profit, Operating Income, Net Income

### Business Summary
- 400-character business description excerpt

</details>

---

## 🛠️ Command Line Arguments

| Argument | Description |
|----------|-------------|
| `tickers` | One or more stock symbols (e.g., `NVDA GOOGL MSFT`) |
| `--buffett` | Display the Buffett 7-point scorecard |
| `--save` | Export all queried data to a timestamped JSON file |
| `-h`, `--help` | Show help message |

---

## 💡 Use Cases

1. **Pre-purchase research**: Quickly evaluate a stock against value investing criteria
2. **Portfolio review**: Run your entire holdings monthly to track quality changes
3. **Screening**: Compare multiple candidates side-by-side
4. **Historical tracking**: Use `--save` to build a personal database
5. **Earnings season**: After a report drops, run the script to see updated metrics

---

## ⚠️ Data Source Notes

- **Source**: Yahoo Finance (via the `yfinance` Python library)
- **Latency**: ~15-20 minute delay during market hours
- **After-hours**: Prices don't update; fundamentals (PE, financials) remain accurate
- **For real-time data**: Consider paid APIs like Polygon, IEX Cloud, or Alpaca
- **For long-term investors**: 15-min delayed data is more than sufficient

---

## 🐛 Troubleshooting

### "ModuleNotFoundError: No module named 'yfinance'"
```bash
pip install yfinance
# or
python -m pip install yfinance
```

### Some fields show "N/A"
- Yahoo Finance occasionally has missing fields for foreign stocks (e.g., TSM) or recently IPO'd companies
- The script handles missing data gracefully — affected fields display as `N/A`

### Financials show `$nan` for the most recent quarter
- Yahoo Finance may not have processed the latest quarterly filing
- Wait a few days after earnings, or use the prior quarter

### "Connection error" or rate limiting
- Yahoo Finance has informal rate limits
- If querying many stocks, add `time.sleep(1)` between requests in the loop
- Consider running the script during off-peak hours

---

## 📁 Project Structure

```
BuffettLens/
├── stock_info.py        # Main script
├── README.md            # English documentation (this file)
├── README_zh.md         # Chinese documentation
├── requirements.txt     # Python dependencies
├── LICENSE              # MIT License
└── .gitignore           # Git ignore rules
```

---

## 🤝 Contributing

Pull requests welcome! Some ideas for enhancements:

- [ ] Add comparison mode (side-by-side table of multiple stocks)
- [ ] Add historical PE chart
- [ ] Add ETF holdings breakdown
- [ ] Add insider trading data
- [ ] Add options data
- [ ] Internationalization (English-only output mode)
- [ ] CSV export option
- [ ] Discord/Telegram bot integration

---

## 📜 License

[MIT](./LICENSE) — feel free to use, modify, and distribute.

---

## 🙏 Acknowledgments

- **Warren Buffett & Charlie Munger** — for the timeless investing wisdom that inspired the scorecard
- **[yfinance](https://github.com/ranaroussi/yfinance)** — the excellent Python library powering this tool
- **Yahoo Finance** — for providing free financial data

---

## 📬 Author

Created as a personal value-investing toolkit. Inspired by the realization that **TTM PE is the rearview mirror, Forward PE is the headlight** — and that real-time data beats large-language-model memory every time.

> "Risk comes from not knowing what you're doing."
> — Warren Buffett

> "Invert, always invert."
> — Charlie Munger

⭐ **If this tool helps you make better investment decisions, please star the repo!**
