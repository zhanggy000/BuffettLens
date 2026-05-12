# 🔍 BuffettLens (巴菲特透镜)

> 一个用巴菲特和芒格价值投资视角看股票的实时数据查询工具。

**[English README](./README.md)**

![Python](https://img.shields.io/badge/python-3.10+-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)
![数据源](https://img.shields.io/badge/数据源-Yahoo%20Finance-purple.svg)

---

## ✨ 功能特点

- 📊 **实时市场数据** —— 通过Yahoo Finance获取(无需API key)
- 💰 **30+ 关键指标** —— Forward PE、PEG、ROE、自由现金流、各种利润率、负债率
- 📋 **最近4季度财报** —— 营收、毛利、营业利润、净利润
- 👔 **分析师共识** —— 评级、目标价、上行空间
- 🎯 **巴菲特评分卡** —— 7项价值投资标准筛选
- 💾 **JSON导出** —— 方便历史追踪和对比
- 🌐 **跨平台** —— 支持 macOS、Linux、Windows

---

## 📦 安装

### 环境要求
- Python 3.10 或更高版本
- pip (Python包管理器)

### 安装依赖

```bash
pip install yfinance
```

或者用 `requirements.txt`:

```bash
pip install -r requirements.txt
```

---

## 🚀 使用方法

### macOS / Linux (终端)

```bash
# 查询单只股票
python3 stock_info.py NVDA

# 查询多只股票
python3 stock_info.py NVDA GOOGL MSFT

# 显示巴菲特评分卡(推荐)
python3 stock_info.py NVDA --buffett

# 保存数据到 JSON
python3 stock_info.py NVDA GOOGL --save

# 交互模式(不传参数)
python3 stock_info.py
```

### Windows (PowerShell)

```powershell
# 查询单只股票
python stock_info.py NVDA

# 多只股票 + 巴菲特评分
python stock_info.py NVDA GOOGL MSFT --buffett

# 保存到 JSON
python stock_info.py NVDA --save
```

### Windows (CMD 命令提示符)

```cmd
python stock_info.py NVDA --buffett
```

### 如果 `python` 不在 PATH 中

**macOS/Linux:**
```bash
/usr/local/bin/python3 stock_info.py NVDA
```

**Windows (用完整路径):**
```powershell
& "C:\Users\你的用户名\AppData\Local\Programs\Python\Python311\python.exe" stock_info.py NVDA
```

---

## 📋 输出示例

```
======================================================================
  🔍 NVDA
======================================================================

📊 公司: NVIDIA Corporation
🏢 行业: Semiconductors | 板块: Technology
🌍 国家: United States
👥 员工: 42,000

💰 价格
  当前价:    $219.44 🔺 +1.96%
  52周高:    $222.30
  52周低:    $124.47
  50日均线:  $189.50
  200日均线: $184.96

📈 估值
  市值:        $5.33T
  企业价值:    $5.28T
  TTM PE:      44.88
  Forward PE:  19.44
  PEG:         0.68
  P/B:         33.91
  EV/EBITDA:   39.64

💵 盈利能力
  EPS (TTM):    $4.89
  EPS Forward:  $11.29
  毛利率:       71.07%
  净利率:       55.60%
  ROE:          101.48%
  ROA:          51.19%

📊 增长 (YoY)
  季度营收增长: 73.20%
  季度利润增长: 95.60%

💸 现金流
  经营现金流:   $102.72B
  自由现金流:   $58.13B

🎯 巴菲特/芒格 评分卡
  ❌ PE比率 44.9 太高
  ✅ ROE 101.5% > 15%
  ✅ 净利率 55.6% > 10%
  ✅ 负债/股本 7% < 100%
  ✅ 自由现金流 $58.13B > 0
  ✅ 营收增长 73.2% > 5%
  ✅ 价格未过度高于200日均线

  📊 总分: 6/7  → 🌟 高度符合巴菲特标准
```

---

## 🎯 巴菲特评分卡说明

脚本基于巴菲特和芒格的价值投资原则,用7项标准评估股票:

| # | 指标 | 阈值 | 为什么重要 |
|---|------|------|----------|
| 1 | TTM PE | < 25 | 避免为盈利付出过高价格 |
| 2 | ROE | > 15% | 优质企业能用资本赚高回报 |
| 3 | 净利率 | > 10% | 体现定价权和运营效率 |
| 4 | 负债/股本 | < 100% | 财务抗风险能力 |
| 5 | 自由现金流 | > 0 | 公司真正产生现金 |
| 6 | 营收增长 | > 5% | 业务在扩张,不是停滞 |
| 7 | 价格 vs 200日均线 | < 120% | 避免在高点买入 |

**得分解读:**
- 🌟 **6-7 / 7**: 高度符合巴菲特标准
- 👍 **4-5 / 7**: 部分符合,值得关注
- ⚠️ **< 4 / 7**: 不符合巴菲特标准

> ⚠️ **免责声明**: 巴菲特评分卡是定量起点,不是完整分析。巴菲特更强调定性因素(护城河、管理层、可预测性),这些脚本无法完全捕捉。请始终做自己的研究。

---

## 📊 完整指标列表

<details>
<summary>点击展开查看所有指标</summary>

### 公司信息
- 公司名、行业、板块、国家、员工数

### 价格数据
- 当前价、涨跌幅
- 52周高/低
- 50日/200日移动平均线

### 估值倍数
- 市值、企业价值
- TTM PE、Forward PE
- PEG
- P/B (市净率)
- P/S (市销率)
- EV/EBITDA
- EV/营收

### 盈利能力
- EPS (TTM、Forward)
- 毛利率、营业利润率、净利率
- ROE (股本回报率)
- ROA (资产回报率)

### 增长 (YoY)
- 季度营收增长
- 季度利润增长
- EPS增长

### 股息 (如有)
- 股息率 (用 年股息/价格 计算)
- 年股息
- 派息比率
- 5年平均收益率

### 资产负债表
- 总现金、总债务
- 负债/股本比率
- 流动比率、速动比率
- 每股账面价值

### 现金流
- 经营现金流
- 自由现金流

### 分析师覆盖
- 共识推荐
- 均值/最高/最低目标价
- 相对当前价的上行空间
- 覆盖的分析师数量

### 财务报表
- 最近4个季度的: 营收、毛利、营业利润、净利润

### 业务摘要
- 400字符的业务描述节选

</details>

---

## 🛠️ 命令行参数

| 参数 | 说明 |
|------|------|
| `tickers` | 一个或多个股票代码 (例如 `NVDA GOOGL MSFT`) |
| `--buffett` | 显示巴菲特7点评分卡 |
| `--save` | 导出所有查询数据到带时间戳的JSON文件 |
| `-h`, `--help` | 显示帮助信息 |

---

## 💡 使用场景

1. **买前研究**: 快速用价值投资标准评估一只股票
2. **持仓回顾**: 每月跑一次所有持仓,跟踪质量变化
3. **横向对比**: 同时比较多只候选股
4. **历史追踪**: 用 `--save` 建立个人数据库
5. **财报季**: 财报发布后跑脚本看最新指标

---

## ⚠️ 数据源说明

- **来源**: Yahoo Finance (通过 `yfinance` Python库)
- **延迟**: 交易时段约 **15-20分钟延迟**
- **盘后**: 价格不更新; 基本面数据(PE、财报)保持准确
- **实时数据**: 需要付费API如 Polygon、IEX Cloud、Alpaca
- **长期投资者**: 15分钟延迟数据**完全够用**

---

## 🐛 常见问题

### "ModuleNotFoundError: No module named 'yfinance'"
```bash
pip install yfinance
# 或者
python -m pip install yfinance
```

### 某些字段显示 "N/A"
- Yahoo Finance对部分外国股票(如TSM)或刚上市公司偶尔缺失数据
- 脚本对缺失数据做了优雅处理 —— 受影响字段显示 `N/A`

### 最新季度财报显示 `$nan`
- Yahoo Finance可能尚未处理最新季报
- 等几天再查,或使用上一季度数据

### "Connection error" 或速率限制
- Yahoo Finance有非正式速率限制
- 查询很多股票时,可在循环中加 `time.sleep(1)`
- 考虑非高峰时段运行

---

## 📁 项目结构

```
BuffettLens/
├── stock_info.py        # 主脚本
├── README.md            # 英文文档
├── README_zh.md         # 中文文档(本文件)
├── requirements.txt     # Python依赖
├── LICENSE              # MIT 协议
└── .gitignore           # Git忽略规则
```

---

## 🤝 贡献

欢迎提交PR!一些可以改进的方向:

- [ ] 添加对比模式(多只股票并排表格)
- [ ] 添加历史PE图表
- [ ] 添加ETF持仓分解
- [ ] 添加内部人士交易数据
- [ ] 添加期权数据
- [ ] 国际化(支持纯英文输出)
- [ ] CSV 导出选项
- [ ] Discord/Telegram bot集成

---

## 📜 协议

[MIT](./LICENSE) —— 可自由使用、修改、分发。

---

## 🙏 致谢

- **巴菲特和芒格** —— 启发评分卡的永恒投资智慧
- **[yfinance](https://github.com/ranaroussi/yfinance)** —— 强大的Python库,本工具的核心
- **Yahoo Finance** —— 提供免费金融数据

---

## 📬 作者

作为个人价值投资工具开发。源于一个认知:**TTM PE是后视镜,Forward PE才是前进灯** —— 实时数据永远胜过大模型的过时记忆。

> "风险来自于你不知道自己在做什么。"
> —— 沃伦·巴菲特

> "反过来想,总是反过来想。"
> —— 查理·芒格

⭐ **如果这个工具帮你做出了更好的投资决策,请给项目点个 Star!**
