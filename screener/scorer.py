"""Scoring rules for BuffettLens.

The scoring system intentionally keeps technical indicators small (5 points)
and gives most weight to business quality, balance-sheet strength, growth, and
valuation.
"""

from typing import Any, Dict, List, Optional, Tuple


def _tier(
    value: Optional[float],
    tiers: List[Tuple[float, float]],
    default: float = 0,
    higher_is_better: bool = True,
) -> float:
    if value is None:
        return default
    for threshold, score in tiers:
        if higher_is_better and value >= threshold:
            return score
        if not higher_is_better and value <= threshold:
            return score
    return default


def hard_gates(m: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """Return whether a stock passes the hard quality gates."""
    reasons: List[str] = []

    mc = m.get("market_cap")
    if mc is None or mc < 500_000_000:
        reasons.append(f"市值不足或缺失 ({mc})")

    roe = m.get("roe_avg") or m.get("roe_current")
    if roe is None:
        reasons.append("ROE 数据缺失")
    elif roe < 0.08:
        reasons.append(f"ROE 过低 ({roe:.1%})")

    ni = m.get("net_income")
    if ni is None:
        reasons.append("净利润数据缺失")
    elif ni <= 0:
        reasons.append("最近年度净利润为负")

    de = m.get("debt_to_equity")
    if de is not None and de > 3.0:
        reasons.append(f"杠杆过高 D/E={de:.2f}")

    if m.get("ni_history_count", 0) < 2:
        reasons.append("历史财务数据不足")

    if m.get("ni_negative_years", 0) >= 3:
        reasons.append(f"近年亏损年份过多 ({m['ni_negative_years']} 次)")

    return len(reasons) == 0, reasons


def _score_a_buffett(m: Dict[str, Any]) -> Tuple[float, List[Dict[str, Any]]]:
    items: List[Dict[str, Any]] = []
    total = 0.0

    v = m.get("roe_avg") or m.get("roe_current")
    s = _tier(v, [(0.20, 8), (0.15, 6), (0.10, 3)])
    items.append({"id": "A1", "name": "ROE 4年平均", "tag": "🦬 Buffett", "value": v, "fmt": "pct", "score": s, "max": 8})
    total += s

    v = m.get("roic")
    s = _tier(v, [(0.15, 7), (0.12, 5), (0.08, 2)])
    items.append({"id": "A2", "name": "ROIC", "tag": "🦬 Buffett / 🧠 Munger", "value": v, "fmt": "pct", "score": s, "max": 7})
    total += s

    v = m.get("op_margin_avg") or m.get("op_margin_current")
    s = _tier(v, [(0.25, 6), (0.15, 4), (0.10, 2)])
    items.append({"id": "A3", "name": "营业利润率 4年平均", "tag": "🦬 Buffett / 🧠 Munger", "value": v, "fmt": "pct", "score": s, "max": 6})
    total += s

    v = m.get("net_margin")
    s = _tier(v, [(0.20, 5), (0.10, 3), (0.05, 1)])
    items.append({"id": "A4", "name": "净利率", "tag": "🦬 Buffett", "value": v, "fmt": "pct", "score": s, "max": 5})
    total += s

    v = m.get("fcf_to_ni")
    s = _tier(v, [(1.0, 5), (0.8, 3), (0.5, 1)])
    items.append({"id": "A5", "name": "FCF / 净利润", "tag": "🦬 Buffett", "value": v, "fmt": "pct", "score": s, "max": 5})
    total += s

    slope = m.get("gm_slope")
    if slope is None:
        s = 0
        v_str = "数据不足"
    elif slope > 0.005:
        s = 4
        v_str = "上升"
    elif slope > -0.005:
        s = 2
        v_str = "稳定"
    else:
        s = 0
        v_str = "下滑"
    items.append({"id": "A6", "name": "毛利率趋势", "tag": "🦬 Buffett", "value": slope, "fmt": "trend", "value_str": v_str, "score": s, "max": 4})
    total += s

    return total, items


def _score_b_strength(m: Dict[str, Any]) -> Tuple[float, List[Dict[str, Any]]]:
    items: List[Dict[str, Any]] = []
    total = 0.0

    v = m.get("lt_debt_to_ni")
    s = _tier(v, [(2, 5), (5, 3), (8, 1)], higher_is_better=False)
    items.append({"id": "B1", "name": "长期债务 / 净利润", "tag": "🦬 Buffett", "value": v, "fmt": "ratio", "score": s, "max": 5})
    total += s

    v = m.get("debt_to_equity")
    s = _tier(v, [(0.5, 4), (1.0, 2), (1.5, 1)], higher_is_better=False)
    items.append({"id": "B2", "name": "Debt / Equity", "tag": "🦬 Buffett", "value": v, "fmt": "ratio", "score": s, "max": 4})
    total += s

    v = m.get("interest_coverage")
    s = _tier(v, [(20, 3), (10, 2), (5, 1)])
    items.append({"id": "B3", "name": "利息保障倍数", "tag": "📘 Graham", "value": v, "fmt": "ratio", "score": s, "max": 3})
    total += s

    v = m.get("current_ratio")
    s = _tier(v, [(2.0, 3), (1.5, 2), (1.0, 1)])
    items.append({"id": "B4", "name": "流动比率", "tag": "📘 Graham", "value": v, "fmt": "ratio", "score": s, "max": 3})
    total += s

    return total, items


def _score_c_growth(m: Dict[str, Any]) -> Tuple[float, List[Dict[str, Any]]]:
    items: List[Dict[str, Any]] = []
    total = 0.0

    v = m.get("ni_cagr_4y")
    s = _tier(v, [(0.15, 5), (0.10, 3), (0.05, 1)])
    items.append({"id": "C1", "name": "净利润 4年 CAGR", "tag": "🦬 Buffett", "value": v, "fmt": "pct", "score": s, "max": 5})
    total += s

    v = m.get("rev_cagr_4y")
    s = _tier(v, [(0.10, 4), (0.05, 2)])
    items.append({"id": "C2", "name": "营收 4年 CAGR", "tag": "📈 Lynch", "value": v, "fmt": "pct", "score": s, "max": 4})
    total += s

    v = m.get("ni_negative_years", 0)
    if v == 0:
        s = 3
    elif v == 1:
        s = 2
    elif v == 2:
        s = 1
    else:
        s = 0
    items.append({"id": "C3", "name": "亏损年份数", "tag": "🦬 Buffett", "value": v, "fmt": "int", "score": s, "max": 3})
    total += s

    v = m.get("share_dilution_cagr")
    if v is None:
        s = 0
    elif v < -0.01:
        s = 3
    elif v < 0.01:
        s = 2
    elif v < 0.02:
        s = 1
    else:
        s = 0
    items.append({"id": "C4", "name": "股本年化变化", "tag": "🧠 Munger", "value": v, "fmt": "pct", "score": s, "max": 3})
    total += s

    return total, items


def _score_d_valuation(m: Dict[str, Any]) -> Tuple[float, List[Dict[str, Any]]]:
    items: List[Dict[str, Any]] = []
    total = 0.0

    v = m.get("pe_forward") or m.get("pe_ttm")
    s = _tier(v, [(15, 5), (20, 3), (25, 1)], higher_is_better=False)
    items.append({"id": "D1", "name": "Forward P/E", "tag": "⚙️ 通用", "value": v, "fmt": "ratio", "score": s, "max": 5})
    total += s

    v = m.get("peg")
    s = _tier(v, [(1.0, 4), (1.5, 2), (2.0, 1)], higher_is_better=False) if v and v > 0 else 0
    items.append({"id": "D2", "name": "PEG", "tag": "📈 Lynch", "value": v, "fmt": "ratio", "score": s, "max": 4})
    total += s

    v = m.get("fcf_yield")
    s = _tier(v, [(0.06, 4), (0.04, 2), (0.02, 1)])
    items.append({"id": "D3", "name": "FCF Yield", "tag": "🏛️ Damodaran", "value": v, "fmt": "pct", "score": s, "max": 4})
    total += s

    v = m.get("p_to_fcf")
    s = _tier(v, [(15, 4), (25, 2), (40, 1)], higher_is_better=False) if v and v > 0 else 0
    items.append({"id": "D4", "name": "P/FCF", "tag": "🦬 Buffett", "value": v, "fmt": "ratio", "score": s, "max": 4})
    total += s

    v = m.get("ey_vs_treasury")
    s = _tier(v, [(0.03, 3), (0, 1)])
    items.append({"id": "D5", "name": "E/P - 10Y 国债", "tag": "🦬 Buffett", "value": v, "fmt": "pct", "score": s, "max": 3})
    total += s

    return total, items


def _score_e_moat(m: Dict[str, Any]) -> Tuple[float, List[Dict[str, Any]]]:
    items: List[Dict[str, Any]] = []
    total = 0.0

    v = m.get("op_margin_avg") or m.get("op_margin_current")
    s = _tier(v, [(0.25, 4), (0.18, 2), (0.12, 1)])
    items.append({"id": "E1", "name": "营业利润率水平", "tag": "🧠 Munger", "value": v, "fmt": "pct", "score": s, "max": 4})
    total += s

    v = m.get("op_margin_cv")
    s = _tier(v, [(0.10, 3), (0.20, 2), (0.30, 1)], higher_is_better=False)
    items.append({"id": "E2", "name": "营业利润率稳定性 (CV)", "tag": "🦬 Buffett / 🧠 Munger", "value": v, "fmt": "ratio", "score": s, "max": 3})
    total += s

    v = m.get("goodwill_ratio")
    if v is None:
        s = 0
    elif v < 0.10:
        s = 3
    elif v < 0.30:
        s = 2
    elif v < 0.50:
        s = 1
    else:
        s = 0
    items.append({"id": "E3", "name": "商誉 / 总资产", "tag": "🧠 Munger", "value": v, "fmt": "pct", "score": s, "max": 3})
    total += s

    return total, items


def _score_f_technical(m: Dict[str, Any]) -> Tuple[float, List[Dict[str, Any]]]:
    items: List[Dict[str, Any]] = []
    total = 0.0

    v = m.get("price_vs_200ma")
    if v is None:
        s = 0
    elif -0.20 <= v <= 0.05:
        s = 3
    elif v < -0.20:
        s = 2
    elif v <= 0.20:
        s = 1
    else:
        s = 0
    items.append({"id": "F1", "name": "价格 vs 200日均线", "tag": "❌🦬 技术参考", "value": v, "fmt": "pct", "score": s, "max": 3})
    total += s

    v = m.get("rsi_14")
    if v is None:
        s = 0
    elif 30 <= v <= 50:
        s = 2
    elif 50 < v <= 70:
        s = 1
    else:
        s = 0
    items.append({"id": "F2", "name": "RSI(14)", "tag": "❌🦬 技术参考", "value": v, "fmt": "ratio", "score": s, "max": 2})
    total += s

    return total, items


def score(m: Dict[str, Any]) -> Dict[str, Any]:
    a_score, a_items = _score_a_buffett(m)
    b_score, b_items = _score_b_strength(m)
    c_score, c_items = _score_c_growth(m)
    d_score, d_items = _score_d_valuation(m)
    e_score, e_items = _score_e_moat(m)
    f_score, f_items = _score_f_technical(m)

    total = a_score + b_score + c_score + d_score + e_score + f_score

    return {
        "total": round(total, 1),
        "categories": [
            {"id": "A", "name": "Buffett 核心质量", "tag": "🦬", "score": round(a_score, 1), "max": 35, "items": a_items},
            {"id": "B", "name": "财务稳健性", "tag": "🛡️", "score": round(b_score, 1), "max": 15, "items": b_items},
            {"id": "C", "name": "成长性", "tag": "📈", "score": round(c_score, 1), "max": 15, "items": c_items},
            {"id": "D", "name": "估值", "tag": "💰", "score": round(d_score, 1), "max": 20, "items": d_items},
            {"id": "E", "name": "Munger 护城河", "tag": "🏰", "score": round(e_score, 1), "max": 10, "items": e_items},
            {"id": "F", "name": "技术参考 (非 Buffett)", "tag": "📊", "score": round(f_score, 1), "max": 5, "items": f_items},
        ],
    }


def rating_stars(total: float) -> Tuple[str, str]:
    if total >= 90:
        return "⭐⭐⭐⭐⭐", "卓越 - 罕见的 Buffett 级机会"
    if total >= 80:
        return "⭐⭐⭐⭐", "优质 - 值得深度研究"
    if total >= 70:
        return "⭐⭐⭐", "良好 - 有亮点但仍有短板"
    if total >= 60:
        return "⭐⭐", "中等 - 需要谨慎评估"
    return "⭐", "一般 - 不建议作为优先研究对象"
