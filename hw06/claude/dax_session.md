# Part D — Claude session (measure 9: AUM-Weighted Alpha)

## Prompt
> Here is my model metadata (see `model_metadata.md`). `fact_portfolio_snapshot` has one row per client per month (`snapshot_date` = first of month, 60 months 2020-01 to 2024-12). `aum` is a balance — not additive over time. `active_alpha_ytd` is year-to-date (decimal: 0.02 = 2%). Write a DAX measure **AUM-Weighted Alpha**: `active_alpha_ytd` weighted by `aum`, at the last snapshot date in the current filter, excluding `is_return_suspect = 1`. Explain its filter context and give a DAX test query.

## Claude's response (first draft)
```DAX
AUM-Weighted Alpha =
VAR LastDate = LASTNONBLANK ( dim_date[date], CALCULATE ( SUM ( fact_portfolio_snapshot[aum] ) ) )
RETURN
CALCULATE (
    DIVIDE (
        SUMX ( fact_portfolio_snapshot, fact_portfolio_snapshot[aum] * fact_portfolio_snapshot[active_alpha_ytd] ),
        SUM ( fact_portfolio_snapshot[aum] )
    ),
    LastDate,
    fact_portfolio_snapshot[is_return_suspect] <> 1,
    NOT ISBLANK ( fact_portfolio_snapshot[active_alpha_ytd] )
)
```
**Filter context (Claude's explanation):** `LASTNONBLANK` runs in the outer filter context (e.g. a year or a tier), scans the dates visible there, and keeps the last one with snapshot data. `CALCULATE` then replaces the date filter with that single date and adds a filter `is_return_suspect <> 1`. Inside, `SUMX` iterates the remaining rows, multiplies aum × alpha, and divides by the AUM of the same rows, so the weights and the numerator use exactly the same population. Without the last-date filter, a year would mix 12 YTD values; without the suspect filter, a handful of corrupt alphas would dominate.

**Test query:**
```DAX
EVALUATE
SUMMARIZECOLUMNS ( dim_date[year], "Weighted Alpha", [AUM-Weighted Alpha], "Signal", [Alpha Signal] )
```

## Second turn
> Power BI says "The syntax for 'LastDate' is incorrect."

Claude's response: the VAR line picked up hidden characters when pasted; rewrite without VAR, one line, using the same LASTNONBLANK pattern as the working `Ending AUM` (COUNTROWS instead of SUM — same last date, since every snapshot row has an aum). `NOT ISBLANK` filter dropped because `active_alpha_ytd` has no blanks (129,547 of 129,547 rows populated).
```DAX
AUM-Weighted Alpha = CALCULATE ( DIVIDE ( SUMX ( fact_portfolio_snapshot, fact_portfolio_snapshot[aum] * fact_portfolio_snapshot[active_alpha_ytd] ), SUM ( fact_portfolio_snapshot[aum] ) ), LASTNONBLANK ( dim_date[date], CALCULATE ( COUNTROWS ( fact_portfolio_snapshot ) ) ), fact_portfolio_snapshot[is_return_suspect] <> 1 )
```
