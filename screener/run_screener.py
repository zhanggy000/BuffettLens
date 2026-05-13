"""
主入口
========
用法:
  # 跑NASDAQ 100 (默认, 约5分钟)
  python -m screener.run_screener --universe ndx100

  # 跑S&P 500 (约25分钟)
  python -m screener.run_screener --universe sp500

  # 跑多个股票池
  python -m screener.run_screener --universe ndx100 sp500 csi300

  # 自定义ticker列表
  python -m screener.run_screener --tickers AAPL,MSFT,GOOGL

  # 调整请求间隔(默认2秒)
  python -m screener.run_screener --universe sp500 --delay 3

  # 只对通过硬门槛的生成报告 (默认行为)
  python -m screener.run_screener --universe ndx100 --min-score 60

  # 强制刷新缓存
  python -m screener.run_screener --universe ndx100 --force-refresh
"""

import argparse
import csv
import sys
import time
from datetime import datetime
from typing import Dict, List, Tuple

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from . import fetcher
from . import metrics as metrics_mod
from . import reporter
from . import scorer
from .universe import get_universe


def resolve_universes(universe_names: List[str]) -> Tuple[List[str], List[Dict[str, str]]]:
    """Expand universes, preserving first occurrence and recording skipped duplicates."""
    seen = set()
    tickers: List[str] = []
    duplicates: List[Dict[str, str]] = []

    for universe_name in universe_names:
        universe_tickers = get_universe(universe_name)
        for ticker in universe_tickers:
            ticker = ticker.strip().upper()
            if not ticker:
                continue
            if ticker in seen:
                duplicates.append({"ticker": ticker, "skipped_from": universe_name})
                continue
            seen.add(ticker)
            tickers.append(ticker)

    if len(universe_names) > 1 or duplicates:
        raw_count = len(tickers) + len(duplicates)
        print(
            f"Universe merge: raw={raw_count}, unique={len(tickers)}, "
            f"duplicates_skipped={len(duplicates)}"
        )

    return tickers, duplicates


def save_universe_duplicates(duplicates: List[Dict[str, str]]):
    if not duplicates:
        return None
    reporter.REPORTS_DIR.mkdir(exist_ok=True)
    date_str = datetime.now().strftime("%Y-%m-%d")
    path = reporter.REPORTS_DIR / f"_universe_duplicates_{date_str}.csv"
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=["ticker", "skipped_from"])
        writer.writeheader()
        writer.writerows(duplicates)
    return path


def run(tickers: List[str], delay: float = 2.0, force_refresh: bool = False,
        min_score: float = 0, all_reports: bool = False) -> None:
    print(f"\n{'=' * 60}")
    print(f"  BuffettLens 价值股筛选器")
    print(f"{'=' * 60}")
    print(f"  目标: {len(tickers)} 只股票")
    print(f"  请求间隔: {delay} 秒")
    print(f"  最低评分: {min_score} (低于此分不生成报告)")
    print(f"{'=' * 60}\n")

    removed = reporter.clear_report_markdown()
    if removed:
        print(f"  已清理旧 Markdown 报告: {removed} 个\n")

    # 获取10年期国债收益率 (按 ticker 市场自动区分: 美股=^TNX, A股=中国10Y)
    print("  获取 10年期国债收益率...")
    treasury_us = fetcher.get_10y_treasury_yield()
    treasury_cn = fetcher._CN_10Y_DEFAULT
    print(f"  US 10Y: {treasury_us:.2f}%   CN 10Y: {treasury_cn:.2f}%\n")

    summary_rows = []
    passed_count = 0
    failed_count = 0
    error_count = 0
    t_start = time.time()

    for i, ticker in enumerate(tickers, 1):
        print(f"[{i}/{len(tickers)}] {ticker} ... ", end="", flush=True)
        try:
            raw = fetcher.fetch_stock(ticker, force_refresh=force_refresh)
            if raw is None:
                print("✗ 抓取失败")
                error_count += 1
                # 请求间隔即使失败也保留(除非命中缓存)
                if i < len(tickers):
                    time.sleep(delay)
                continue

            t10y = treasury_cn if fetcher.xueqiu_fetcher.is_ashare(ticker) else treasury_us
            m = metrics_mod.compute_metrics(raw, treasury_10y=t10y)
            passed, fail_reasons = scorer.hard_gates(m)
            scoring = scorer.score(m)
            total = scoring["total"]

            row = {
                "ticker": ticker,
                "name": m.get("name"),
                "sector": m.get("sector"),
                "total_score": total,
                "buffett_score": scoring["categories"][0]["score"],
                "strength_score": scoring["categories"][1]["score"],
                "growth_score": scoring["categories"][2]["score"],
                "valuation_score": scoring["categories"][3]["score"],
                "moat_score": scoring["categories"][4]["score"],
                "technical_score": scoring["categories"][5]["score"],
                "market_cap": m.get("market_cap"),
                "current_price": m.get("current_price"),
                "pe_ttm": m.get("pe_ttm"),
                "pe_forward": m.get("pe_forward"),
                "peg": m.get("peg"),
                "roe_avg": m.get("roe_avg"),
                "roic": m.get("roic"),
                "op_margin_avg": m.get("op_margin_avg"),
                "net_margin": m.get("net_margin"),
                "fcf_yield": m.get("fcf_yield"),
                "p_to_fcf": m.get("p_to_fcf"),
                "debt_to_equity": m.get("debt_to_equity"),
                "lt_debt_to_ni": m.get("lt_debt_to_ni"),
                "ni_cagr_4y": m.get("ni_cagr_4y"),
                "rev_cagr_4y": m.get("rev_cagr_4y"),
                "price_vs_200ma": m.get("price_vs_200ma"),
                "rsi_14": m.get("rsi_14"),
                "return_ytd": m.get("return_ytd"),
                "return_1y": m.get("return_1y"),
                "return_3y": m.get("return_3y"),
                "max_drawdown_3y": m.get("max_drawdown_3y"),
                "passed": passed,
                "fail_reasons": "; ".join(fail_reasons) if fail_reasons else "",
            }
            summary_rows.append(row)

            # 生成报告
            should_report = (passed and total >= min_score) or all_reports
            if should_report:
                path = reporter.save_report(m, scoring)
                stars, _ = scorer.rating_stars(total)
                print(f"✓ {total:5.1f}分 {stars}  → {path.name}")
                passed_count += 1
            elif not passed:
                print(f"✗ 未通过硬门槛: {fail_reasons[0] if fail_reasons else ''}")
                failed_count += 1
            else:
                print(f"-  {total:5.1f}分 (低于 min-score)")
                failed_count += 1

        except Exception as e:
            print(f"✗ 错误: {e}")
            error_count += 1
            import traceback
            traceback.print_exc()

        # 节流 (命中缓存的也保持一个小间隔, 避免下次失败太密)
        if i < len(tickers):
            cached = fetcher._cache_get(ticker)
            time.sleep(0.1 if cached else delay)

    # 保存总览CSV
    csv_path = reporter.save_summary_csv(summary_rows)

    elapsed = time.time() - t_start
    print(f"\n{'=' * 60}")
    print(f"  完成! 总耗时: {elapsed / 60:.1f} 分钟")
    print(f"{'=' * 60}")
    print(f"  通过并生成报告: {passed_count}")
    print(f"  未通过 / 分数过低: {failed_count}")
    print(f"  抓取/计算错误: {error_count}")
    print(f"  总览CSV: {csv_path}")
    print(f"  报告目录: {reporter.REPORTS_DIR}")
    print(f"{'=' * 60}\n")

    # Top 10 提示
    top = sorted([r for r in summary_rows if r["passed"]],
                 key=lambda r: r["total_score"], reverse=True)[:10]
    if top:
        print("🏆 Top 10 (通过硬门槛):")
        for i, r in enumerate(top, 1):
            print(f"  {i:2d}. {r['total_score']:5.1f}  {r['ticker']:6}  {r['name']}")
        print()


def main():
    p = argparse.ArgumentParser(description="BuffettLens 价值股筛选器")
    grp = p.add_mutually_exclusive_group()
    grp.add_argument("--universe", "-u", nargs="+",
                     choices=["sp500", "ndx100", "csi300", "all"],
                     default=["ndx100"], help="股票池，可传多个 (默认: ndx100)")
    grp.add_argument("--tickers", "-t", type=str,
                     help="自定义ticker列表, 逗号分隔 (例如: AAPL,MSFT,GOOGL)")

    p.add_argument("--delay", "-d", type=float, default=2.0,
                   help="请求间隔(秒, 默认2.0)")
    p.add_argument("--force-refresh", "-f", action="store_true",
                   help="强制刷新缓存")
    p.add_argument("--min-score", type=float, default=60,
                   help="最低评分阈值, 低于此分不生成报告 (默认60)")
    p.add_argument("--all-reports", action="store_true",
                   help="为所有股票生成报告(包括未通过的, 仅供调试)")
    p.add_argument("--limit", type=int, default=0,
                   help="限制处理数量 (用于测试, 0=不限)")

    args = p.parse_args()

    if args.tickers:
        tickers = [t.strip().upper() for t in args.tickers.split(",") if t.strip()]
        duplicates = []
    else:
        tickers, duplicates = resolve_universes(args.universe)
        duplicate_path = save_universe_duplicates(duplicates)
        if duplicate_path:
            print(f"Duplicate universe tickers skipped: {duplicate_path}")

    if args.limit > 0:
        tickers = tickers[:args.limit]

    if not tickers:
        print("❌ 股票列表为空")
        sys.exit(1)

    run(tickers, delay=args.delay, force_refresh=args.force_refresh,
        min_score=args.min_score, all_reports=args.all_reports)


if __name__ == "__main__":
    main()
