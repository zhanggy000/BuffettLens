# BuffettLens

一个用 Yahoo Finance 免费数据做美股查询和价值筛选的小工具。

项目里有两个入口：

- `stock_info.py`：单股/多股即时查询，带 7 项 Buffett 简易评分卡。
- `screener/`：100 分价值筛选系统，批量扫描股票池并生成 Markdown 报告。

> 免责声明：本项目只做数据整理和量化初筛，不构成投资建议。高分不等于可以买，低分也不等于一定差。请结合业务、行业、估值、风险和自己的研究判断。

---

## 安装

建议使用 Python 3.10+。

```powershell
pip install -r requirements.txt
```

如果你使用本机当前约定的 Python 路径，可以这样运行：

```powershell
& "C:\Users\EDY\AppData\Local\Python\bin\python.exe" -m pip install -r requirements.txt
```

依赖包括：

- `yfinance`：获取 Yahoo Finance 数据
- `pandas`：yfinance 依赖，同时用于读取股票池
- `lxml`：读取 Wikipedia 成分股表格

---

## 入口一：日常查询 `stock_info.py`

这个脚本适合快速看单只股票或几只股票的实时数据。

```powershell
# 查询单只股票
& "C:\Users\EDY\AppData\Local\Python\bin\python.exe" stock_info.py NVDA

# 查询多只股票
& "C:\Users\EDY\AppData\Local\Python\bin\python.exe" stock_info.py NVDA GOOGL MSFT

# 显示 7 项 Buffett 简易评分卡
& "C:\Users\EDY\AppData\Local\Python\bin\python.exe" stock_info.py NVDA --buffett

# 保存 JSON 数据
& "C:\Users\EDY\AppData\Local\Python\bin\python.exe" stock_info.py NVDA GOOGL --save
```

如果 Windows 控制台显示 emoji 报错，可以先设置输出编码：

```powershell
$env:PYTHONIOENCODING="utf-8"
& "C:\Users\EDY\AppData\Local\Python\bin\python.exe" stock_info.py NVDA --buffett
```

`stock_info.py` 会显示：

- 公司、行业、国家、员工数
- 当前价格、52 周高低点、50/200 日均线
- PE、Forward PE、PEG、PB、PS、EV/EBITDA
- 毛利率、营业利润率、净利率、ROE、ROA
- 营收/利润增长
- 现金、债务、流动比率、自由现金流
- 分析师目标价和评级
- 7 项 Buffett 简易评分卡

---

## 入口二：100 分价值筛选系统

100 分系统在 `screener/` 目录里，适合批量扫描股票池并生成单股 Markdown 报告。

### 快速运行

```powershell
# 扫描自定义股票列表
& "C:\Users\EDY\AppData\Local\Python\bin\python.exe" -m screener.run_screener --tickers NVDA,GOOGL,MSFT,AVGO,TSM

# 扫描 NASDAQ 100
& "C:\Users\EDY\AppData\Local\Python\bin\python.exe" -m screener.run_screener --universe ndx100

# 扫描 S&P 500
& "C:\Users\EDY\AppData\Local\Python\bin\python.exe" -m screener.run_screener --universe sp500

# 同时扫描 NASDAQ 100 和 S&P 500
& "C:\Users\EDY\AppData\Local\Python\bin\python.exe" -m screener.run_screener --universe both
```

### 常用参数

```powershell
# 设置请求间隔，默认 2 秒，降低被 Yahoo 限流的概率
--delay 3

# 强制刷新缓存
--force-refresh

# 限制处理数量，适合测试
--limit 10

# 修改生成报告的最低分，默认 60
--min-score 70

# 所有股票都生成报告，包括低于 min-score 或未通过硬门槛的股票
--all-reports
```

示例：

```powershell
& "C:\Users\EDY\AppData\Local\Python\bin\python.exe" -m screener.run_screener --universe ndx100 --delay 3

& "C:\Users\EDY\AppData\Local\Python\bin\python.exe" -m screener.run_screener --tickers ETN --all-reports
```

---

## 输出文件

运行后输出在：

```text
reports/
```

包括：

- `_summary_YYYY-MM-DD.csv` 或 `_summary_YYYY-MM-DD_HHMMSS.csv`：汇总 CSV，按分数降序。
- `{分数}_{TICKER}_{公司名}.md`：单股 Markdown 报告，例如 `072.0_NVDA_NVIDIA_Corporation.md`。

注意：

- 每次运行筛选器前，会清理旧的单股 `.md` 报告，避免不同批次结果混在一起。
- 如果当天的 summary CSV 正被 Excel 或预览占用，程序会自动写一个带时间后缀的新 CSV。
- `reports/` 是运行生成物，默认不建议提交到 Git。

---

## 100 分系统怎么打分

总分 100 分，分成 6 组：

| 组别 | 名称 | 满分 | 关注点 |
|---|---|---:|---|
| A | Buffett 核心质量 | 35 | ROE、ROIC、利润率、FCF 质量、毛利率趋势 |
| B | 财务稳健性 | 15 | 长债/净利润、D/E、利息保障倍数、流动比率 |
| C | 成长性 | 15 | 净利润 CAGR、营收 CAGR、亏损年份、股本变化 |
| D | 估值 | 20 | Forward PE、PEG、FCF Yield、P/FCF、E/P vs 10Y 国债 |
| E | Munger 护城河 | 10 | 营业利润率水平、利润率稳定性、商誉/总资产 |
| F | 技术参考 | 5 | 价格 vs 200 日均线、RSI |

技术指标只占 5 分，因为它只用于择时参考，不应该主导价值判断。

### 硬门槛

进入评分前会先做硬门槛过滤：

- 市值大于 5 亿美元
- ROE 平均值或当前值大于 8%
- 最近年度净利润为正
- D/E 不超过 3.0
- 至少有 2 年历史财务数据
- 近年亏损年份不能太多

硬门槛不通过，默认不会生成单股报告；需要调试时可以加 `--all-reports`。

### 评级解释

| 分数 | 星级 | 含义 |
|---:|---|---|
| 90+ | 5 星 | 极少见的高质量机会，需要深度核实 |
| 80-89 | 4 星 | 优质候选，值得优先研究 |
| 70-79 | 3 星 | 良好，有亮点但仍有短板 |
| 60-69 | 2 星 | 中等，谨慎评估 |
| <60 | 1 星 | 一般，不作为优先研究对象 |

---

## 报告里有哪些内容

每份 Markdown 报告包括：

- 总分、星级、行业、国家、价格、市值
- 推荐理由：强项、短板、估值定位
- 涨跌背景：
  - YTD、近 1 年、近 3 年回报
  - 距 52 周高位
  - 近 3 年最大回撤
  - 高分且大涨的“强势高分提醒”
  - 高分但大跌的“可能原因”，无法判断时写“原因不详”
- 公司简介：Yahoo Finance 英文原文
- 评分明细：A-F 六组每个指标的分数和来源标签
- 关键数据快照
- 技术参考
- 标签说明

---

## AI 影响怎么理解

当前程序不会自动给出最终的 AI 正/负面结论，但报告会展示涨跌背景和新闻标题线索，方便你人工判断。

一般可以这样理解：

- AI 正面影响明显：AI 算力、半导体设备、AI 云、AI 广告效率、芯片设计工具。
- AI 负面或替代风险：传统软件、IT 外包、人力服务、部分会计/税务/设计工作流。
- AI 影响间接或不明确：电商、医疗器械、制药、平台型公司、工业服务。

如果公司高分但大跌，尤其是软件公司，要重点确认是不是 AI 正在削弱商业模式或定价权。

如果公司高分且近几年涨很多，也很有价值，因为这可能说明市场正在验证它的质量，而不是单纯“跌出来的便宜”。

---

## 数据口径注意事项

Yahoo Finance 对 ADR 或海外公司可能返回不同币种：

- 股价/市值币种，例如 USD
- 财报币种，例如 TWD

当两者币种不一致时，程序会避免计算 `FCF Yield` 和 `P/FCF`，防止把不同币种直接相除导致估值虚高。

---

## 项目结构

```text
BuffettLens/
├── stock_info.py              # 日常单股/多股查询工具
├── screener/                  # 100 分价值筛选系统
│   ├── universe.py            # 股票池：NASDAQ 100 / S&P 500
│   ├── fetcher.py             # yfinance 抓取 + SQLite 缓存
│   ├── metrics.py             # 指标计算
│   ├── scorer.py              # 100 分评分
│   ├── reporter.py            # Markdown/CSV 报告
│   └── run_screener.py        # CLI 主入口
├── reports/                   # 运行后生成，默认不提交
├── requirements.txt
├── README.md
└── README_zh.md
```

---

## 常见问题

### 为什么某只股票分数高但跌很多？

可能是估值回落带来安全边际，也可能是业务被永久削弱。报告里的“涨跌背景”会提示可能原因；如果证据不足，会写“原因不详”。

### 为什么某只股票涨很多但分数还高？

如果质量、增长、护城河仍然强，并且估值没有被模型完全判为过热，它仍可能高分。这类公司要重点看未来增长能否继续支撑估值。

### 为什么 ETN 这种好公司分数低？

可能不是公司差，而是估值贵。例如 Forward PE、PEG、FCF Yield、P/FCF 都不满足价值标准时，估值模块会拖低总分。

### 为什么 TSM 分数被修正？

TSM 是 ADR，股价/市值是 USD，财报是 TWD。旧算法曾把 TWD 的 FCF 和 USD 市值直接相除，导致 FCF Yield 虚高。现在已修正：币种不一致时不计算 FCF Yield/P-FCF。
