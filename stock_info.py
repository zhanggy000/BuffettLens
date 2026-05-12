"""
股票数据查询工具 (Stock Info Fetcher)
========================================
用法:
  python stock_info.py                          # 交互模式
  python stock_info.py NVDA GOOGL MSFT          # 命令行参数
  python stock_info.py NVDA --save              # 导出JSON
  python stock_info.py NVDA --buffett           # 显示巴菲特评分卡

数据源: Yahoo Finance (实时)
依赖: pip install yfinance
"""

import sys
import json
import argparse
from datetime import datetime
from pathlib import Path

try:
    import yfinance as yf
except ImportError:
    print("❌ 需要先安装 yfinance")
    print("   请运行: pip install yfinance")
    sys.exit(1)


# ============== 格式化辅助函数 ==============

def fmt_number(num, currency=True, decimals=2):
    """格式化大数字: 1.23T / 4.56B / 7.89M"""
    if num is None:
        return "N/A"
    try:
        num = float(num)
        prefix = "$" if currency else ""
        if abs(num) >= 1e12:
            return f"{prefix}{num/1e12:.{decimals}f}T"
        elif abs(num) >= 1e9:
            return f"{prefix}{num/1e9:.{decimals}f}B"
        elif abs(num) >= 1e6:
            return f"{prefix}{num/1e6:.{decimals}f}M"
        elif abs(num) >= 1e3:
            return f"{prefix}{num/1e3:.{decimals}f}K"
        return f"{prefix}{num:,.{decimals}f}"
    except (ValueError, TypeError):
        return "N/A"


def fmt_pct(num, already_percent=False):
    """格式化百分比. yfinance里部分字段是小数(0.15), 部分是百分比(15)"""
    if num is None:
        return "N/A"
    try:
        v = float(num)
        if not already_percent:
            v *= 100
        return f"{v:.2f}%"
    except (ValueError, TypeError):
        return "N/A"


def fmt_price(num):
    if num is None:
        return "N/A"
    try:
        return f"${float(num):,.2f}"
    except (ValueError, TypeError):
        return "N/A"


def fmt_ratio(num, decimals=2):
    if num is None:
        return "N/A"
    try:
        return f"{float(num):.{decimals}f}"
    except (ValueError, TypeError):
        return "N/A"


def safe_get(info, key, default=None):
    """安全获取字典值"""
    val = info.get(key, default)
    if val == "Infinity" or val == "-Infinity":
        return None
    return val


# ============== 巴菲特/芒格评分卡 ==============

def buffett_scorecard(info):
    """根据巴菲特/芒格标准给股票打分"""
    score = 0
    max_score = 7
    details = []

    # 1. PE < 25
    pe = safe_get(info, "trailingPE")
    pe_str = f"{pe:.1f}" if pe else "N/A"
    if pe and pe < 25:
        score += 1
        details.append(("✅", f"PE比率 {pe_str} < 25"))
    elif pe and pe < 35:
        details.append(("⚠️ ", f"PE比率 {pe_str} 偏高 (Buffett喜欢<25)"))
    else:
        details.append(("❌", f"PE比率 {pe_str} 太高"))

    # 2. ROE > 15%
    roe = safe_get(info, "returnOnEquity")
    roe_str = f"{roe*100:.1f}%" if roe else "N/A"
    if roe and roe > 0.15:
        score += 1
        details.append(("✅", f"ROE {roe_str} > 15%"))
    else:
        details.append(("❌", f"ROE {roe_str} 不足15%"))

    # 3. 净利率 > 10%
    margin = safe_get(info, "profitMargins")
    margin_str = f"{margin*100:.1f}%" if margin else "N/A"
    if margin and margin > 0.10:
        score += 1
        details.append(("✅", f"净利率 {margin_str} > 10%"))
    else:
        details.append(("❌", f"净利率 {margin_str} 不足10%"))

    # 4. Debt/Equity < 1.0 (即 <100)
    de = safe_get(info, "debtToEquity")
    de_str = f"{de:.0f}%" if de is not None else "N/A"
    if de is not None and de < 100:
        score += 1
        details.append(("✅", f"负债/股本 {de_str} < 100%"))
    else:
        details.append(("❌", f"负债/股本 {de_str} 偏高"))

    # 5. 自由现金流 > 0
    fcf = safe_get(info, "freeCashflow")
    if fcf and fcf > 0:
        score += 1
        details.append(("✅", f"自由现金流 {fmt_number(fcf)} > 0"))
    else:
        details.append(("❌", "自由现金流 ≤ 0 或缺失"))

    # 6. 营收增长 > 5%
    rev_growth = safe_get(info, "revenueGrowth")
    rev_str = f"{rev_growth*100:.1f}%" if rev_growth else "N/A"
    if rev_growth and rev_growth > 0.05:
        score += 1
        details.append(("✅", f"营收增长 {rev_str} > 5%"))
    else:
        details.append(("❌", f"营收增长 {rev_str} 不足5%"))

    # 7. 当前价格 < 200日均线*1.2 (不过度狂热)
    price = safe_get(info, "currentPrice") or safe_get(info, "regularMarketPrice")
    ma200 = safe_get(info, "twoHundredDayAverage")
    if price and ma200 and price < ma200 * 1.2:
        score += 1
        details.append(("✅", f"价格未过度高于200日均线"))
    else:
        details.append(("⚠️ ", f"价格高于200日均线20%以上,可能短期过热"))

    return score, max_score, details


# ============== 核心查询函数 ==============

def fetch_stock(ticker, show_buffett=False):
    """获取并打印单个股票数据"""
    sep = "=" * 70
    print(f"\n{sep}")
    print(f"  🔍 {ticker.upper()}")
    print(sep)

    try:
        stock = yf.Ticker(ticker)
        info = stock.info

        # 基本验证: 如果连名字都没有,可能是无效ticker
        name = info.get("longName") or info.get("shortName")
        if not name:
            print(f"❌ 找不到股票代码 {ticker} (或Yahoo Finance无数据)")
            return None

        # ----- 公司基本信息 -----
        print(f"\n📊 公司: {name}")
        print(f"🏢 行业: {info.get('industry', 'N/A')} | 板块: {info.get('sector', 'N/A')}")
        print(f"🌍 国家: {info.get('country', 'N/A')}")
        employees = info.get("fullTimeEmployees")
        if employees:
            print(f"👥 员工: {employees:,}")

        # ----- 价格 -----
        price = safe_get(info, "currentPrice") or safe_get(info, "regularMarketPrice")
        prev_close = safe_get(info, "previousClose")
        change_pct = None
        if price and prev_close:
            change_pct = (price - prev_close) / prev_close * 100

        print(f"\n💰 价格")
        if change_pct is not None:
            arrow = "🔺" if change_pct >= 0 else "🔻"
            print(f"  当前价:    {fmt_price(price)} {arrow} {change_pct:+.2f}%")
        else:
            print(f"  当前价:    {fmt_price(price)}")
        print(f"  52周高:    {fmt_price(info.get('fiftyTwoWeekHigh'))}")
        print(f"  52周低:    {fmt_price(info.get('fiftyTwoWeekLow'))}")
        print(f"  50日均线:  {fmt_price(info.get('fiftyDayAverage'))}")
        print(f"  200日均线: {fmt_price(info.get('twoHundredDayAverage'))}")

        # ----- 估值 -----
        print(f"\n📈 估值")
        print(f"  市值:        {fmt_number(info.get('marketCap'))}")
        print(f"  企业价值:    {fmt_number(info.get('enterpriseValue'))}")
        print(f"  TTM PE:      {fmt_ratio(info.get('trailingPE'))}")
        print(f"  Forward PE:  {fmt_ratio(info.get('forwardPE'))}")
        print(f"  PEG:         {fmt_ratio(info.get('trailingPegRatio') or info.get('pegRatio'))}")
        print(f"  P/B:         {fmt_ratio(info.get('priceToBook'))}")
        print(f"  P/S (TTM):   {fmt_ratio(info.get('priceToSalesTrailing12Months'))}")
        print(f"  EV/EBITDA:   {fmt_ratio(info.get('enterpriseToEbitda'))}")
        print(f"  EV/营收:     {fmt_ratio(info.get('enterpriseToRevenue'))}")

        # ----- 盈利能力 -----
        print(f"\n💵 盈利能力")
        print(f"  EPS (TTM):    ${fmt_ratio(info.get('trailingEps'))}")
        print(f"  EPS Forward:  ${fmt_ratio(info.get('forwardEps'))}")
        print(f"  毛利率:       {fmt_pct(info.get('grossMargins'))}")
        print(f"  营业利润率:   {fmt_pct(info.get('operatingMargins'))}")
        print(f"  净利率:       {fmt_pct(info.get('profitMargins'))}")
        print(f"  ROE:          {fmt_pct(info.get('returnOnEquity'))}")
        print(f"  ROA:          {fmt_pct(info.get('returnOnAssets'))}")

        # ----- 增长 -----
        print(f"\n📊 增长 (YoY)")
        print(f"  季度营收增长: {fmt_pct(info.get('revenueGrowth'))}")
        print(f"  季度利润增长: {fmt_pct(info.get('earningsGrowth'))}")
        print(f"  EPS季度增长:  {fmt_pct(info.get('earningsQuarterlyGrowth'))}")

        # ----- 股息 -----
        div_rate = info.get("dividendRate")
        if div_rate and price:
            # 直接用年股息/价格计算,避免yfinance字段不一致
            calc_yield = div_rate / price * 100
            print(f"\n💎 股息")
            print(f"  股息率:     {calc_yield:.2f}%")
            print(f"  年股息:     ${fmt_ratio(div_rate)}")
            print(f"  派息比率:   {fmt_pct(info.get('payoutRatio'))}")
            avg_yield = info.get("fiveYearAvgDividendYield")
            if avg_yield:
                print(f"  5年均收益:  {avg_yield:.2f}%")

        # ----- 资产负债表 -----
        print(f"\n🏦 资产负债表")
        print(f"  总现金:       {fmt_number(info.get('totalCash'))}")
        print(f"  总债务:       {fmt_number(info.get('totalDebt'))}")
        de = info.get("debtToEquity")
        print(f"  负债/股本:    {f'{de:.0f}%' if de else 'N/A'}")
        print(f"  流动比率:     {fmt_ratio(info.get('currentRatio'))}")
        print(f"  速动比率:     {fmt_ratio(info.get('quickRatio'))}")
        print(f"  每股账面值:   ${fmt_ratio(info.get('bookValue'))}")

        # ----- 现金流 -----
        print(f"\n💸 现金流")
        print(f"  经营现金流:   {fmt_number(info.get('operatingCashflow'))}")
        print(f"  自由现金流:   {fmt_number(info.get('freeCashflow'))}")

        # ----- 分析师 -----
        print(f"\n👔 分析师")
        rec = info.get("recommendationKey", "N/A")
        rec_map = {
            "strong_buy": "强烈买入",
            "buy": "买入",
            "hold": "持有",
            "sell": "卖出",
            "strong_sell": "强烈卖出",
            "underperform": "跑输大盘",
            "outperform": "跑赢大盘",
        }
        print(f"  推荐:         {rec_map.get(rec, rec)}")
        target_mean = info.get("targetMeanPrice")
        if target_mean and price:
            upside = (target_mean - price) / price * 100
            print(f"  目标价(均):   {fmt_price(target_mean)} ({upside:+.1f}% 空间)")
        else:
            print(f"  目标价(均):   {fmt_price(target_mean)}")
        print(f"  目标价(高):   {fmt_price(info.get('targetHighPrice'))}")
        print(f"  目标价(低):   {fmt_price(info.get('targetLowPrice'))}")
        print(f"  分析师数量:   {info.get('numberOfAnalystOpinions', 'N/A')}")

        # ----- 最近4季度财报 -----
        try:
            fin = stock.quarterly_financials
            if not fin.empty:
                print(f"\n📋 最近季度财报")
                cols = list(fin.columns)[:4]
                # 表头
                header = "  指标          | " + " | ".join(
                    [c.strftime("%Y-%m-%d") if hasattr(c, "strftime") else str(c) for c in cols]
                )
                print(header)
                print("  " + "-" * (len(header) - 2))

                rows = [
                    ("Total Revenue", "营收"),
                    ("Gross Profit", "毛利"),
                    ("Operating Income", "营业利润"),
                    ("Net Income", "净利润"),
                ]
                for key, label in rows:
                    if key in fin.index:
                        values = [fmt_number(fin.loc[key, c]) for c in cols]
                        line = f"  {label:<10}    | " + " | ".join(f"{v:>10}" for v in values)
                        print(line)
        except Exception:
            pass

        # ----- 业务摘要 -----
        summary = info.get("longBusinessSummary")
        if summary:
            print(f"\n📝 业务摘要")
            # 截取前400字符
            text = summary[:400] + ("..." if len(summary) > 400 else "")
            print(f"  {text}")

        # ----- 巴菲特评分卡 -----
        if show_buffett:
            try:
                print(f"\n🎯 巴菲特/芒格 评分卡")
                score, max_score, details = buffett_scorecard(info)
                for icon, text in details:
                    print(f"  {icon} {text}")
                print(f"\n  📊 总分: {score}/{max_score}", end="")
                if score >= 6:
                    print("  → 🌟 高度符合巴菲特标准")
                elif score >= 4:
                    print("  → 👍 部分符合,可以关注")
                else:
                    print("  → ⚠️  不符合Buffett标准")
            except Exception as e:
                print(f"  ⚠️  评分卡生成失败: {e}")

        return info

    except Exception as e:
        print(f"❌ 错误: {e}")
        return None


# ============== 主程序 ==============

def main():
    parser = argparse.ArgumentParser(
        description="股票数据查询工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python stock_info.py NVDA GOOGL MSFT
  python stock_info.py NVDA --buffett
  python stock_info.py NVDA GOOGL --save
        """,
    )
    parser.add_argument("tickers", nargs="*", help="股票代码 (例如: NVDA GOOGL MSFT)")
    parser.add_argument("--buffett", action="store_true", help="显示巴菲特评分卡")
    parser.add_argument("--save", action="store_true", help="保存JSON到文件")
    args = parser.parse_args()

    header = "=" * 70
    print(header)
    print(f"  📈 股票数据查询工具  |  数据源: Yahoo Finance")
    print(f"  ⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(header)

    tickers = args.tickers
    if not tickers:
        user_input = input("\n请输入股票代码 (多个用空格分隔, 如 NVDA GOOGL MSFT):\n> ").strip()
        if not user_input:
            print("未输入,退出。")
            return
        tickers = user_input.split()

    results = {}
    for ticker in tickers:
        info = fetch_stock(ticker.upper(), show_buffett=args.buffett)
        if info:
            results[ticker.upper()] = info

    # 保存JSON
    if args.save and results:
        out_path = Path("stock_data_" + datetime.now().strftime("%Y%m%d_%H%M%S") + ".json")
        # 过滤掉无法序列化的对象
        clean = {}
        for t, data in results.items():
            clean[t] = {k: v for k, v in data.items() if isinstance(v, (str, int, float, bool, list, dict, type(None)))}
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(clean, f, ensure_ascii=False, indent=2)
        print(f"\n💾 已保存到 {out_path}")

    print(f"\n{header}")
    print(f"  ✅ 查询完成 (共 {len(results)} 只)")
    print(header)


if __name__ == "__main__":
    main()
