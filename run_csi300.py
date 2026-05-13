"""Run BuffettLens on the first N CSI 300 constituents by index weight."""
from __future__ import annotations

import argparse
import sys

from screener.run_screener import build_report_dir, run
from screener.universe import get_csi300

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run BuffettLens on top-N CSI 300 constituents.")
    parser.add_argument("--limit", type=int, default=50, help="number of CSI 300 constituents to run")
    parser.add_argument("--delay", "-d", type=float, default=2.0, help="request interval seconds")
    parser.add_argument("--force-refresh", "-f", action="store_true", help="ignore SQLite cache")
    parser.add_argument("--min-score", type=float, default=60, help="minimum score for report generation")
    parser.add_argument("--all-reports", action="store_true", help="generate reports for every processed stock")
    args = parser.parse_args()

    if args.limit <= 0:
        parser.error("--limit must be greater than 0")

    tickers = get_csi300()[:args.limit]
    print(f"CSI 300 top {len(tickers)} by index weight")
    output_dir = build_report_dir("csi300", args.limit, args.min_score)
    run(
        tickers,
        delay=args.delay,
        force_refresh=args.force_refresh,
        min_score=args.min_score,
        all_reports=args.all_reports,
        output_dir=output_dir,
    )


if __name__ == "__main__":
    main()
