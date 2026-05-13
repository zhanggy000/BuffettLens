"""A股数据适配器 (v2 - 完整三表)
=================
数据源: Sina (财务摘要 + 完整三表) + Baidu (PE/PB)
绕开东方财富 (国内代理下不通).

主要 trade-off (相比美股 yfinance):
- 无 forward PE / PEG -> 用 TTM PE 代替 D1, D2(PEG) 通常 0
- 银行/保险流动资产负债不适用 -> current_ratio 为 None (合理)
其余 LT Debt / 利息保障 / 真 FCF / 股本历史 均已补齐.
"""

from __future__ import annotations

import os
import re
import time
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

try:
    import akshare as ak
except ImportError:
    ak = None


# ---------- ticker 解析 ----------

_CN_RE = re.compile(r"^(\d{6})(?:\.(SS|SH|SZ|SHA|SZA))?$", re.IGNORECASE)


def is_ashare(ticker: str) -> bool:
    return bool(_CN_RE.match((ticker or "").upper().strip()))


def _parse_code(ticker: str) -> Tuple[str, str, str]:
    """Return (6-digit code, exch_prefix_lower 'sh'/'sz', sina_symbol 'sh600519')."""
    m = _CN_RE.match(ticker.upper().strip())
    if not m:
        raise ValueError(f"not an A-share ticker: {ticker}")
    code = m.group(1)
    suffix = (m.group(2) or "").upper()
    if suffix in ("SS", "SH", "SHA"):
        exch = "sh"
    elif suffix in ("SZ", "SZA"):
        exch = "sz"
    else:
        if code.startswith(("6", "9")):
            exch = "sh"
        elif code.startswith(("0", "2", "3")):
            exch = "sz"
        else:
            exch = "sh"
    return code, exch, f"{exch}{code}"


# ---------- spot snapshot 缓存 (一次抓全市场) ----------

_spot_cache: Optional[Dict[str, Dict[str, Any]]] = None
_spot_ts: float = 0
_SPOT_TTL = 600  # 10 分钟


def _require_akshare() -> None:
    if ak is None:
        raise ImportError(
            "akshare is required only for the A-share fallback data source. "
            "Install it with: python -m pip install akshare"
        )


def _get_spot_map() -> Dict[str, Dict[str, Any]]:
    _require_akshare()
    """Sina 全A实时快照, 返回 {sina_symbol -> {name, price, ...}}."""
    global _spot_cache, _spot_ts
    now = time.time()
    if _spot_cache and (now - _spot_ts) < _SPOT_TTL:
        return _spot_cache
    df = ak.stock_zh_a_spot()
    _spot_cache = {}
    for _, r in df.iterrows():
        sym = str(r["代码"])
        _spot_cache[sym] = {
            "name": str(r["名称"]),
            "price": _safe_float(r["最新价"]),
            "high": _safe_float(r["最高"]),
            "low": _safe_float(r["最低"]),
        }
    _spot_ts = now
    return _spot_cache


# ---------- 工具 ----------

def _safe_float(x) -> Optional[float]:
    try:
        if x is None:
            return None
        if isinstance(x, float) and (x != x):
            return None
        return float(x)
    except (TypeError, ValueError):
        return None


def _annual_periods(cols: List[str]) -> List[str]:
    annual = [c for c in cols if str(c).endswith("1231") and re.fullmatch(r"\d{8}", str(c))]
    annual.sort(reverse=True)
    return annual


def _row_by_indicator(df: pd.DataFrame, indicator_name: str) -> Optional[pd.Series]:
    if df is None or df.empty:
        return None
    matched = df[df["指标"] == indicator_name]
    if matched.empty:
        return None
    return matched.iloc[0]


# ---------- 主抓取 ----------

def fetch_ashare(ticker: str) -> Optional[Dict[str, Any]]:
    _require_akshare()
    code, exch, sina_sym = _parse_code(ticker)

    # 1) 实时 (name + price) — 走 Sina 全市场快照, 一次缓存全部
    try:
        spot_map = _get_spot_map()
    except Exception as e:
        print(f"  WARN spot fail (all): {e}")
        spot_map = {}
    spot = spot_map.get(sina_sym, {})
    name = spot.get("name")
    current_price = spot.get("price")

    # 2) 财务摘要 (Sina) — 核心
    try:
        abstract = ak.stock_financial_abstract(symbol=code)
    except Exception as e:
        print(f"  WARN abstract fail {ticker}: {e}")
        abstract = pd.DataFrame()

    period_cols = [c for c in abstract.columns if re.fullmatch(r"\d{8}", str(c))] if not abstract.empty else []
    annual_cols = _annual_periods(period_cols)[:6]

    def _series(indicator: str) -> List[Optional[float]]:
        row = _row_by_indicator(abstract, indicator) if not abstract.empty else None
        if row is None:
            return [None] * len(annual_cols)
        return [_safe_float(row.get(c)) for c in annual_cols]

    ni_series = _series("归母净利润")
    rev_series = _series("营业总收入")
    cogs_series = _series("营业成本")
    eq_series = _series("股东权益合计(净资产)")
    ocf_series = _series("经营现金流量净额")
    goodwill_series = _series("商誉")
    roe_series_pct = _series("净资产收益率(ROE)")
    gm_series_pct = _series("毛利率")
    nm_series_pct = _series("销售净利率")
    da_series_pct = _series("资产负债率")
    expense_ratio_pct = _series("期间费用率")

    # 3) 估值 — Baidu
    pe_ttm = pb = None
    try:
        pe_df = ak.stock_zh_valuation_baidu(symbol=code, indicator="市盈率(TTM)", period="近三年")
        if pe_df is not None and not pe_df.empty:
            pe_ttm = _safe_float(pe_df["value"].iloc[-1])
    except Exception:
        pass
    try:
        pb_df = ak.stock_zh_valuation_baidu(symbol=code, indicator="市净率", period="近三年")
        if pb_df is not None and not pb_df.empty:
            pb = _safe_float(pb_df["value"].iloc[-1])
    except Exception:
        pass

    # 3.5) 完整三表 (Sina) — 补 abstract 缺失的细节字段
    bs_df = is_df = cf_df = None
    try:
        bs_df = ak.stock_financial_report_sina(stock=sina_sym, symbol="资产负债表")
    except Exception as e:
        print(f"  WARN BS fail {ticker}: {e}")
    try:
        is_df = ak.stock_financial_report_sina(stock=sina_sym, symbol="利润表")
    except Exception as e:
        print(f"  WARN IS fail {ticker}: {e}")
    try:
        cf_df = ak.stock_financial_report_sina(stock=sina_sym, symbol="现金流量表")
    except Exception as e:
        print(f"  WARN CF fail {ticker}: {e}")

    def _annual_rows(df) -> pd.DataFrame:
        if df is None or df.empty:
            return pd.DataFrame()
        return df[df["报告日"].astype(str).str.endswith("1231")].copy().sort_values("报告日", ascending=False).head(6)

    bs_a = _annual_rows(bs_df)
    is_a = _annual_rows(is_df)
    cf_a = _annual_rows(cf_df)

    # 4) 价格历史 (Sina, 含 outstanding_share)
    price_history: List[tuple] = []
    shares_outstanding = None
    try:
        end = pd.Timestamp.today().strftime("%Y%m%d")
        start = (pd.Timestamp.today() - pd.Timedelta(days=365 * 5 + 30)).strftime("%Y%m%d")
        hist = ak.stock_zh_a_daily(symbol=sina_sym, start_date=start, end_date=end, adjust="qfq")
        if hist is not None and not hist.empty:
            for _, r in hist.iterrows():
                d = str(r["date"])
                c = _safe_float(r["close"])
                if c is not None:
                    price_history.append((d, c))
            last = hist.iloc[-1]
            shares_outstanding = _safe_float(last.get("outstanding_share"))
            if current_price is None:
                current_price = _safe_float(last.get("close"))
    except Exception as e:
        print(f"  WARN price hist fail {ticker}: {e}")

    if not current_price:
        return None

    # 5) market cap = price × outstanding (Sina 给的是流通股数;贵州茅台流通=总股本, 大多数已全流通)
    market_cap = current_price * shares_outstanding if shares_outstanding else None

    # 52w hi/lo from price history (近 252 个交易日)
    last_252 = price_history[-252:] if len(price_history) >= 50 else price_history
    if last_252:
        closes_252 = [p[1] for p in last_252]
        w52_high = max(closes_252)
        w52_low = min(closes_252)
    else:
        w52_high = w52_low = None

    # ---------- 完整三表 → 各字段年度序列 (从新到旧, 与 abstract 对齐) ----------

    def _bs_val(col: str, idx: int) -> Optional[float]:
        if bs_a.empty or idx >= len(bs_a) or col not in bs_a.columns:
            return None
        return _safe_float(bs_a.iloc[idx][col])

    def _is_val(col: str, idx: int) -> Optional[float]:
        if is_a.empty or idx >= len(is_a) or col not in is_a.columns:
            return None
        return _safe_float(is_a.iloc[idx][col])

    def _cf_val(col: str, idx: int) -> Optional[float]:
        if cf_a.empty or idx >= len(cf_a) or col not in cf_a.columns:
            return None
        return _safe_float(cf_a.iloc[idx][col])

    # 用 annual_cols (来自 abstract) 长度对齐. 若 abstract 没有该年, 但完整三表有, 仍按 1231 对齐.
    n_years = max(len(annual_cols), len(bs_a), len(is_a), len(cf_a))

    lt_debt_series   = [_bs_val("长期借款", i) for i in range(n_years)]
    st_debt_series   = [_bs_val("短期借款", i) for i in range(n_years)]
    curr_assets_series = [_bs_val("流动资产合计", i) for i in range(n_years)]
    curr_liab_series   = [_bs_val("流动负债合计", i) for i in range(n_years)]
    total_assets_series_d = [_bs_val("资产总计", i) for i in range(n_years)]
    total_liab_series_d   = [_bs_val("负债合计", i) for i in range(n_years)]
    # 用 归属母公司股东权益 (跟 归母净利润 匹配口径); 拿不到才退回 总权益
    equity_series_d       = [(_bs_val("归属于母公司股东权益合计", i)
                              or _bs_val("所有者权益(或股东权益)合计", i)) for i in range(n_years)]
    goodwill_series_d     = [_bs_val("商誉", i) for i in range(n_years)]
    cash_series_d         = [_bs_val("货币资金", i) for i in range(n_years)]
    share_capital_series  = [_bs_val("实收资本(或股本)", i) for i in range(n_years)]

    interest_exp_series   = [_is_val("利息费用", i) for i in range(n_years)]
    op_income_series      = [_is_val("营业利润", i) for i in range(n_years)]
    fin_cost_series       = [_is_val("财务费用", i) for i in range(n_years)]
    ni_series_d           = [_is_val("归属于母公司所有者的净利润", i) for i in range(n_years)]
    rev_series_d          = [_is_val("营业总收入", i) or _is_val("营业收入", i) for i in range(n_years)]
    cogs_series_d         = [_is_val("营业成本", i) for i in range(n_years)]

    ocf_series_d   = [_cf_val("经营活动产生的现金流量净额", i) for i in range(n_years)]
    capex_series_d = [_cf_val("购建固定资产、无形资产和其他长期资产所支付的现金", i) for i in range(n_years)]

    # 真 FCF = OCF - CapEx (CapEx 在 Sina 报表里是正值)
    fcf_series_d: List[Optional[float]] = []
    for i in range(n_years):
        if ocf_series_d[i] is not None and capex_series_d[i] is not None:
            fcf_series_d.append(ocf_series_d[i] - capex_series_d[i])
        else:
            fcf_series_d.append(None)

    # ---------- 拼装 info ----------

    roe_latest = roe_series_pct[0] / 100.0 if roe_series_pct and roe_series_pct[0] is not None else None
    net_margin_latest = nm_series_pct[0] / 100.0 if nm_series_pct and nm_series_pct[0] is not None else None
    gross_margin_latest = gm_series_pct[0] / 100.0 if gm_series_pct and gm_series_pct[0] is not None else None
    op_margin_latest = None
    if (gm_series_pct and gm_series_pct[0] is not None
            and expense_ratio_pct and expense_ratio_pct[0] is not None):
        op_margin_latest = (gm_series_pct[0] - expense_ratio_pct[0]) / 100.0

    # D/E:优先用 (LT+ST debt) / Equity (有息债 / 股东权益), 银行口径会偏低 → 合理
    # 拿不到才回退 D/A 推算
    de_ratio = None
    eq0 = equity_series_d[0] if equity_series_d else None
    lt0 = lt_debt_series[0] if lt_debt_series else None
    st0 = st_debt_series[0] if st_debt_series else None
    total_debt_latest = None
    if eq0 and eq0 > 0:
        debt = (lt0 or 0) + (st0 or 0)
        if lt0 is not None or st0 is not None:
            total_debt_latest = debt
            de_ratio = debt / eq0
    if de_ratio is None and da_series_pct and da_series_pct[0] is not None:
        d = da_series_pct[0] / 100.0
        if 0 < d < 1:
            de_ratio = d / (1 - d)

    # Current Ratio
    current_ratio_latest = None
    if (curr_assets_series and curr_liab_series
            and curr_assets_series[0] and curr_liab_series[0]
            and curr_liab_series[0] > 0):
        current_ratio_latest = curr_assets_series[0] / curr_liab_series[0]

    earnings_growth = revenue_growth = None
    if len(ni_series) >= 2 and ni_series[0] and ni_series[1] and ni_series[1] > 0:
        earnings_growth = (ni_series[0] - ni_series[1]) / ni_series[1]
    if len(rev_series) >= 2 and rev_series[0] and rev_series[1] and rev_series[1] > 0:
        revenue_growth = (rev_series[0] - rev_series[1]) / rev_series[1]

    info_dict = {
        "longName": name,
        "shortName": name,
        "sector": None,
        "industry": None,
        "country": "China",
        "currency": "CNY",
        "financialCurrency": "CNY",
        "marketCap": market_cap,
        "currentPrice": current_price,
        "regularMarketPrice": current_price,
        "sharesOutstanding": shares_outstanding,
        "fiftyTwoWeekHigh": w52_high,
        "fiftyTwoWeekLow": w52_low,
        "trailingPE": pe_ttm,
        "forwardPE": pe_ttm,
        "priceToBook": pb,
        "trailingPegRatio": None,
        "pegRatio": None,
        "priceToSalesTrailing12Months": None,
        "enterpriseToEbitda": None,
        "enterpriseToRevenue": None,
        # fetcher 模块对 yfinance 的 debtToEquity 有「>5 视为百分数」的逻辑, 这里直接给倍数 ×100 让其除回
        "debtToEquity": de_ratio * 100 if de_ratio is not None else None,
        "totalDebt": total_debt_latest,
        "currentRatio": current_ratio_latest,
        "profitMargins": net_margin_latest,
        "operatingMargins": op_margin_latest,
        "grossMargins": gross_margin_latest,
        "returnOnEquity": roe_latest,
        "earningsGrowth": earnings_growth,
        "revenueGrowth": revenue_growth,
        "freeCashflow": fcf_series_d[0] if fcf_series_d and fcf_series_d[0] is not None else (ocf_series[0] if ocf_series and ocf_series[0] is not None else None),
        "fiftyDayAverage": None,
        "twoHundredDayAverage": None,
        "beta": None,
        "targetMeanPrice": None,
        "recommendationKey": None,
        "dividendYield": None,
        "payoutRatio": None,
        "heldPercentInsiders": None,
        "longBusinessSummary": "",
    }

    # 收集所有出现过的年份 (1231) 作为 keys, 取并集
    all_year_keys: List[str] = []
    for col in annual_cols:
        all_year_keys.append(f"{col[:4]}-{col[4:6]}-{col[6:8]}")
    for df_a in (bs_a, is_a, cf_a):
        if not df_a.empty:
            for d in df_a["报告日"].astype(str).tolist():
                k = f"{d[:4]}-{d[4:6]}-{d[6:8]}"
                if k not in all_year_keys:
                    all_year_keys.append(k)
    # 排序: 新 → 旧 (与 abstract 一致)
    all_year_keys.sort(reverse=True)

    def _date_to_idx_abstract(date_key: str) -> Optional[int]:
        col = date_key.replace("-", "")
        try:
            return annual_cols.index(col)
        except ValueError:
            return None

    def _date_to_idx_detail(date_key: str, df_a) -> Optional[int]:
        if df_a.empty:
            return None
        col = date_key.replace("-", "")
        dates = df_a["报告日"].astype(str).tolist()
        try:
            return dates.index(col)
        except ValueError:
            return None

    financials: Dict[str, Dict[str, float]] = {}
    balance_sheet: Dict[str, Dict[str, float]] = {}
    cashflow: Dict[str, Dict[str, float]] = {}

    for date_key in all_year_keys:
        idx_abs = _date_to_idx_abstract(date_key)
        idx_is  = _date_to_idx_detail(date_key, is_a)
        idx_bs  = _date_to_idx_detail(date_key, bs_a)
        idx_cf  = _date_to_idx_detail(date_key, cf_a)

        # ---- 利润表 ----
        fin_row: Dict[str, float] = {}
        ni_v = (_is_val("归属于母公司所有者的净利润", idx_is) if idx_is is not None else None) \
               or (ni_series[idx_abs] if idx_abs is not None else None)
        if ni_v is not None:
            fin_row["Net Income"] = ni_v
        rev_v = (_is_val("营业总收入", idx_is) if idx_is is not None else None) \
                or (_is_val("营业收入", idx_is) if idx_is is not None else None) \
                or (rev_series[idx_abs] if idx_abs is not None else None)
        if rev_v is not None:
            fin_row["Total Revenue"] = rev_v
        cogs_v = (_is_val("营业成本", idx_is) if idx_is is not None else None) \
                 or (cogs_series[idx_abs] if idx_abs is not None else None)
        if rev_v is not None and cogs_v is not None:
            fin_row["Gross Profit"] = rev_v - cogs_v
        op_v = _is_val("营业利润", idx_is) if idx_is is not None else None
        if op_v is None and idx_abs is not None:
            # 回退到估算
            if (rev_series[idx_abs] is not None and gm_series_pct[idx_abs] is not None
                    and expense_ratio_pct[idx_abs] is not None):
                op_v = rev_series[idx_abs] * (gm_series_pct[idx_abs] - expense_ratio_pct[idx_abs]) / 100.0
        if op_v is not None:
            fin_row["Operating Income"] = op_v
        # 利息费用: 优先用 利息费用字段; 否则用 财务费用 (正值时近似)
        ie_v = _is_val("利息费用", idx_is) if idx_is is not None else None
        if ie_v is None or ie_v == 0:
            fc_v = _is_val("财务费用", idx_is) if idx_is is not None else None
            if fc_v is not None and fc_v > 0:
                ie_v = fc_v
        if ie_v is not None:
            fin_row["Interest Expense"] = ie_v
        if fin_row:
            financials[date_key] = fin_row

        # ---- 资产负债表 ----
        bs_row: Dict[str, float] = {}
        eq_v = (_bs_val("归属于母公司股东权益合计", idx_bs) if idx_bs is not None else None) \
               or (_bs_val("所有者权益(或股东权益)合计", idx_bs) if idx_bs is not None else None) \
               or (eq_series[idx_abs] if idx_abs is not None else None)
        if eq_v is not None:
            bs_row["Stockholders Equity"] = eq_v
        ta_v = _bs_val("资产总计", idx_bs) if idx_bs is not None else None
        if ta_v is None and idx_abs is not None and eq_v and da_series_pct[idx_abs] is not None:
            d = da_series_pct[idx_abs] / 100.0
            if 0 < d < 1:
                ta_v = eq_v / (1 - d)
        if ta_v is not None:
            bs_row["Total Assets"] = ta_v
        tl_v = _bs_val("负债合计", idx_bs) if idx_bs is not None else None
        if tl_v is None and ta_v is not None and eq_v is not None:
            tl_v = ta_v - eq_v
        if tl_v is not None:
            bs_row["Total Liabilities Net Minority Interest"] = tl_v
        lt_v = _bs_val("长期借款", idx_bs) if idx_bs is not None else None
        if lt_v is not None:
            bs_row["Long Term Debt"] = lt_v
        st_v = _bs_val("短期借款", idx_bs) if idx_bs is not None else None
        if lt_v is not None or st_v is not None:
            bs_row["Total Debt"] = (lt_v or 0) + (st_v or 0)
        gw_v = (_bs_val("商誉", idx_bs) if idx_bs is not None else None) \
               or (goodwill_series[idx_abs] if idx_abs is not None else None)
        if gw_v is not None:
            bs_row["Goodwill"] = gw_v
        ca_v = _bs_val("流动资产合计", idx_bs) if idx_bs is not None else None
        if ca_v is not None:
            bs_row["Current Assets"] = ca_v
        cl_v = _bs_val("流动负债合计", idx_bs) if idx_bs is not None else None
        if cl_v is not None:
            bs_row["Current Liabilities"] = cl_v
        cash_v = _bs_val("货币资金", idx_bs) if idx_bs is not None else None
        if cash_v is not None:
            bs_row["Cash And Cash Equivalents"] = cash_v
        # 股本 (用于稀释/回购检测)
        sc_v = _bs_val("实收资本(或股本)", idx_bs) if idx_bs is not None else None
        if sc_v is not None:
            bs_row["Share Issued"] = sc_v
            bs_row["Ordinary Shares Number"] = sc_v
        if bs_row:
            balance_sheet[date_key] = bs_row

        # ---- 现金流量表 ----
        cf_row: Dict[str, float] = {}
        ocf_v = (_cf_val("经营活动产生的现金流量净额", idx_cf) if idx_cf is not None else None) \
                or (ocf_series[idx_abs] if idx_abs is not None else None)
        capex_v = _cf_val("购建固定资产、无形资产和其他长期资产所支付的现金", idx_cf) if idx_cf is not None else None
        if ocf_v is not None:
            cf_row["Operating Cash Flow"] = ocf_v
            if capex_v is not None:
                cf_row["Capital Expenditure"] = -capex_v  # yfinance 约定 CapEx 为负
                cf_row["Free Cash Flow"] = ocf_v - capex_v
            else:
                cf_row["Free Cash Flow"] = ocf_v  # 退化
                cf_row["Capital Expenditure"] = 0.0
        if cf_row:
            cashflow[date_key] = cf_row

    return {
        "ticker": ticker,
        "info": info_dict,
        "financials": financials,
        "balance_sheet": balance_sheet,
        "cashflow": cashflow,
        "price_history": price_history,
        "news": [],
        "_source": "akshare",
    }


def fetch_ashare_with_retry(ticker: str, retries: int = 2, delay: float = 1.5) -> Optional[Dict[str, Any]]:
    last = None
    for attempt in range(retries + 1):
        try:
            r = fetch_ashare(ticker)
            if r is not None:
                return r
        except Exception as e:
            last = e
        if attempt < retries:
            time.sleep(delay * (attempt + 1))
    if last:
        print(f"  WARN ashare fetch failed {ticker}: {last}")
    return None
