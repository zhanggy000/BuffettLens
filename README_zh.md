# BuffettLens

一个支持 **A 股 + 美股** 的价值股筛选工具,数据源按 ticker 自动路由。

> 免责声明:BuffettLens 只做数据整理和量化初筛,不构成投资建议。高分不等于可以买,低分也不等于一定差。

---

## 我该用哪个脚本?

| 场景 | 脚本 | 入口命令 |
|---|---|---|
| 单只/几只美股快速查询 + 7 项简易评分 | `stock_info.py` | `python stock_info.py NVDA` |
| 批量评分:自定义清单(美股 / A 股 / **混合**) | `screener.run_screener` | `python -m screener.run_screener --tickers ...` |
| 批量评分:整个股票池(NASDAQ 100 / S&P 500 / CSI 300) | `screener.run_screener` | `python -m screener.run_screener --universe ndx100` |
| 批量评分:多个股票池 | `screener.run_screener` | `python -m screener.run_screener --universe ndx100 sp500 csi300` |

## 数据源是自动选的

不用配置,根据 ticker 形式自动决定:

| ticker 形式 | 主源 | 兜底 | 10年期国债基准 |
|---|---|---|---|
| `600519.SS` / `300502.SZ`(A股) | **雪球** xueqiu.com | akshare(新浪/百度) | 中国 10Y ≈ 1.7% |
| `AAPL` / `MSFT`(美股) | **yfinance**(Yahoo Finance) | 无 | 美国 10Y (^TNX 动态取) |

每份 Markdown 报告底部都会标注用了哪个数据源。

---

## 安装

建议 Python 3.10+。

**Windows(PowerShell)**

```powershell
pip install -r requirements.txt
# 或用显式 Python 路径:
& "C:\Users\EDY\AppData\Local\Python\bin\python.exe" -m pip install -r requirements.txt
```

**macOS / Linux(bash/zsh)**

```bash
pip install -r requirements.txt
```

依赖:`yfinance`(美股)、`requests`(雪球 HTTP)、`akshare`(A 股兜底)、`pandas`、`lxml`、`xlrd`。

---

## 场景 1 — 看一两只美股的基本面

`stock_info.py` 显示基本面 + 7 项 Buffett 评分。**只支持美股**。

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

Windows 控制台如果显示 emoji 报错:
```powershell
$env:PYTHONIOENCODING="utf-8"
python stock_info.py NVDA --buffett
```

`stock_info.py` 输出:公司/行业/国家/员工数、价格/52周高低/均线、PE/Forward PE/PEG/PB/PS/EV-EBITDA、各项利润率、ROE/ROA、营收/利润增长、现金/债务/流动比率/FCF、分析师目标价、7 项 Buffett 评分。

---

## 场景 2 — 跑自定义清单(美股 / A 股 / **混合**)

这是最常用的入口。混合输入自动按 ticker 路由,国债收益率也会按市场自动选(中国 1.7% / 美国 4%)。

**Windows(PowerShell)**
```powershell
# 纯美股
python -m screener.run_screener --tickers "NVDA,GOOGL,MSFT,AVGO"

# 纯 A 股
python -m screener.run_screener --tickers "600519.SS,300502.SZ,000651.SZ"

# 混合一次跑 — 数据源、国债基准都自动按股票选
python -m screener.run_screener --tickers "AAPL,MSFT,600519.SS,300502.SZ,NVDA"
```

**macOS / Linux**
```bash
python -m screener.run_screener --tickers "NVDA,GOOGL,MSFT,AVGO"
python -m screener.run_screener --tickers "600519.SS,300502.SZ,000651.SZ"
python -m screener.run_screener --tickers "AAPL,MSFT,600519.SS,300502.SZ,NVDA"
```

终端会输出类似:
```
US 10Y: 4.46%   CN 10Y: 1.70%

[1/5] AAPL      → 56.0  ⭐
[2/5] MSFT      → 68.0  ⭐⭐
[3/5] 600519.SS → 68.0  ⭐⭐  贵州茅台
...
```

---

## 场景 3 — 跑整个股票池(NASDAQ 100 / S&P 500)

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

传入多个股票池时,BuffettLens 会保留每个 ticker 第一次出现的位置,重复成分股会跳过不重复跑。重复记录会写入本次运行的报告目录。

常用参数:
```text
--delay 3            请求间隔秒数(默认 2,仅影响 cache miss 的请求)
--force-refresh      忽略 SQLite 缓存强制刷新
--limit 10           只跑前 N 只(测试用)
--min-score 70       低于此分不生成单股报告(默认 60)
--all-reports        即便未过硬门槛或分数低也生成报告(调试用)
```

`csi300` 默认读取仓库内 `data/000300closeweight.xls`。如需临时使用另一份沪深300权重表,可设置 `CSI300_WEIGHT_XLS` 环境变量。Excel 文件缺失或读取失败时,会回退到代码内置的 `CSI300_FALLBACK` ticker 列表。

---

## 场景 4 — 跑沪深 300 前 N 大权重

入口:`run_csi300.py`。它读取 `data/000300closeweight.xls`,按权重排序后用 `--limit N` 跑前 N 只。

**Windows**
```powershell
python run_csi300.py --limit 50
python run_csi300.py --limit 80
```

**macOS / Linux**

在仓库根目录直接运行:
```bash
python run_csi300.py --limit 50
python run_csi300.py --limit 80
```

雪球速度很快 — 50 只大约 45 秒。

---

## 输出文件在哪

所有脚本都会在 `reports/` 下新建一个本次运行目录,不会清空旧报告:

```
reports/
└── 20260513_150501_ndx100_limit80_score60/
    ├── 20260513_150501_ndx100_limit80_score60_summary.csv
    ├── 085.0_ADBE_Adobe_Inc.md
    └── ...
```

每份 Markdown 报告底部一行注明数据源,例如:
```
*数据源: 雪球 xueqiu.com (A股主源)*
```

目录名格式为 `生成时间_市场_limitN_scoreN`,例如 `20260513_150501_ndx100_limit80_score60`。

---

## 100 分系统怎么算

总分 100 分,六组:

| 组 | 满分 | 关注点 |
|---|---:|---|
| A — Buffett 核心质量 | 35 | ROE、ROIC、各项利润率、FCF/净利润、毛利率趋势 |
| B — 财务稳健性 | 15 | 长债/净利润、D/E、利息保障倍数、流动比率 |
| C — 成长性 | 15 | 净利润 CAGR、营收 CAGR、亏损年份、股本变化 |
| D — 估值 | 20 | Forward PE、PEG、FCF Yield、P/FCF、E/P vs 10Y 国债 |
| E — Munger 护城河 | 10 | 营业利润率水平、利润率稳定性(CV)、商誉/总资产 |
| F — 技术参考 | 5 | 价格 vs 200日均线、RSI |

**硬门槛**(默认不通过不生成单股报告):
- 市值 ≥ 5 亿美元(A 股 ≈ 35 亿人民币)
- 4 年平均 ROE ≥ 8%
- 最近年度净利润 > 0
- D/E ≤ 3.0  *(银行结构性不通过,见下)*
- 至少 2 年财务历史
- 近期亏损年份 < 3

**ROE 用中国会计准则口径计算**:NI / 加权平均权益((期初+期末)/2),且分母用**归属母公司股东权益**(跟分子的归母净利润对齐口径)。这跟雪球/Wind 显示的一致。

---

## A 股数据口径说明

- **主源选雪球**:它提供中国会计准则加权 ROE、完整三表、实时 PE/PB,一个 API 给齐。
- **akshare(新浪/百度)兜底**:雪球失败(cookie 失效 / 限速)时自动启用。已知问题:新浪 `净资产收益率(ROE)` 字段偶有 bug(例如紫金矿业 2024 返回 21.66 而非真实的 25.89),BuffettLens **不信任**这个字段,ROE 始终从 NI/权益重算。
- **银行/券商分数偏低**:D/E 用「计息债务/股东权益」,银行天然 10x+ 杠杆,被硬门槛拦下。不代表银行差,只是模型口径不适用。建议银行内部横向比较。
- **真 FCF,不再用 OCF 近似**:雪球直接提供 `cash_paid_for_assets`,FCF = OCF − CapEx 是准的。

---

## 美股的币种边界情况

ADR / 非美国公司 Yahoo 可能返回不一致的币种(股价 USD、财报 TWD)。BuffettLens 检测到币种不一致时,会跳过 `FCF Yield` 和 `P/FCF`,避免不同币种相除得出虚假便宜。

---

## 项目结构

```
BuffettLens/
├── stock_info.py                # 美股单股查询 + 7 项简易评分
├── run_csi300.py                # 沪深300前N权重驱动脚本
├── data/
│   └── 000300closeweight.xls    # 沪深300成分权重文件
├── screener/
│   ├── run_screener.py          # 主入口(支持混合输入)
│   ├── fetcher.py               # 路由 + SQLite 缓存 + 国债收益率
│   ├── xueqiu_fetcher.py        # 雪球 v5 客户端(A 股主源)
│   ├── ashare_fetcher.py        # akshare 适配器(A 股兜底)
│   ├── metrics.py               # 指标计算(加权 ROE、ROIC 等)
│   ├── scorer.py                # 100 分评分 + 硬门槛
│   ├── reporter.py              # Markdown + CSV 输出
│   └── universe.py              # NDX100 / SP500 / CSI300 清单
├── reports/                     # 运行生成(gitignore)
├── requirements.txt
├── README.md
└── README_zh.md
```

---

## 常见问题

**为什么高分股票跌很多?** 可能是估值压缩留下了安全边际,也可能是业务被永久削弱。报告里的"涨跌背景"会给提示,但不会下因果结论。

**为什么银行分数低?** D/E 硬门槛是按工业/科技校准的。银行 10x+ 杠杆是会计本质,模型口径不适用 — 银行该看 NIM、资本充足率、不良率。

**雪球被限速了怎么办?** 会自动回退到 akshare,终端显示 `→ 回退 akshare`。继续跑不打断。

**ETN 这种好公司为啥分数低?** 多半是估值贵 — PE/PEG/FCF Yield 全部不满足价值门槛,D 组拉低总分。

**ROE 跟雪球对不上?** 旧版本用「NI/期末权益」,会系统性低估快速增长公司的 ROE。现版用「NI/加权平均归母权益」,与雪球完全一致。
