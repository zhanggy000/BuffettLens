"""对比 5 只 A 股: 雪球 vs akshare(新浪) 数据源 + BuffettLens 评分差异."""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from screener.xueqiu_fetcher import fetch_xueqiu
from screener.ashare_fetcher import fetch_ashare
from screener import metrics as M, scorer as S

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

TICKERS = [
    ("600519.SS", "贵州茅台"),
    ("300502.SZ", "新易盛"),
    ("601899.SS", "紫金矿业"),
    ("300274.SZ", "阳光电源"),
    ("000651.SZ", "格力电器"),
]
CN_10Y = 1.7


def run_one(tk, name):
    print(f"\n========== {tk}  {name} ==========")
    # ---- 雪球 ----
    t0 = time.time()
    try:
        raw_xq = fetch_xueqiu(tk)
        t_xq = time.time() - t0
    except Exception as e:
        print(f"雪球 抓取失败: {e}")
        raw_xq = None
        t_xq = 0
    # ---- akshare ----
    t0 = time.time()
    try:
        raw_ak = fetch_ashare(tk)
        t_ak = time.time() - t0
    except Exception as e:
        print(f"akshare 抓取失败: {e}")
        raw_ak = None
        t_ak = 0

    rows = []
    for label, raw, t in [("雪球", raw_xq, t_xq), ("akshare", raw_ak, t_ak)]:
        if raw is None:
            rows.append((label, None, None))
            continue
        m = M.compute_metrics(raw, treasury_10y=CN_10Y)
        passed, reasons = S.hard_gates(m)
        sc = S.score(m)
        rows.append((label, m, sc))
        print(f"\n--- {label} ({t:.1f}s) ---")
        roe_s = m.get("roe_series") or []
        roe_str = "  ".join(f"{v*100:.2f}%" if v else "NA" for v in roe_s)
        print(f"  ROE 序列(新→旧): {roe_str}")
        print(f"  ROE 均值: {(m.get('roe_avg') or 0)*100:.2f}%   ROIC: {(m.get('roic') or 0)*100:.2f}%")
        print(f"  PE TTM: {m.get('pe_ttm')}   PB: {m.get('pb')}")
        print(f"  OpMargin avg: {(m.get('op_margin_avg') or 0)*100:.2f}%   NetMargin: {(m.get('net_margin') or 0)*100:.2f}%")
        print(f"  D/E: {m.get('debt_to_equity')}   CurrentRatio: {m.get('current_ratio')}")
        print(f"  IntCov: {m.get('interest_coverage')}   FCF/NI: {m.get('fcf_to_ni')}")
        print(f"  通过硬门槛: {passed}  {('原因: '+'; '.join(reasons)) if reasons else ''}")
        print(f"  总分: {sc['total']}  A/B/C/D/E/F = "
              f"{sc['categories'][0]['score']}/{sc['categories'][1]['score']}/{sc['categories'][2]['score']}/"
              f"{sc['categories'][3]['score']}/{sc['categories'][4]['score']}/{sc['categories'][5]['score']}")

    # 差异表
    if rows[0][1] is not None and rows[1][1] is not None:
        m_xq, sc_xq = rows[0][1], rows[0][2]
        m_ak, sc_ak = rows[1][1], rows[1][2]
        print(f"\n>>> 差异:")
        print(f"    总分:  雪球={sc_xq['total']:.0f}   akshare={sc_ak['total']:.0f}   Δ={sc_xq['total']-sc_ak['total']:+.0f}")
        def pct(v): return f"{v*100:.2f}%" if v else "NA"
        print(f"    ROE均值: 雪球={pct(m_xq.get('roe_avg'))}  akshare={pct(m_ak.get('roe_avg'))}")
        print(f"    ROIC:    雪球={pct(m_xq.get('roic'))}  akshare={pct(m_ak.get('roic'))}")
        print(f"    OpMargin: 雪球={pct(m_xq.get('op_margin_avg'))}  akshare={pct(m_ak.get('op_margin_avg'))}")


def main():
    for tk, name in TICKERS:
        run_one(tk, name)
        time.sleep(1.2)  # 雪球速率限制


if __name__ == "__main__":
    main()
