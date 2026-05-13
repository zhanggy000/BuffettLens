"""Run BuffettLens on top 50 CSI 300 by index weight."""
from __future__ import annotations

import sys
import time
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from screener import fetcher, metrics as M, scorer as S, reporter
from screener.ashare_fetcher import _parse_code

XLS = Path(__file__).resolve().parent / "data" / "000300closeweight.xls"
TOP_N = 50
CN_10Y = 1.7  # 中国10年期国债收益率近似 (2026 年中位水平)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def build_tickers(n: int) -> list[tuple[str, str, float]]:
    df = pd.read_excel(XLS)
    df = df.sort_values("权重(%)weight", ascending=False).reset_index(drop=True)
    df = df.head(n)
    out = []
    for _, r in df.iterrows():
        code = str(r["成份券代码Constituent Code"]).zfill(6)
        name = str(r["成份券名称Constituent Name"])
        weight = float(r["权重(%)weight"])
        exch = str(r["交易所Exchange"])
        suffix = ".SS" if "上海" in exch else ".SZ"
        out.append((f"{code}{suffix}", name, weight))
    return out


def main():
    tickers = build_tickers(TOP_N)
    print(f"准备跑 {len(tickers)} 只 A 股 (CSI 300 前 {TOP_N} 大权重)")
    print(f"使用 10Y 国债收益率: {CN_10Y}% (中国)")
    print("=" * 70)

    rows = []
    t0 = time.time()
    for i, (tk, hint_name, weight) in enumerate(tickers, 1):
        t_one = time.time()
        print(f"[{i:2d}/{len(tickers)}] {tk} ({hint_name}) ... ", end="", flush=True)
        try:
            raw = fetcher.fetch_stock(tk, force_refresh=True)
            if raw is None:
                print("FETCH FAIL")
                rows.append({"rank_weight": i, "ticker": tk, "name": hint_name, "weight": weight,
                             "total_score": None, "status": "FETCH_FAIL"})
                continue
            m = M.compute_metrics(raw, treasury_10y=CN_10Y)
            passed, reasons = S.hard_gates(m)
            sc = S.score(m)
            total = sc["total"]
            stars, _ = S.rating_stars(total)
            print(f"{total:5.1f} {stars}  ({time.time()-t_one:.1f}s)  {'✓' if passed else '✗ ' + (reasons[0] if reasons else '')}")
            rows.append({
                "rank_weight": i,
                "ticker": tk,
                "name": m.get("name") or hint_name,
                "weight": weight,
                "data_source": m.get("data_source") or "unknown",
                "total_score": total,
                "buffett_A": sc["categories"][0]["score"],
                "strength_B": sc["categories"][1]["score"],
                "growth_C": sc["categories"][2]["score"],
                "valuation_D": sc["categories"][3]["score"],
                "moat_E": sc["categories"][4]["score"],
                "tech_F": sc["categories"][5]["score"],
                "passed": passed,
                "fail_reasons": "; ".join(reasons),
                "pe_ttm": m.get("pe_ttm"),
                "pb": m.get("pb"),
                "roe_avg": m.get("roe_avg"),
                "roic": m.get("roic"),
                "op_margin_avg": m.get("op_margin_avg"),
                "net_margin": m.get("net_margin"),
                "ni_cagr_4y": m.get("ni_cagr_4y"),
                "rev_cagr_4y": m.get("rev_cagr_4y"),
                "fcf_yield": m.get("fcf_yield"),
                "debt_to_equity": m.get("debt_to_equity"),
                "price_vs_200ma": m.get("price_vs_200ma"),
                "rsi_14": m.get("rsi_14"),
                "market_cap_b": (m.get("market_cap") or 0) / 1e9,
                "current_price": m.get("current_price"),
                "status": "OK",
            })
            # 顺便存详细报告
            try:
                reporter.save_report(m, sc)
            except Exception as e:
                print(f"    (report fail: {e})")
        except Exception as e:
            print(f"ERROR: {e}")
            rows.append({"rank_weight": i, "ticker": tk, "name": hint_name, "weight": weight,
                         "total_score": None, "status": f"ERR: {e}"})

    out_df = pd.DataFrame(rows)
    out_path = Path("reports") / "csi300_top50_scored.csv"
    out_path.parent.mkdir(exist_ok=True)
    out_df.to_csv(out_path, index=False, encoding="utf-8-sig")
    print()
    print("=" * 70)
    print(f"总耗时 {(time.time()-t0)/60:.1f} 分钟")
    print(f"CSV: {out_path}")

    # Top 排行
    ok = out_df[out_df["total_score"].notna()].sort_values("total_score", ascending=False)
    print()
    print("按 BuffettLens 总分排名:")
    print(f"{'排名':>4} {'权重#':>4}  {'代码':<11} {'名称':<14} {'权重%':>5}  {'总分':>5}  A/B/C/D/E/F  数据源")
    for i, (_, r) in enumerate(ok.iterrows(), 1):
        cats = f"{r['buffett_A']:.0f}/{r['strength_B']:.0f}/{r['growth_C']:.0f}/{r['valuation_D']:.0f}/{r['moat_E']:.0f}/{r['tech_F']:.0f}"
        src = r.get('data_source','?')
        print(f"{i:>4} {r['rank_weight']:>4}  {r['ticker']:<11} {r['name']:<14} {r['weight']:>5.2f}  {r['total_score']:>5.1f}  {cats}  {src}")


if __name__ == "__main__":
    main()
