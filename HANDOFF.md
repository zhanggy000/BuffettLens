# BuffettLens Screener - 项目交接文档

> 给接手开发者（Codex）的完整说明。读完这份就能继续。

---

## 一、项目目标

在 `BuffettLens` 仓库下，**新增**一个独立的筛选器子模块 `screener/`，用来：

1. **批量扫描美股**（先支持 NASDAQ 100 / S&P 500，未来可扩到全市场）
2. **按价值投资标准（巴菲特 + 芒格为核心 + Graham/Lynch/Fisher/Damodaran 等流派）打分**，满分 100
3. **层层筛选**：先用硬门槛淘汰垃圾，再对幸存者打分
4. **为每只通过的股票生成单独的 Markdown 分析报告**，文件名带分数前缀（如 `092.5_AAPL_Apple.md`），按文件名排序即按分数排序，用户可一只一只看

### 用户的明确要求

- ✅ **不要动 `stock_info.py`**（日常查询用，保持原状）
- ✅ **新写一个独立脚本**（位于 `screener/`）
- ✅ **用免费数据源**（yfinance），允许慢、允许跑一晚上
- ✅ **支持请求间隔**（防 yfinance 限流封禁，默认 2 秒）
- ✅ **第一阶段只跑 NDX100 / S&P500**，未来可扩展
- ✅ **不要做大工程**，重点是评分机制和分层筛选要做扎实
- ✅ **每只通过的股票一个 .md 报告**，文件名带 3 位补零分数前缀（如 `092.5_TICKER.md`）便于按字母序排序
- ✅ **总览 CSV**（按分数降序）
- ✅ **每个指标都标注来源**（🅑 Buffett / 🅜 Munger / 🅖 Graham / 🅛 Lynch / 🅓 Damodaran / ⚪ 通用 / ❌🅑 巴菲特反对的技术指标）

---

## 二、目录结构

```
BuffettLens/
├── stock_info.py              ← 用户日常脚本，禁止改动
├── README.md / README_zh.md   ← 项目主 README
├── requirements.txt           ← 已含 yfinance
├── HANDOFF.md                 ← 本文档
│
├── screener/                  ← 新增的筛选器（本次交付）
│   ├── __init__.py
│   ├── universe.py            ✅ 完成
│   ├── fetcher.py             ✅ 完成
│   ├── metrics.py             ✅ 完成
│   ├── scorer.py              ✅ 完成
│   ├── reporter.py            ✅ 完成
│   ├── run_screener.py        ✅ 完成（主入口）
│   └── cache/                 ← SQLite 缓存目录（运行后自动生成）
│       └── data.db
│
└── reports/                   ← 报告输出目录（运行后自动生成）
    ├── _summary_YYYY-MM-DD.csv          ← 总览 CSV
    ├── 092.5_AAPL_Apple_Inc.md
    ├── 089.0_MSFT_Microsoft.md
    └── ...
```

---

## 三、Python 环境

用户使用的 Python 解释器路径：

```
C:\Users\EDY\AppData\Local\Python\bin\python.exe
```

已安装的依赖：`yfinance`、`pandas`（yfinance 依赖）。

运行方式（从 `BuffettLens/` 根目录）：

```powershell
# 测试 5 只
& "C:\Users\EDY\AppData\Local\Python\bin\python.exe" -m screener.run_screener --tickers AAPL,MSFT,GOOGL,KO,JNJ

# NDX100（约5-10分钟）
& "C:\Users\EDY\AppData\Local\Python\bin\python.exe" -m screener.run_screener --universe ndx100

# S&P500（约25分钟）
& "C:\Users\EDY\AppData\Local\Python\bin\python.exe" -m screener.run_screener --universe sp500

# 强制刷新缓存
& "C:\Users\EDY\AppData\Local\Python\bin\python.exe" -m screener.run_screener --universe ndx100 --force-refresh

# 调整请求间隔
& "C:\Users\EDY\AppData\Local\Python\bin\python.exe" -m screener.run_screener --universe sp500 --delay 3
```

---

## 四、评分体系（满分 100）

### 硬门槛（不通过直接淘汰，不生成报告）

实现在 `scorer.hard_gates()`：

| # | 指标 | 标准 |
|---|------|------|
| H1 | 市值 | > $500M |
| H2 | ROE 4年平均（或当期） | > 8% |
| H3 | 最近年度净利润 | > 0 |
| H4 | D/E | < 3.0 |
| H5 | 历史财报数据 | ≥ 2 年 |
| H6 | 近年净利润亏损年份 | < 3 |

### 100 分评分体系

| 组 | 名称 | 满分 | 维度 |
|----|------|------|------|
| 🅑 A | Buffett 核心质量 | **35** | ROE/ROIC/营业利润率/净利率/FCF质量/毛利率趋势 |
| 🛡️ B | 财务稳健性 | **15** | 长债/D-E/利息保障/流动比率 |
| 📈 C | 成长性 | **15** | 4年净利CAGR/4年营收CAGR/负增长年份/股本变化 |
| 💵 D | 估值 | **20** | Forward PE/PEG/FCF Yield/P-FCF/E-P vs 10Y国债 |
| 🏰 E | Munger 护城河 | **10** | 营业利润率绝对水平/稳定性CV/商誉占比 |
| 📊 F | 技术参考 | **5** | 价格 vs 200MA / RSI(14) |
| | **合计** | **100** | |

### A 组：🅑 Buffett 核心质量（35）

| ID | 指标 | 标签 | 分级 | 满分 |
|----|------|------|------|------|
| A1 | ROE 4年平均 | 🅑 | >20%→8, >15%→6, >10%→3 | 8 |
| A2 | ROIC | 🅑🅜 | >15%→7, >12%→5, >8%→2 | 7 |
| A3 | 营业利润率 4年平均 | 🅑🅜 | >25%→6, >15%→4, >10%→2 | 6 |
| A4 | 净利率 | 🅑 | >20%→5, >10%→3, >5%→1 | 5 |
| A5 | FCF / 净利润 | 🅑 | >100%→5, >80%→3, >50%→1 | 5 |
| A6 | 毛利率趋势 | 🅑 | 上升→4, 稳定→2, 下滑→0 | 4 |

### B 组：🛡️ 财务稳健（15）

| ID | 指标 | 标签 | 分级 | 满分 |
|----|------|------|------|------|
| B1 | 长债 / 净利润 | 🅑 | <2→5, <5→3, <8→1 | 5 |
| B2 | D/E | 🅑 | <0.5→4, <1→2, <1.5→1 | 4 |
| B3 | 利息保障倍数 | 🅖 | >20→3, >10→2, >5→1 | 3 |
| B4 | 流动比率 | 🅖 | >2→3, >1.5→2, >1→1 | 3 |

### C 组：📈 成长（15）

| ID | 指标 | 标签 | 分级 | 满分 |
|----|------|------|------|------|
| C1 | 净利润 4年CAGR | 🅑 | >15%→5, >10%→3, >5%→1 | 5 |
| C2 | 营收 4年CAGR | 🅛 | >10%→4, >5%→2 | 4 |
| C3 | 净利润负增长年份 | 🅑 | 0→3, 1→2, 2→1 | 3 |
| C4 | 股本年化变化 | 🅜 | 回购→3, 持平→2, <2%稀释→1 | 3 |

### D 组：💵 估值（20）

| ID | 指标 | 标签 | 分级 | 满分 |
|----|------|------|------|------|
| D1 | Forward P/E | ⚪ | <15→5, <20→3, <25→1 | 5 |
| D2 | PEG | 🅛 | <1→4, <1.5→2, <2→1 | 4 |
| D3 | FCF Yield | 🅓 | >6%→4, >4%→2, >2%→1 | 4 |
| D4 | P/FCF | 🅑 | <15→4, <25→2, <40→1 | 4 |
| D5 | E/P - 10Y国债 | 🅑 | >+3%→3, >0%→1 | 3 |

### E 组：🏰 Munger 护城河（10）

| ID | 指标 | 标签 | 分级 | 满分 |
|----|------|------|------|------|
| E1 | 营业利润率水平（定价权） | 🅜 | >25%→4, >18%→2, >12%→1 | 4 |
| E2 | 营业利润率稳定性 (CV) | 🅑🅜 | <0.10→3, <0.20→2, <0.30→1 | 3 |
| E3 | 商誉 / 总资产 | 🅜 | <10%→3, <30%→2, <50%→1 | 3 |

### F 组：📊 技术参考（5）非 Buffett 派

| ID | 指标 | 标签 | 分级 | 满分 |
|----|------|------|------|------|
| F1 | 价格 vs 200MA | ❌🅑 | -20%~+5%→3, <-20%→2, +5~20%→1 | 3 |
| F2 | RSI(14) | ❌🅑 | 30-50→2, 50-70→1, 其他→0 | 2 |

### 评级映射

| 分数 | 星级 | 描述 |
|------|------|------|
| 90+ | ⭐⭐⭐⭐⭐ | 卓越 - 罕见的巴菲特级机会 |
| 80-89 | ⭐⭐⭐⭐ | 优质 - 值得深度研究 |
| 70-79 | ⭐⭐⭐ | 良好 - 有亮点但有短板 |
| 60-69 | ⭐⭐ | 中等 - 需谨慎评估 |
| <60 | ⭐ | 一般 - 不建议研究 |

---

## 五、输出规格

### 1. 单股报告

- **路径**: `reports/{NNN.N}_{TICKER}_{安全文件名}.md`
- **分数补零到 5 位**：如 `092.5`、`100.0`（按字母序 = 按分数序）
- **结构**:
  1. 标题 + 总分 + 星级
  2. 行业 / 国家 / 价格 / 市值
  3. 📌 推荐理由（自动生成的强项 / 短板 / 估值定位）
  4. 公司简介
  5. 📊 评分明细（按 A-F 6 组，每组带进度条 + 表格）
  6. 💰 关键数据快照（PE/PB/ROE/ROIC/利润率等）
  7. 📈 技术参考（200MA / RSI / 52周高低 / 分析师推荐）
  8. 🏷️ 标签说明（🅑🅜🅖🅛🅓⚪❌🅑）

### 2. 总览 CSV

- **路径**: `reports/_summary_YYYY-MM-DD.csv`
- **排序**: 按总分降序
- **列**: rank, ticker, name, sector, total_score, 6个分项得分, 关键财务指标, passed/fail_reasons

---

## 六、已完成的代码

### ✅ `screener/__init__.py`
版本声明。

### ✅ `screener/universe.py`
- 从维基百科抓取 S&P 500 / NASDAQ 100 成分股
- 内置 fallback 列表（离线时用）
- 函数：`get_sp500()`、`get_ndx100()`、`get_universe(name)`

### ✅ `screener/fetcher.py`
- yfinance 抓取：info / financials / balance_sheet / cashflow / quarterly / 价格历史
- SQLite 缓存（24 小时 TTL），路径 `screener/cache/data.db`
- 函数：`fetch_stock(ticker, force_refresh)`、`fetch_batch()`、`get_10y_treasury_yield()`

### ✅ `screener/metrics.py`
从原始数据计算所有指标。
- `compute_metrics(raw, treasury_10y)` 返回扁平 dict
- 内含：ROIC（NOPAT 公式）、4 年 CAGR、营业利润率序列 / CV、毛利率斜率（线性回归）、200MA、RSI(14)、FCF Yield、E/P vs 国债、商誉占比等
- 数据缺失时优雅返回 None，由 scorer 处理

### ✅ `screener/scorer.py`
- `hard_gates(metrics)` → `(passed: bool, reasons: list)`
- `score(metrics)` → 完整评分 dict，含 6 组分项明细
- `rating_stars(total)` → 星级

### ✅ `screener/reporter.py`
- `gen_report(m, scoring)` → 生成单股 Markdown 字符串
- `save_report()` → 保存到 `reports/`，文件名带分数前缀
- `save_summary_csv()` → 总览 CSV
- `_gen_recommendation_reason()` → 自动生成推荐理由

### ✅ `screener/run_screener.py`
主入口，CLI 参数：
- `--universe / -u`: sp500 / ndx100 / both
- `--tickers / -t`: 自定义列表
- `--delay / -d`: 请求间隔
- `--force-refresh / -f`: 强制刷新
- `--min-score`: 最低分阈值（默认 60）
- `--all-reports`: 全部生成（调试）
- `--limit`: 限制数量（测试用）

---

## 七、还没做（请 Codex 继续）

### 🔴 P0 - 必做（验证 + 修 bug）

1. **跑一次小测试集**，确认全链路正常：
   ```powershell
   & "C:\Users\EDY\AppData\Local\Python\bin\python.exe" -m screener.run_screener --tickers AAPL,MSFT,GOOGL,KO,JNJ
   ```
   预期：
   - 5 只全部抓取成功
   - `reports/` 目录下生成 5 份 .md 报告 + 1 份 CSV
   - 文件名格式形如 `087.5_AAPL_Apple_Inc.md`
   - 报告内容完整，无 `N/A` 比例过高的情况

2. **修预期会遇到的问题**：
   - yfinance 字段名变化（`Long Term Debt` vs `LongTermDebt` vs `Long Term Debt And Capital Lease Obligation` 等），`metrics.NAMES_*` 常量可能要扩充
   - yfinance 偶尔返回 NaN 或空 DataFrame，可能在某些指标上抛错 —— 加 try/except 兜底
   - 维基百科表格结构如果变 → `universe._try_wiki_table()` 的 match 逻辑可能要调
   - SQLite 缓存的数据 JSON 序列化（财务数据中可能有 numpy.int64 / Timestamp）→ 已用 `default=str`，但要验证读回后类型正确

3. **跑一次 NDX100 完整测试**，确认 100 只 5-10 分钟内能跑完，至少有 10-30 只通过硬门槛生成报告。

### 🟡 P1 - 改进项（按优先级）

4. **报告中的"推荐理由"目前比较模板化**，可改进：
   - 加入"风险提示"段落（基于失分项自动生成，比如 "估值过高"、"杠杆偏高"、"成长性弱"）
   - 加入"操作建议"段落（基于 PEG 和 FCF Yield 给出 强烈买入 / 可分批 / 观望 / 避免 的价位区间）

5. **行业相对比较**（当前 E1 用绝对值，更严谨的是 vs 行业中位数）：
   - 两遍扫描：先收集所有数据，算每个行业的中位数，再二次评分
   - 或维护一个静态的 `industry_baselines.json`

6. **增加更多指标**（如果 yfinance 数据可得）：
   - Piotroski F-Score 完整版（9 项）—— 当前只用了部分
   - Beneish M-Score（财务造假检测）
   - Altman Z-Score（破产预测）
   - 内部人近期买卖（yfinance 有 `insider_transactions` 字段）
   - 分析师预期变化趋势

7. **报告输出增强**：
   - 在 Markdown 报告里加一个 **Plotly / matplotlib 图**（保存为 PNG 嵌入），展示 5 年 ROE / 营业利润率 / FCF 趋势
   - 输出 HTML 版本（更美观，可在浏览器看）

8. **性能优化**：
   - 用 `concurrent.futures` 并发抓取（yfinance 限流要小心，建议 max_workers=3）
   - 缓存命中时跳过 sleep（当前已实现）

### 🟢 P2 - 远期（不急）

9. **扩展到全美股**：
   - 用 NASDAQ Trader FTP 或 SEC 公司列表（约 5000+ 股）
   - 一晚上跑完，需要更好的错误恢复（断点续跑）

10. **接入付费 API**（如果 yfinance 不够用）：
    - Financial Modeling Prep ($14/月) - 有 30 年历史
    - Alpha Vantage / Polygon

11. **回测**：
    - 给定历史日期，看当时高分股的后续表现
    - 验证评分体系的预测力

12. **Web 仪表盘**：
    - Streamlit / Flask 把 reports/ 渲染成可点击的网页

---

## 八、关键设计决策（不要轻易改）

1. **文件名分数前缀补零到 5 位**（`092.5` 而非 `92.5`）—— 按字母序就是按分数序，用户能在文件夹里直接排序看。**不要改成下划线分隔或其他格式**。

2. **每个指标都带"出处标签"**（🅑🅜🅖🅛🅓⚪❌🅑）—— 用户的核心要求是"如果是巴菲特/芒格的指标就标清楚"。新增指标必须带标签。

3. **❌🅑 技术指标只占 5 分**（不是 0 分也不是 20 分）—— 用户明确要求保留但不主导，因为巴菲特反对技术分析，所以分数低且标 ❌。

4. **硬门槛宽松一点（ROE>8%）而非严苛（>15%）**—— 8% 是底线，避免漏掉周期性低谷的好公司。严格的"巴菲特级"由评分体现，不由门槛体现。

5. **不要动 `stock_info.py`** —— 用户日常使用的脚本。

6. **缓存 24 小时**—— 财务数据日更足够，跑批中途断也能续。

---

## 九、关键文件清单

```
screener/__init__.py              ~3 行
screener/universe.py             ~100 行
screener/fetcher.py              ~170 行
screener/metrics.py              ~310 行
screener/scorer.py               ~310 行
screener/reporter.py             ~240 行
screener/run_screener.py         ~190 行
```

总计约 **1300 行** Python。

---

## 十、立即可执行的下一步

```powershell
cd C:\Users\EDY\Desktop\BuffettLens

# 1. 快速烟囱测试（5只，约15秒）
& "C:\Users\EDY\AppData\Local\Python\bin\python.exe" -m screener.run_screener --tickers AAPL,MSFT,KO,JNJ,BRK-B

# 2. 检查输出
dir reports

# 3. 打开最高分报告查看
# (在 Windows 资源管理器里打开 reports 文件夹，按文件名降序排)

# 4. 如果都正常，跑NDX100
& "C:\Users\EDY\AppData\Local\Python\bin\python.exe" -m screener.run_screener --universe ndx100
```

如果第 1 步有报错，**先修 bug 再做改进项**。最可能出问题的地方：

- `metrics.py` 中字段名匹配失败（财报某些行项目找不到）
- yfinance 某些 ticker 返回空数据
- SQLite 缓存读回时 JSON 反序列化出错

调试时可在 `run_screener.run()` 里 `import traceback; traceback.print_exc()` 已经写好了。

---

## 十一、给 Codex 的话

- 用户的 Python 路径写在 `C:\Users\EDY\.claude\CLAUDE.md` 的全局规则里（财务数据**不要凭记忆**给，必须跑脚本）
- 用户偏好简洁、可用、能跑通 > 完美
- 用户语言：中文
- 不要在没确认的情况下改动 `stock_info.py`
- 不要把 stock_info.py 的输出风格搬到 screener 报告里（screener 是 Markdown，stock_info 是 CLI 文本）

完成 P0 后请告诉用户："基础筛选器已跑通，N 只通过硬门槛，最高分 X 分，可以在 reports/ 文件夹按名字降序查看。"
