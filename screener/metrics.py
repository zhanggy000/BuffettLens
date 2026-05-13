"""
指标计算模块
==============
从 fetcher 返回的 raw data dict 中计算所有评分所需的指标.
所有未能计算出的指标返回 None, 由 scorer 优雅处理.
"""

import math
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional


# ---------- 工具函数 ----------

def _safe_div(a, b):
    try:
        if a is None or b is None or b == 0:
            return None
        return float(a) / float(b)
    except (TypeError, ValueError, ZeroDivisionError):
        return None


def _row(stmt: Dict[str, Dict[str, float]], names: List[str], col_index: int = 0) -> Optional[float]:
    """
    在三表 dict 中按候选名查找某一年的值.
    col_index=0 为最新一年, 1 为去年, 以此类推.
    """
    if not stmt:
        return None
    cols = sorted(stmt.keys(), reverse=True)  # 最新在前
    if col_index >= len(cols):
        return None
    col = stmt[cols[col_index]]
    for name in names:
        for key in col.keys():
            if name.lower() == str(key).lower():
                v = col[key]
                if v is None:
                    continue
                return float(v)
    # 模糊匹配
    for name in names:
        for key in col.keys():
            if name.lower() in str(key).lower():
                v = col[key]
                if v is None:
                    continue
                return float(v)
    return None


def _row_series(stmt: Dict[str, Dict[str, float]], names: List[str]) -> List[Optional[float]]:
    """返回该指标的所有年份序列, 从最新到最旧."""
    if not stmt:
        return []
    cols = sorted(stmt.keys(), reverse=True)
    result = []
    for i in range(len(cols)):
        result.append(_row(stmt, names, col_index=i))
    return result


def _cagr(start: float, end: float, years: int) -> Optional[float]:
    """计算年复合增长率. start 和 end 都需要为正."""
    if start is None or end is None or years <= 0:
        return None
    if start <= 0 or end <= 0:
        return None
    try:
        return (end / start) ** (1.0 / years) - 1.0
    except (ValueError, ZeroDivisionError):
        return None


def _mean(values: List[Optional[float]]) -> Optional[float]:
    vs = [v for v in values if v is not None]
    if not vs:
        return None
    return sum(vs) / len(vs)


def _stdev(values: List[Optional[float]]) -> Optional[float]:
    vs = [v for v in values if v is not None]
    if len(vs) < 2:
        return None
    m = sum(vs) / len(vs)
    var = sum((v - m) ** 2 for v in vs) / len(vs)
    return math.sqrt(var)


def _linreg_slope(values: List[Optional[float]]) -> Optional[float]:
    """简单线性回归斜率 (序列从旧到新). 正值 = 上升趋势."""
    vs = [v for v in values if v is not None]
    if len(vs) < 3:
        return None
    n = len(vs)
    xs = list(range(n))
    x_mean = sum(xs) / n
    y_mean = sum(vs) / n
    num = sum((xs[i] - x_mean) * (vs[i] - y_mean) for i in range(n))
    den = sum((xs[i] - x_mean) ** 2 for i in range(n))
    if den == 0:
        return None
    return num / den


# ---------- 技术指标 ----------

def _calc_200ma(prices: List[tuple]) -> Optional[float]:
    if not prices or len(prices) < 50:
        return None
    closes = [p[1] for p in prices[-200:]]
    return sum(closes) / len(closes)


def _calc_rsi(prices: List[tuple], period: int = 14) -> Optional[float]:
    if not prices or len(prices) < period + 1:
        return None
    closes = [p[1] for p in prices[-(period + 1) * 2:]]  # 多取一些
    if len(closes) < period + 1:
        return None
    gains, losses = [], []
    for i in range(1, len(closes)):
        diff = closes[i] - closes[i - 1]
        gains.append(max(diff, 0))
        losses.append(max(-diff, 0))
    # 取最后period个
    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def _price_return_since(prices: List[tuple], since: date) -> Optional[float]:
    if not prices:
        return None
    try:
        latest = float(prices[-1][1])
    except (TypeError, ValueError, IndexError):
        return None

    base = None
    for d_str, close in prices:
        try:
            d = datetime.fromisoformat(str(d_str)[:10]).date()
            if d >= since:
                base = float(close)
                break
        except (TypeError, ValueError):
            continue

    if base is None or base == 0:
        return None
    return (latest - base) / base


def _max_drawdown(prices: List[tuple], years: int = 3) -> Optional[float]:
    if not prices:
        return None
    cutoff = date.today() - timedelta(days=365 * years)
    peak = None
    worst = 0.0
    seen = False
    for d_str, close in prices:
        try:
            d = datetime.fromisoformat(str(d_str)[:10]).date()
            c = float(close)
        except (TypeError, ValueError):
            continue
        if d < cutoff:
            continue
        seen = True
        peak = c if peak is None else max(peak, c)
        if peak and peak > 0:
            worst = min(worst, (c - peak) / peak)
    return worst if seen else None


# ---------- 主计算函数 ----------

# yfinance 字段命名(可能多种)
NAMES_NET_INCOME = ["Net Income", "Net Income Common Stockholders", "Net Income From Continuing Operations"]
NAMES_REVENUE = ["Total Revenue", "Operating Revenue", "Revenue"]
NAMES_OP_INCOME = ["Operating Income", "Operating Revenue"]
NAMES_GROSS_PROFIT = ["Gross Profit"]
NAMES_INTEREST_EXP = ["Interest Expense", "Interest Expense Non Operating"]
NAMES_EBIT = ["EBIT", "Operating Income"]

NAMES_TOTAL_ASSETS = ["Total Assets"]
NAMES_TOTAL_LIAB = ["Total Liabilities Net Minority Interest", "Total Liabilities"]
NAMES_LT_DEBT = ["Long Term Debt", "Long Term Debt And Capital Lease Obligation"]
NAMES_TOTAL_DEBT = ["Total Debt"]
NAMES_EQUITY = ["Stockholders Equity", "Common Stock Equity", "Total Stockholder Equity", "Total Equity Gross Minority Interest"]
NAMES_CASH = ["Cash And Cash Equivalents", "Cash", "Cash Cash Equivalents And Short Term Investments"]
NAMES_GOODWILL = ["Goodwill", "Goodwill And Other Intangible Assets"]
NAMES_SHARES = ["Share Issued", "Ordinary Shares Number", "Common Stock Equity"]
NAMES_CURRENT_ASSETS = ["Current Assets", "Total Current Assets"]
NAMES_CURRENT_LIAB = ["Current Liabilities", "Total Current Liabilities"]

NAMES_FCF = ["Free Cash Flow"]
NAMES_OCF = ["Operating Cash Flow", "Cash Flow From Continuing Operating Activities"]
NAMES_CAPEX = ["Capital Expenditure", "Capital Expenditures"]


def compute_metrics(raw: Dict[str, Any], treasury_10y: float = 4.0) -> Dict[str, Any]:
    """从原始数据 dict 计算所有指标, 返回扁平化的 metrics dict."""
    info = raw.get("info", {}) or {}
    fin = raw.get("financials", {}) or {}
    bs = raw.get("balance_sheet", {}) or {}
    cf = raw.get("cashflow", {}) or {}
    prices = raw.get("price_history", []) or []

    m: Dict[str, Any] = {
        "ticker": raw.get("ticker"),
        "name": info.get("longName") or info.get("shortName"),
        "sector": info.get("sector"),
        "industry": info.get("industry"),
        "country": info.get("country"),
        "summary": info.get("longBusinessSummary"),
        "news": raw.get("news", []) or [],
        "data_source": raw.get("_source") or "yfinance",
    }

    # ---- 基础信息 ----
    m["market_cap"] = info.get("marketCap")
    m["current_price"] = info.get("currentPrice") or info.get("regularMarketPrice")
    m["currency"] = info.get("currency")
    m["financial_currency"] = info.get("financialCurrency")
    m["shares_outstanding"] = info.get("sharesOutstanding")
    m["52w_high"] = info.get("fiftyTwoWeekHigh")
    m["52w_low"] = info.get("fiftyTwoWeekLow")
    m["50ma_info"] = info.get("fiftyDayAverage")
    m["200ma_info"] = info.get("twoHundredDayAverage")
    m["beta"] = info.get("beta")
    m["target_mean"] = info.get("targetMeanPrice")
    m["recommendation"] = info.get("recommendationKey")
    m["dividend_yield"] = info.get("dividendYield")
    m["payout_ratio"] = info.get("payoutRatio")
    m["insider_pct"] = info.get("heldPercentInsiders")

    # ---- A组: Buffett 核心质量 ----

    # ROE 4年: 用 加权平均股东权益 = (期初+期末)/2  作分母 (中国会计准则口径, 与雪球/Wind 一致)
    # 这对快速增长公司很重要 — 期末口径会系统性低估 ROE
    fin_cols = sorted(fin.keys(), reverse=True)
    bs_cols = sorted(bs.keys(), reverse=True)

    roe_series = []
    for i in range(min(len(fin_cols), len(bs_cols), 4)):
        ni = _row(fin, NAMES_NET_INCOME, i)
        eq_end = _row(bs, NAMES_EQUITY, i)
        eq_begin = _row(bs, NAMES_EQUITY, i + 1)  # 上一年期末 = 本年期初
        if eq_begin is not None and eq_end is not None:
            eq_avg = (eq_begin + eq_end) / 2.0
        else:
            eq_avg = eq_end  # 没有期初数据时退化为期末
        roe_series.append(_safe_div(ni, eq_avg))
    m["roe_series"] = roe_series
    m["roe_avg"] = _mean(roe_series)
    m["roe_current"] = roe_series[0] if roe_series else info.get("returnOnEquity")

    # ROIC = NOPAT / 加权平均(Equity + LT Debt). NOPAT ≈ 营业利润 × 0.79
    op_income = _row(fin, NAMES_OP_INCOME, 0)
    eq0 = _row(bs, NAMES_EQUITY, 0)
    eq1 = _row(bs, NAMES_EQUITY, 1)
    ltd0 = _row(bs, NAMES_LT_DEBT, 0) or 0
    ltd1 = _row(bs, NAMES_LT_DEBT, 1) or 0
    if op_income is not None and eq0 is not None:
        invested0 = eq0 + ltd0
        invested1 = (eq1 + ltd1) if eq1 is not None else invested0
        invested_avg = (invested0 + invested1) / 2.0
        if invested_avg > 0:
            m["roic"] = (op_income * 0.79) / invested_avg
        else:
            m["roic"] = None
    else:
        m["roic"] = None

    # 营业利润率 4年序列
    op_margins = []
    for i in range(min(len(fin_cols), 4)):
        op = _row(fin, NAMES_OP_INCOME, i)
        rev = _row(fin, NAMES_REVENUE, i)
        op_margins.append(_safe_div(op, rev))
    m["op_margin_series"] = op_margins
    m["op_margin_avg"] = _mean(op_margins)
    m["op_margin_current"] = op_margins[0] if op_margins else info.get("operatingMargins")

    # 净利率
    m["net_margin"] = info.get("profitMargins")
    if m["net_margin"] is None:
        ni0 = _row(fin, NAMES_NET_INCOME, 0)
        rev0 = _row(fin, NAMES_REVENUE, 0)
        m["net_margin"] = _safe_div(ni0, rev0)

    # FCF / Net Income
    fcf = info.get("freeCashflow") or _row(cf, NAMES_FCF, 0)
    if fcf is None:
        ocf0 = _row(cf, NAMES_OCF, 0)
        capex0 = _row(cf, NAMES_CAPEX, 0)
        if ocf0 is not None and capex0 is not None:
            fcf = ocf0 + capex0  # capex通常为负
    m["fcf"] = fcf
    ni0 = _row(fin, NAMES_NET_INCOME, 0)
    m["net_income"] = ni0
    m["fcf_to_ni"] = _safe_div(fcf, ni0)

    # 毛利率 4年趋势
    gm_series = []
    for i in range(min(len(fin_cols), 4)):
        gp = _row(fin, NAMES_GROSS_PROFIT, i)
        rev = _row(fin, NAMES_REVENUE, i)
        gm_series.append(_safe_div(gp, rev))
    m["gm_series"] = gm_series
    m["gm_current"] = gm_series[0] if gm_series else info.get("grossMargins")
    # 从旧到新算斜率
    m["gm_slope"] = _linreg_slope(list(reversed(gm_series)))

    # ---- B组: 财务稳健性 ----

    # LT Debt / NI
    ltd = _row(bs, NAMES_LT_DEBT, 0)
    m["lt_debt"] = ltd
    m["lt_debt_to_ni"] = _safe_div(ltd, ni0) if (ni0 is not None and ni0 > 0) else None

    # D/E (yfinance给的是百分数)
    de_raw = info.get("debtToEquity")
    if de_raw is not None:
        # yfinance通常返回百分数(如 150 表示 1.5)
        m["debt_to_equity"] = float(de_raw) / 100.0 if de_raw > 5 else float(de_raw)
    else:
        td = info.get("totalDebt") or _row(bs, NAMES_TOTAL_DEBT, 0)
        m["debt_to_equity"] = _safe_div(td, eq0)

    # 利息保障倍数 = EBIT / Interest Expense
    ebit = _row(fin, NAMES_EBIT, 0) or op_income
    int_exp = _row(fin, NAMES_INTEREST_EXP, 0)
    if ebit is not None and int_exp is not None and abs(int_exp) > 0:
        m["interest_coverage"] = ebit / abs(int_exp)
    else:
        m["interest_coverage"] = None

    # 流动比率
    m["current_ratio"] = info.get("currentRatio")
    if m["current_ratio"] is None:
        ca = _row(bs, NAMES_CURRENT_ASSETS, 0)
        cl = _row(bs, NAMES_CURRENT_LIAB, 0)
        m["current_ratio"] = _safe_div(ca, cl)

    # ---- C组: 成长 ----

    # EPS 4yr CAGR (从 net income 估算, 假设股本变化不大)
    ni_series = _row_series(fin, NAMES_NET_INCOME)
    rev_series = _row_series(fin, NAMES_REVENUE)
    m["net_income_series"] = ni_series
    m["revenue_series"] = rev_series

    if len(ni_series) >= 4 and ni_series[0] and ni_series[3]:
        m["ni_cagr_4y"] = _cagr(ni_series[3], ni_series[0], 3)  # 4个点 = 3年
    else:
        m["ni_cagr_4y"] = info.get("earningsGrowth")

    if len(rev_series) >= 4 and rev_series[0] and rev_series[3]:
        m["rev_cagr_4y"] = _cagr(rev_series[3], rev_series[0], 3)
    else:
        m["rev_cagr_4y"] = info.get("revenueGrowth")

    # 净利润负增长年份数
    neg_years = 0
    for v in ni_series:
        if v is not None and v < 0:
            neg_years += 1
    m["ni_negative_years"] = neg_years
    m["ni_history_count"] = sum(1 for v in ni_series if v is not None)

    # 股本变化 (回购/稀释)
    shares_series = _row_series(bs, ["Share Issued", "Ordinary Shares Number"])
    m["shares_series"] = shares_series
    if len(shares_series) >= 2 and shares_series[0] and shares_series[-1]:
        years_apart = len(shares_series) - 1
        m["share_dilution_cagr"] = _cagr(shares_series[-1], shares_series[0], years_apart)
    else:
        m["share_dilution_cagr"] = None

    # ---- D组: 估值 ----

    m["pe_ttm"] = info.get("trailingPE")
    m["pe_forward"] = info.get("forwardPE")
    m["peg"] = info.get("trailingPegRatio") or info.get("pegRatio")
    m["pb"] = info.get("priceToBook")
    m["ps"] = info.get("priceToSalesTrailing12Months")
    m["ev_ebitda"] = info.get("enterpriseToEbitda")
    m["ev_rev"] = info.get("enterpriseToRevenue")

    # FCF Yield 和 P/FCF
    same_currency = (
        not m.get("currency")
        or not m.get("financial_currency")
        or m.get("currency") == m.get("financial_currency")
    )
    m["currency_mismatch"] = not same_currency
    if fcf is not None and m["market_cap"] and same_currency:
        m["fcf_yield"] = fcf / m["market_cap"]
        m["p_to_fcf"] = m["market_cap"] / fcf if fcf > 0 else None
    else:
        m["fcf_yield"] = None
        m["p_to_fcf"] = None

    # Earnings Yield vs 10Y国债
    if m["pe_ttm"] and m["pe_ttm"] > 0:
        m["earnings_yield"] = 1.0 / m["pe_ttm"]
        m["ey_vs_treasury"] = m["earnings_yield"] - (treasury_10y / 100.0)
    else:
        m["earnings_yield"] = None
        m["ey_vs_treasury"] = None

    m["treasury_10y"] = treasury_10y

    # ---- E组: 护城河 ----

    m["op_margin_stdev"] = _stdev(op_margins)
    # 用变异系数 (CV = stdev/mean)
    if m["op_margin_avg"] and m["op_margin_avg"] > 0 and m["op_margin_stdev"] is not None:
        m["op_margin_cv"] = m["op_margin_stdev"] / m["op_margin_avg"]
    else:
        m["op_margin_cv"] = None

    # Goodwill / Total Assets
    gw = _row(bs, NAMES_GOODWILL, 0)
    ta = _row(bs, NAMES_TOTAL_ASSETS, 0)
    m["goodwill"] = gw
    m["total_assets"] = ta
    m["goodwill_ratio"] = _safe_div(gw, ta) if gw is not None else 0  # 没商誉=0是好事

    # ---- F组: 技术指标 ----

    m["ma_200"] = _calc_200ma(prices) or m["200ma_info"]
    m["rsi_14"] = _calc_rsi(prices, 14)

    if m["current_price"] and m["ma_200"]:
        m["price_vs_200ma"] = (m["current_price"] - m["ma_200"]) / m["ma_200"]
    else:
        m["price_vs_200ma"] = None

    if m["current_price"] and m["52w_high"]:
        m["pct_from_52w_high"] = (m["current_price"] - m["52w_high"]) / m["52w_high"]
    else:
        m["pct_from_52w_high"] = None

    if m["current_price"] and m["52w_low"]:
        m["pct_from_52w_low"] = (m["current_price"] - m["52w_low"]) / m["52w_low"]
    else:
        m["pct_from_52w_low"] = None

    today = date.today()
    m["return_ytd"] = _price_return_since(prices, date(today.year, 1, 1))
    m["return_1y"] = _price_return_since(prices, today - timedelta(days=365))
    m["return_3y"] = _price_return_since(prices, today - timedelta(days=365 * 3))
    m["max_drawdown_3y"] = _max_drawdown(prices, years=3)

    return m
