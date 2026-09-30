"""Print NVDA quarterly Total Revenue and Net Income (raw dollars) for every
quarter Yahoo Finance returns.

Requires: pip install yfinance pandas
"""

import math

import yfinance as yf

TICKER = "NVDA"
METRICS = ["Total Revenue", "Net Income"]


def fmt_dollars(value) -> str:
    """Format a number as raw dollars with thousands separators, or N/A."""
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "N/A"
    return f"${int(value):,}"


def main() -> None:
    ticker = yf.Ticker(TICKER)

    # Rows are line items, columns are quarter-end dates (newest first).
    stmt = ticker.quarterly_income_stmt
    if stmt is None or stmt.empty:
        raise SystemExit(f"No quarterly income statement data returned for {TICKER}.")

    missing = [m for m in METRICS if m not in stmt.index]
    if missing:
        raise SystemExit(
            f"Missing line items {missing}. Available rows:\n" + "\n".join(stmt.index)
        )

    # Transpose so each row is a quarter; sort oldest -> newest.
    data = stmt.loc[METRICS].T.sort_index()

    print(f"{TICKER} quarterly results ({len(data)} quarters available)\n")
    print(f"{'Quarter End':<12} {'Total Revenue':>22} {'Net Income':>22}")
    print("-" * 58)
    for quarter_end, row in data.iterrows():
        print(
            f"{quarter_end.strftime('%Y-%m-%d'):<12} "
            f"{fmt_dollars(row['Total Revenue']):>22} "
            f"{fmt_dollars(row['Net Income']):>22}"
        )


if __name__ == "__main__":
    main()
