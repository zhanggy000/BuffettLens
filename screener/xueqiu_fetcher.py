"""雪球数据适配器
================
通过 xueqiu.com v5 公开 API 抓取 A 股数据,封装成 yfinance fetcher 兼容的 raw dict.

优势 vs akshare(新浪):
- avg_roe 是中国会计准则的 加权 ROE 口径, 与雪球展示一致
- 每个指标自带 YoY 同比变化, 趋势分析可直接用
- 一个 indicator 接口就给齐 ROE/毛利率/净利率/流动比率/资产负债率/营收/利润
- 字段标准化、英文 key, 无中文名歧义

劣势:
- 需先访问 xueqiu.com 拿 cookie (xq_a_token), 否则 400016
- 有速率限制, 建议每只之间 1s 间隔
"""

from __future__ import annotations

import re
import time
from typing import Any, Dict, List, Optional, Tuple

import requests

_CN_RE = re.compile(r"^(\d{6})(?:\.(SS|SH|SZ|SHA|SZA))?$", re.IGNORECASE)


def _parse_xq_symbol(ticker: str) -> Tuple[str, str]:
    """Return (code, xueqiu_symbol like 'SH600519')."""
    m = _CN_RE.match(ticker.upper().strip())
    if not m:
        raise ValueError(f"not an A-share ticker: {ticker}")
    code = m.group(1)
    suffix = (m.group(2) or "").upper()
    if suffix in ("SS", "SH", "SHA"):
        exch = "SH"
    elif suffix in ("SZ", "SZA"):
        exch = "SZ"
    else:
        exch = "SH" if code.startswith(("6", "9")) else "SZ"
    return code, f"{exch}{code}"


class XueqiuClient:
    """Lazy session with cookie bootstrap."""
    _instance: Optional["XueqiuClient"] = None

    def __init__(self):
        self.s = requests.Session()
        self.s.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Referer": "https://xueqiu.com/",
        })
        self._ready = False

    @classmethod
    def shared(cls) -> "XueqiuClient":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _bootstrap(self):
        if self._ready:
            return
        # 访问任意股票详情页, Snowball 会种 xq_a_token 等 cookie
        self.s.get("https://xueqiu.com/snowman/S/SH600519/detail", timeout=15)
        self._ready = True

    def get(self, path: str, params: Dict[str, Any]) -> Dict[str, Any]:
        self._bootstrap()
        r = self.s.get(f"https://stock.xueqiu.com{path}", params=params, timeout=20)
        r.raise_for_status()
        return r.json()


def _unwrap(v):
    """雪球 v5 三表+indicator 字段普遍是 [value, yoy_change] 列表, 这里只取 value."""
    if isinstance(v, list):
        return v[0] if v else None
    return v


def _vval(d: Dict[str, Any], key: str) -> Optional[float]:
    if not d:
        return None
    v = _unwrap(d.get(key))
    try:
        return float(v) if v is not None else None
    except (TypeError, ValueError):
        return None


def _yoy(d: Dict[str, Any], key: str) -> Optional[float]:
    if not d:
        return None
    v = d.get(key)
    if isinstance(v, list) and len(v) >= 2:
        try:
            return float(v[1])
        except (TypeError, ValueError):
            return None
    return None


def fetch_xueqiu(ticker: str, count: int = 6) -> Optional[Dict[str, Any]]:
    code, xq_sym = _parse_xq_symbol(ticker)
    cli = XueqiuClient.shared()

    # 1) Quote (price, mcap, pe_ttm, pb, shares)
    try:
        q = cli.get("/v5/stock/quote.json", {"symbol": xq_sym, "extend": "detail"})
        quote = q.get("data", {}).get("quote") or {}
    except Exception as e:
        print(f"  WARN quote fail {ticker}: {e}")
        return None

    if not quote.get("current"):
        return None

    # 2) Indicator (annual, 含 YoY)
    try:
        ind_resp = cli.get("/v5/stock/finance/cn/indicator.json",
                           {"symbol": xq_sym, "type": "Q4", "is_detail": "true", "count": str(count)})
        ind_list = ind_resp.get("data", {}).get("list", []) or []
    except Exception as e:
        print(f"  WARN indicator fail {ticker}: {e}")
        ind_list = []

    # 3) Income / Balance / Cash Flow (annual)
    def _fetch_stmt(ep: str) -> List[Dict[str, Any]]:
        try:
            d = cli.get(f"/v5/stock/finance/cn/{ep}.json",
                        {"symbol": xq_sym, "type": "Q4", "is_detail": "true", "count": str(count)})
            return d.get("data", {}).get("list", []) or []
        except Exception as e:
            print(f"  WARN {ep} fail {ticker}: {e}")
            return []

    inc_list = _fetch_stmt("income")
    bs_list  = _fetch_stmt("balance")
    cf_list  = _fetch_stmt("cash_flow")

    # 三表字段同样是 [value, yoy] 形式, 提前 unwrap 一份用于数值计算
    def _unwrap_items(lst):
        out = []
        for it in lst:
            row = {}
            for k, v in it.items():
                row[k] = _unwrap(v) if k not in ("report_date", "report_name", "ctime") else v
            out.append(row)
        return out
    inc_list = _unwrap_items(inc_list)
    bs_list  = _unwrap_items(bs_list)
    cf_list  = _unwrap_items(cf_list)

    # 4) K 线 (近 5 年, 日线)
    price_history: List[tuple] = []
    try:
        # Snowball 行情接口
        end_ts = int(time.time() * 1000)
        khist = cli.get("/v5/stock/chart/kline.json", {
            "symbol": xq_sym, "begin": end_ts, "period": "day",
            "type": "before", "count": "-1300", "indicator": "kline",
        })
        items = khist.get("data", {}).get("item", []) or []
        col_names = khist.get("data", {}).get("column", []) or []
        if items and "timestamp" in col_names and "close" in col_names:
            ts_idx = col_names.index("timestamp")
            cl_idx = col_names.index("close")
            for it in items:
                if it[ts_idx] and it[cl_idx]:
                    d_str = time.strftime("%Y-%m-%d", time.localtime(it[ts_idx] / 1000))
                    price_history.append((d_str, float(it[cl_idx])))
    except Exception as e:
        print(f"  WARN kline fail {ticker}: {e}")

    # ---------- 拼装 raw dict ----------

    def _report_date(item: Dict[str, Any]) -> str:
        rd = item.get("report_date")
        if rd:
            return time.strftime("%Y-%m-%d", time.localtime(rd / 1000))
        return item.get("report_name", "")[:4] + "-12-31"

    # 共同年份集合 (基于 indicator)
    years = [_report_date(x) for x in ind_list]
    if not years and inc_list:
        years = [_report_date(x) for x in inc_list]

    # --- info dict (yfinance-like) ---
    pe_ttm = _vval({"v": quote.get("pe_ttm")}, "v") if quote.get("pe_ttm") is not None else None
    pe_ttm = quote.get("pe_ttm")
    pb = quote.get("pb")

    # ROE/margins/ratios from indicator (latest)
    ind0 = ind_list[0] if ind_list else {}
    roe_latest = _vval(ind0, "avg_roe")
    gm_latest = _vval(ind0, "gross_selling_rate")
    nm_latest = _vval(ind0, "net_selling_rate")
    current_ratio_latest = _vval(ind0, "current_ratio")
    asset_liab_latest = _vval(ind0, "asset_liab_ratio")

    # 营业利润率 (用 op / total_revenue 算)
    op_margin_latest = None
    if inc_list:
        op_v = inc_list[0].get("op")
        rev_v = inc_list[0].get("total_revenue") or inc_list[0].get("revenue")
        if op_v and rev_v:
            op_margin_latest = op_v / rev_v

    # YoY 同比 (avg_roe 的 YoY = ROE 变化, 不是营收/利润同比)
    earnings_growth = _yoy(ind0, "net_profit_atsopc_yoy")  # 这是 同比的同比, 不要
    # 取直接的同比
    if inc_list:
        ni0 = inc_list[0].get("net_profit_atsopc")
        ni1 = inc_list[1].get("net_profit_atsopc") if len(inc_list) > 1 else None
        if ni0 and ni1 and ni1 > 0:
            earnings_growth = (ni0 - ni1) / ni1
        rev0 = inc_list[0].get("total_revenue") or inc_list[0].get("revenue")
        rev1 = (inc_list[1].get("total_revenue") or inc_list[1].get("revenue")) if len(inc_list) > 1 else None
        if rev0 and rev1 and rev1 > 0:
            revenue_growth = (rev0 - rev1) / rev1
        else:
            revenue_growth = None
    else:
        revenue_growth = None

    # D/E (优先用 计息债务/归母权益)
    de_ratio = None
    total_debt_latest = None
    if bs_list:
        lt = bs_list[0].get("lt_loan") or 0
        st = bs_list[0].get("st_loan") or 0
        eq_parent = bs_list[0].get("total_quity_atsopc")
        if eq_parent and eq_parent > 0:
            total_debt_latest = (lt or 0) + (st or 0)
            de_ratio = total_debt_latest / eq_parent

    # 52w hi/lo
    last_252 = price_history[-252:] if len(price_history) >= 50 else price_history
    if last_252:
        closes = [p[1] for p in last_252]
        w52_high, w52_low = max(closes), min(closes)
    else:
        w52_high = w52_low = None

    # 实际 FCF = OCF - CapEx
    fcf_latest = None
    if cf_list:
        ocf = cf_list[0].get("ncf_from_oa")
        capex = cf_list[0].get("cash_paid_for_assets")
        if ocf is not None and capex is not None:
            fcf_latest = ocf - capex
        elif ocf is not None:
            fcf_latest = ocf

    info_dict = {
        "longName": quote.get("name"),
        "shortName": quote.get("name"),
        "sector": None,
        "industry": None,
        "country": "China",
        "currency": "CNY",
        "financialCurrency": "CNY",
        "marketCap": quote.get("market_capital"),
        "currentPrice": quote.get("current"),
        "regularMarketPrice": quote.get("current"),
        "sharesOutstanding": quote.get("total_shares"),
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
        "debtToEquity": de_ratio * 100 if de_ratio is not None else None,
        "totalDebt": total_debt_latest,
        "currentRatio": current_ratio_latest,
        "profitMargins": nm_latest / 100.0 if nm_latest is not None else None,
        "operatingMargins": op_margin_latest,
        "grossMargins": gm_latest / 100.0 if gm_latest is not None else None,
        "returnOnEquity": roe_latest / 100.0 if roe_latest is not None else None,
        "earningsGrowth": earnings_growth,
        "revenueGrowth": revenue_growth,
        "freeCashflow": fcf_latest,
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

    # --- financials / balance_sheet / cashflow (年度, 字段用 yfinance 命名以让 metrics.py 直接吃) ---
    financials: Dict[str, Dict[str, float]] = {}
    balance_sheet: Dict[str, Dict[str, float]] = {}
    cashflow: Dict[str, Dict[str, float]] = {}

    def _idx_by_date(lst, dk):
        for j, item in enumerate(lst):
            if _report_date(item) == dk:
                return j
        return None

    # 用 indicator 的年份作主索引; 不在 indicator 的也补
    all_dates = []
    for lst in (ind_list, inc_list, bs_list, cf_list):
        for it in lst:
            dk = _report_date(it)
            if dk not in all_dates:
                all_dates.append(dk)
    all_dates.sort(reverse=True)

    for dk in all_dates:
        i_inc = _idx_by_date(inc_list, dk)
        i_bs  = _idx_by_date(bs_list, dk)
        i_cf  = _idx_by_date(cf_list, dk)

        # ---- 利润表 ----
        fin_row: Dict[str, float] = {}
        if i_inc is not None:
            it = inc_list[i_inc]
            ni = it.get("net_profit_atsopc")
            rev = it.get("total_revenue") or it.get("revenue")
            cogs = it.get("operating_cost") or it.get("operating_costs")
            op_v = it.get("op")
            ie = it.get("finance_cost_interest_fee")
            if ni is not None: fin_row["Net Income"] = ni
            if rev is not None: fin_row["Total Revenue"] = rev
            if rev is not None and cogs is not None: fin_row["Gross Profit"] = rev - cogs
            if op_v is not None: fin_row["Operating Income"] = op_v
            if ie is not None and ie > 0: fin_row["Interest Expense"] = ie
        if fin_row:
            financials[dk] = fin_row

        # ---- 资产负债表 ----
        bs_row: Dict[str, float] = {}
        if i_bs is not None:
            it = bs_list[i_bs]
            eq_p = it.get("total_quity_atsopc")
            ta = it.get("total_assets")
            tl = it.get("total_liab")
            lt = it.get("lt_loan")
            st = it.get("st_loan")
            gw = it.get("goodwill")
            ca = it.get("total_current_assets")
            cl = it.get("total_current_liab")
            sh = it.get("shares")
            if eq_p is not None: bs_row["Stockholders Equity"] = eq_p
            if ta is not None: bs_row["Total Assets"] = ta
            if tl is not None: bs_row["Total Liabilities Net Minority Interest"] = tl
            if lt is not None: bs_row["Long Term Debt"] = lt
            if lt is not None or st is not None:
                bs_row["Total Debt"] = (lt or 0) + (st or 0)
            if gw is not None: bs_row["Goodwill"] = gw
            if ca is not None: bs_row["Current Assets"] = ca
            if cl is not None: bs_row["Current Liabilities"] = cl
            if sh is not None:
                bs_row["Share Issued"] = sh
                bs_row["Ordinary Shares Number"] = sh
        if bs_row:
            balance_sheet[dk] = bs_row

        # ---- 现金流量表 ----
        cf_row: Dict[str, float] = {}
        if i_cf is not None:
            it = cf_list[i_cf]
            ocf = it.get("ncf_from_oa")
            capex = it.get("cash_paid_for_assets")
            if ocf is not None:
                cf_row["Operating Cash Flow"] = ocf
                if capex is not None:
                    cf_row["Capital Expenditure"] = -capex  # yfinance 约定 CapEx 为负
                    cf_row["Free Cash Flow"] = ocf - capex
                else:
                    cf_row["Free Cash Flow"] = ocf
                    cf_row["Capital Expenditure"] = 0.0
        if cf_row:
            cashflow[dk] = cf_row

    return {
        "ticker": ticker,
        "info": info_dict,
        "financials": financials,
        "balance_sheet": balance_sheet,
        "cashflow": cashflow,
        "price_history": price_history,
        "news": [],
        "_source": "xueqiu",
    }


def is_ashare(ticker: str) -> bool:
    return bool(_CN_RE.match((ticker or "").upper().strip()))
