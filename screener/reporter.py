"""Markdown and CSV report generation for BuffettLens."""

import csv
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from .scorer import rating_stars

REPORTS_DIR = Path(__file__).resolve().parent.parent / "reports"
REPORTS_DIR.mkdir(exist_ok=True)


def _fmt_value(v, fmt: str) -> str:
    if v is None:
        return "N/A"
    try:
        if fmt == "pct":
            return f"{v * 100:.2f}%"
        if fmt == "ratio":
            return f"{v:.2f}"
        if fmt == "int":
            return f"{int(v)}"
        if fmt == "money":
            return _fmt_money(v)
        return str(v)
    except (TypeError, ValueError):
        return "N/A"


def _fmt_money(v) -> str:
    if v is None:
        return "N/A"
    try:
        v = float(v)
        if abs(v) >= 1e12:
            return f"${v / 1e12:.2f}T"
        if abs(v) >= 1e9:
            return f"${v / 1e9:.2f}B"
        if abs(v) >= 1e6:
            return f"${v / 1e6:.2f}M"
        return f"${v:,.2f}" if abs(v) < 1000 else f"${v:,.0f}"
    except (TypeError, ValueError):
        return "N/A"


def _safe_filename(s: str) -> str:
    return re.sub(r"[^\w\-_]+", "_", s)[:40].strip("_")


def _category_bar(score: float, max_score: float, width: int = 20) -> str:
    if max_score <= 0:
        return ""
    pct = max(0.0, min(1.0, score / max_score))
    filled = int(round(pct * width))
    return "█" * filled + "░" * (width - filled)


def _gen_recommendation_reason(m: Dict[str, Any], scoring: Dict[str, Any]) -> str:
    lines: List[str] = []
    total = scoring["total"]
    cats = {c["id"]: c for c in scoring["categories"]}
    name = m.get("name") or m["ticker"]

    if total >= 80:
        lines.append(f"**{name}** 综合评分 **{total}/100**，属于高质量价值候选，值得进入深度研究。")
    elif total >= 70:
        lines.append(f"**{name}** 综合评分 **{total}/100**，基本面有亮点，但仍需要重点核查短板。")
    elif total >= 60:
        lines.append(f"**{name}** 综合评分 **{total}/100**，可作为观察对象，不适合直接下结论。")
    else:
        lines.append(f"**{name}** 综合评分 **{total}/100**，当前更适合作为对照样本。")

    strengths = []
    weaknesses = []
    for c in scoring["categories"]:
        ratio = c["score"] / c["max"] if c["max"] else 0
        label = f"{c['tag']} {c['name']} ({c['score']}/{c['max']})"
        if ratio >= 0.75:
            strengths.append(label)
        elif ratio < 0.40:
            weaknesses.append(label)

    if strengths:
        lines.append(f"**强项**: {', '.join(strengths)}")
    if weaknesses:
        lines.append(f"**短板**: {', '.join(weaknesses)}")

    d_score = cats.get("D", {}).get("score", 0)
    if d_score >= 15:
        lines.append("**估值定位**: 当前估值较有吸引力，但低估值本身不是买入理由，必须先确认下跌不是结构性恶化导致。")
    elif d_score >= 10:
        lines.append("**估值定位**: 当前估值大致合理，适合结合业务确定性继续研究。")
    elif d_score >= 5:
        lines.append("**估值定位**: 当前估值偏高，建议等待更好的价格或更强的增长证据。")
    else:
        lines.append("**估值定位**: 当前估值压力较大，不建议只因公司质量而忽略价格。")

    return "\n\n".join(lines)


def _decline_flags(m: Dict[str, Any]) -> List[str]:
    flags = []
    checks = [
        ("今年以来", m.get("return_ytd"), -0.20),
        ("近1年", m.get("return_1y"), -0.25),
        ("近3年", m.get("return_3y"), -0.35),
        ("距52周高位", m.get("pct_from_52w_high"), -0.25),
        ("近3年最大回撤", m.get("max_drawdown_3y"), -0.35),
    ]
    for label, value, threshold in checks:
        if value is not None and value <= threshold:
            flags.append(f"{label} {_fmt_value(value, 'pct')}")
    return flags


def _rally_flags(m: Dict[str, Any]) -> List[str]:
    flags = []
    checks = [
        ("今年以来", m.get("return_ytd"), 0.30),
        ("近1年", m.get("return_1y"), 0.50),
        ("近3年", m.get("return_3y"), 1.00),
    ]
    for label, value, threshold in checks:
        if value is not None and value >= threshold:
            flags.append(f"{label} {_fmt_value(value, 'pct')}")

    if m.get("pct_from_52w_high") is not None and m["pct_from_52w_high"] >= -0.08:
        flags.append(f"接近52周高位（距高位 {_fmt_value(m.get('pct_from_52w_high'), 'pct')}）")
    return flags


def _news_hints(m: Dict[str, Any]) -> List[str]:
    hints = []
    keywords = [
        "ai", "artificial intelligence", "guidance", "outlook", "earnings",
        "downgrade", "lawsuit", "antitrust", "regulatory", "competition",
        "slowdown", "tariff", "margin", "layoff", "investigation",
    ]
    for item in (m.get("news") or [])[:8]:
        title = item.get("title", "")
        lower = title.lower()
        if any(k in lower for k in keywords):
            hints.append(title)
    return hints[:3]


def _gen_decline_diagnosis(m: Dict[str, Any], scoring: Dict[str, Any]) -> str:
    """Explain likely decline reasons from price action, metrics, and news titles."""
    lines = []
    flags = _decline_flags(m)
    active_decline_flags = [flag for flag in flags if not flag.startswith("近3年最大回撤")]
    rally = _rally_flags(m)
    cats = {c["id"]: c for c in scoring["categories"]}

    lines.append(
        f"- **价格变化**: YTD {_fmt_value(m.get('return_ytd'), 'pct')} | "
        f"近1年 {_fmt_value(m.get('return_1y'), 'pct')} | "
        f"近3年 {_fmt_value(m.get('return_3y'), 'pct')} | "
        f"距52周高位 {_fmt_value(m.get('pct_from_52w_high'), 'pct')} | "
        f"近3年最大回撤 {_fmt_value(m.get('max_drawdown_3y'), 'pct')}"
    )

    if rally and scoring.get("total", 0) >= 70:
        lines.append("- **强势高分提醒**: 这家公司分数高，同时价格也明显走强：" + "；".join(rally) + "。这类标的很有研究价值，因为它不是单纯“跌出来的便宜”，而是基本面评分和市场趋势同时偏强。")
    elif rally:
        lines.append("- **上涨提醒**: 价格明显走强：" + "；".join(rally) + "。需要区分基本面改善和估值过热。")

    if not active_decline_flags:
        if flags and rally:
            lines.append("- **回撤说明**: 近几年曾出现较大回撤，但当前价格已经明显修复，因此不把它归类为“跌出来的便宜”。")
        elif flags:
            lines.append("- **回撤说明**: 近几年曾出现较大回撤，但当前未检测到明显的年度级深跌。")
        if not rally:
            lines.append("- **结论**: 未检测到明显的大跌或长期深度回撤；本报告不把“跌得多”作为推荐理由。")
        return "\n".join(lines)

    reasons = []
    sector = (m.get("sector") or "").lower()
    industry = (m.get("industry") or "").lower()

    if "software" in industry or ("technology" in sector and ("application" in industry or "infrastructure" in industry)):
        reasons.append("所属软件/科技板块，需重点核查 AI 对传统软件功能、订阅席位、定价权和客户预算的冲击。")

    valuation_score = cats.get("D", {}).get("score", 0)
    if valuation_score <= 6:
        reasons.append("估值分偏低，市场可能仍在压缩高估值或担心未来增长不能支撑当前倍数。")

    if m.get("rev_cagr_4y") is not None and m["rev_cagr_4y"] < 0.05:
        reasons.append("营收 4 年 CAGR 偏低，显示增长动能不足。")
    if m.get("ni_cagr_4y") is not None and m["ni_cagr_4y"] < 0.05:
        reasons.append("净利润 4 年 CAGR 偏低，说明盈利增长不足或波动较大。")
    if m.get("fcf_to_ni") is not None and m["fcf_to_ni"] < 0.5:
        reasons.append("自由现金流/净利润偏低，利润质量需要复核。")
    if m.get("debt_to_equity") is not None and m["debt_to_equity"] > 1.5:
        reasons.append("杠杆偏高，利率和再融资压力可能放大下跌。")
    if m.get("gm_slope") is not None and m["gm_slope"] < -0.005:
        reasons.append("毛利率趋势下滑，可能反映竞争、价格压力或成本压力。")

    news = _news_hints(m)
    if news:
        reasons.append("近期新闻标题中出现可能相关线索：" + "；".join(news))

    if reasons:
        lines.append("- **可能原因**: " + " ".join(reasons))
    else:
        lines.append("- **可能原因**: 原因不详。价格数据确认有明显回撤，但免费数据和近期标题没有给出足够清晰的解释。")

    lines.append("- **使用提醒**: 跌幅只说明价格更低，不等于安全边际。若下跌来自商业模式被 AI/竞争/监管永久削弱，应降低评分结论的可信度；反过来，高分且持续上涨的公司值得优先复核是否存在“质量被市场持续确认”的机会。")
    return "\n".join(lines)


def gen_report(m: Dict[str, Any], scoring: Dict[str, Any]) -> str:
    ticker = m["ticker"]
    name = m.get("name") or ticker
    total = scoring["total"]
    stars, desc = rating_stars(total)

    lines: List[str] = []
    lines.append(f"# {ticker} - {name}")
    lines.append("")
    lines.append(f"**综合评分: {total} / 100** | {stars} {desc}")
    lines.append("")
    lines.append(f"- **行业**: {m.get('sector') or 'N/A'} / {m.get('industry') or 'N/A'}")
    lines.append(f"- **国家**: {m.get('country') or 'N/A'}")
    lines.append(f"- **当前价格**: {_fmt_money(m.get('current_price'))} | **市值**: {_fmt_money(m.get('market_cap'))}")
    lines.append("")

    lines.append("## 📌 推荐理由")
    lines.append("")
    lines.append(_gen_recommendation_reason(m, scoring))
    lines.append("")

    lines.append("## 🔎 涨跌背景")
    lines.append("")
    lines.append(_gen_decline_diagnosis(m, scoring))
    lines.append("")

    if m.get("summary"):
        summary = m["summary"][:500] + ("..." if len(m["summary"]) > 500 else "")
        lines.append("### 公司简介（英文原文，Yahoo Finance）")
        lines.append(f"> {summary}")
        lines.append("")

    if m.get("currency_mismatch"):
        lines.append("### 数据口径提醒")
        lines.append(
            f"> 该股票价格/市值币种为 {m.get('currency') or 'N/A'}，财报币种为 "
            f"{m.get('financial_currency') or 'N/A'}。为避免币种混用，本报告不计算 FCF Yield 和 P/FCF。"
        )
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("## 📊 评分明细")
    lines.append("")
    for c in scoring["categories"]:
        bar = _category_bar(c["score"], c["max"])
        lines.append(f"### {c['tag']} {c['name']}: **{c['score']} / {c['max']}**")
        lines.append(f"`{bar}`")
        lines.append("")
        lines.append("| # | 指标 | 来源标签 | 值 | 得分 |")
        lines.append("|---|------|----------|-----|------|")
        for item in c["items"]:
            val_str = item.get("value_str") or _fmt_value(item.get("value"), item.get("fmt", "ratio"))
            score_str = f"{item['score']} / {item['max']}"
            mark = "✅" if item["score"] >= item["max"] * 0.7 else ("⚠️" if item["score"] > 0 else "❌")
            lines.append(f"| {item['id']} | {item['name']} | {item['tag']} | {val_str} | {mark} {score_str} |")
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("## 💵 关键数据快照")
    lines.append("")
    lines.append("| 指标 | 值 | 指标 | 值 |")
    lines.append("|------|-----|------|-----|")
    rows = [
        ("当前价格", _fmt_money(m.get("current_price")), "市值", _fmt_money(m.get("market_cap"))),
        ("TTM P/E", _fmt_value(m.get("pe_ttm"), "ratio"), "Forward P/E", _fmt_value(m.get("pe_forward"), "ratio")),
        ("PEG", _fmt_value(m.get("peg"), "ratio"), "P/B", _fmt_value(m.get("pb"), "ratio")),
        ("P/S", _fmt_value(m.get("ps"), "ratio"), "EV/EBITDA", _fmt_value(m.get("ev_ebitda"), "ratio")),
        ("ROE (4yr)", _fmt_value(m.get("roe_avg"), "pct"), "ROIC", _fmt_value(m.get("roic"), "pct")),
        ("营业利润率 (4yr)", _fmt_value(m.get("op_margin_avg"), "pct"), "净利率", _fmt_value(m.get("net_margin"), "pct")),
        ("毛利率", _fmt_value(m.get("gm_current"), "pct"), "FCF/净利润", _fmt_value(m.get("fcf_to_ni"), "pct")),
        ("FCF (TTM)", _fmt_money(m.get("fcf")), "净利润 (最近年度)", _fmt_money(m.get("net_income"))),
        ("D/E", _fmt_value(m.get("debt_to_equity"), "ratio"), "长期债务/净利润", _fmt_value(m.get("lt_debt_to_ni"), "ratio")),
        ("利息保障倍数", _fmt_value(m.get("interest_coverage"), "ratio"), "流动比率", _fmt_value(m.get("current_ratio"), "ratio")),
        ("商誉/总资产", _fmt_value(m.get("goodwill_ratio"), "pct"), "营业利润率稳定性 (CV)", _fmt_value(m.get("op_margin_cv"), "ratio")),
        ("营收 4yr CAGR", _fmt_value(m.get("rev_cagr_4y"), "pct"), "净利润 4yr CAGR", _fmt_value(m.get("ni_cagr_4y"), "pct")),
        ("FCF Yield", _fmt_value(m.get("fcf_yield"), "pct"), "P/FCF", _fmt_value(m.get("p_to_fcf"), "ratio")),
        ("YTD 回报", _fmt_value(m.get("return_ytd"), "pct"), "近1年回报", _fmt_value(m.get("return_1y"), "pct")),
        ("近3年回报", _fmt_value(m.get("return_3y"), "pct"), "近3年最大回撤", _fmt_value(m.get("max_drawdown_3y"), "pct")),
        ("股息收益率", _fmt_value(m.get("dividend_yield"), "pct"), "派息率", _fmt_value(m.get("payout_ratio"), "pct")),
        ("内部人持股", _fmt_value(m.get("insider_pct"), "pct"), "Beta", _fmt_value(m.get("beta"), "ratio")),
    ]
    for r in rows:
        lines.append(f"| {r[0]} | {r[1]} | {r[2]} | {r[3]} |")
    lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("## 📈 技术参考 (非 Buffett 流，仅做择时参考)")
    lines.append("")
    lines.append(f"- **价格 vs 200日均线**: {_fmt_value(m.get('price_vs_200ma'), 'pct')}")
    lines.append(f"- **RSI(14)**: {_fmt_value(m.get('rsi_14'), 'ratio')}")
    lines.append(f"- **52周高/低**: {_fmt_money(m.get('52w_high'))} / {_fmt_money(m.get('52w_low'))}")
    lines.append(f"- **距52周高位**: {_fmt_value(m.get('pct_from_52w_high'), 'pct')}")
    lines.append(f"- **距52周低位**: {_fmt_value(m.get('pct_from_52w_low'), 'pct')}")
    lines.append(f"- **分析师建议**: {m.get('recommendation') or 'N/A'} | **目标均价**: {_fmt_money(m.get('target_mean'))}")
    lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("## 🏷️ 标签说明")
    lines.append("")
    lines.append("- 🦬 Buffett = Buffett 公开认可或长期强调的指标")
    lines.append("- 🧠 Munger = Munger 公开论述的质量/护城河指标")
    lines.append("- 📘 Graham = Graham 传统安全边际/财务稳健指标")
    lines.append("- 📈 Lynch = Peter Lynch 增长和 PEG 思路")
    lines.append("- 🏛️ Damodaran = Damodaran 估值框架")
    lines.append("- ⚙️ 通用 = 通用财务或学术指标")
    lines.append("- ❌🦬 技术参考 = Buffett 不依赖技术分析，因此只占 5 分")
    lines.append("")
    lines.append(f"*报告生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*  ")
    _source = m.get("data_source") or "yfinance"
    _src_label = {
        "xueqiu": "雪球 xueqiu.com (A股主源)",
        "akshare": "akshare → 新浪/百度 (A股兜底)",
        "yfinance": "Yahoo Finance via yfinance (美/港股)",
    }.get(_source, _source)
    lines.append(f"*数据源: {_src_label}*")
    lines.append("")

    return "\n".join(lines)


def save_report(m: Dict[str, Any], scoring: Dict[str, Any], output_dir: Path = None) -> Path:
    out_dir = output_dir or REPORTS_DIR
    out_dir.mkdir(exist_ok=True)
    ticker = m["ticker"]
    name = _safe_filename(m.get("name") or ticker)
    score_str = f"{scoring['total']:05.1f}"
    path = out_dir / f"{score_str}_{ticker}_{name}.md"
    path.write_text(gen_report(m, scoring), encoding="utf-8")
    return path


def save_summary_csv(rows: List[Dict[str, Any]], suffix: str = "", output_dir: Path = None) -> Path:
    out_dir = output_dir or REPORTS_DIR
    out_dir.mkdir(exist_ok=True)
    rows = sorted(rows, key=lambda r: r.get("total_score", 0), reverse=True)
    date_str = datetime.now().strftime("%Y-%m-%d")
    fname = f"{out_dir.name}_summary" if output_dir else f"_summary_{date_str}"
    if suffix:
        fname += f"_{suffix}"
    path = out_dir / f"{fname}.csv"

    if not rows:
        path.write_text("ticker,total_score\n(no results)\n", encoding="utf-8")
        return path

    fields = [
        "rank", "ticker", "name", "sector", "total_score",
        "currency", "financial_currency", "data_source",
        "buffett_score", "strength_score", "growth_score", "valuation_score",
        "moat_score", "technical_score",
        "market_cap", "current_price",
        "pe_ttm", "pe_forward", "peg",
        "roe_avg", "roic", "op_margin_avg", "net_margin",
        "fcf_yield", "p_to_fcf",
        "debt_to_equity", "lt_debt_to_ni",
        "ni_cagr_4y", "rev_cagr_4y",
        "price_vs_200ma", "rsi_14",
        "return_ytd", "return_1y", "return_3y", "max_drawdown_3y",
        "passed", "fail_reasons",
    ]
    try:
        f = path.open("w", newline="", encoding="utf-8-sig")
    except PermissionError:
        fallback = out_dir / f"{fname}_{datetime.now().strftime('%H%M%S')}.csv"
        f = fallback.open("w", newline="", encoding="utf-8-sig")
        path = fallback

    with f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for i, row in enumerate(rows, 1):
            row["rank"] = i
            writer.writerow(row)
    return path
