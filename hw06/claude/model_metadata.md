# Model metadata (hw06.pbix)

## Tables

| Table | Rows |
|---|---:|
| dim_advisor | 25 |
| dim_benchmark | 8 |
| dim_client | 2500 |
| dim_date | 1827 |
| dim_security | 500 |
| fact_fees | 122197 |
| fact_portfolio_snapshot | 129547 |
| fact_transactions | 298572 |

## Columns

| Table | Column | Data type |
|---|---|---|
| dim_advisor | advisor_id | Int64 |
| dim_advisor | first_name | string |
| dim_advisor | last_name | string |
| dim_advisor | region | string |
| dim_advisor | years_experience | Int64 |
| dim_advisor | aum_target_mm | Int64 |
| dim_advisor | certifications | string |
| dim_benchmark | benchmark_id | Int64 |
| dim_benchmark | name | string |
| dim_benchmark | asset_class | string |
| dim_benchmark | ticker_proxy | string |
| dim_client | client_id | Int64 |
| dim_client | first_name | string |
| dim_client | last_name | string |
| dim_client | age | Int64 |
| dim_client | city | string |
| dim_client | state | string |
| dim_client | zip_code | string |
| dim_client | risk_profile | string |
| dim_client | client_tier | string |
| dim_client | primary_account_type | string |
| dim_client | initial_aum | Float64 |
| dim_client | client_since | datetime64[ns] |
| dim_client | advisor_id | Int64 |
| dim_client | is_active | bool |
| dim_date | date_id | Int64 |
| dim_date | date | datetime64[ns] |
| dim_date | year | Int64 |
| dim_date | quarter | Int64 |
| dim_date | month | Int64 |
| dim_date | month_name | string |
| dim_date | week_of_year | Int64 |
| dim_date | day_of_week | string |
| dim_date | is_month_end | Int64 |
| dim_date | is_quarter_end | Int64 |
| dim_date | is_year_end | Int64 |
| dim_date | is_trading_day | Int64 |
| dim_security | security_id | Int64 |
| dim_security | ticker | string |
| dim_security | name | string |
| dim_security | asset_class | string |
| dim_security | sector | string |
| dim_security | benchmark_id | Int64 |
| dim_security | is_etf | bool |
| dim_security | expense_ratio_bps | Int64 |
| fact_fees | fee_id | Int64 |
| fact_fees | client_id | Int64 |
| fact_fees | advisor_id | Int64 |
| fact_fees | fee_date | datetime64[ns] |
| fact_fees | fee_type | string |
| fact_fees | aum_basis | Float64 |
| fact_fees | bps_charged | Float64 |
| fact_fees | amount | Float64 |
| fact_portfolio_snapshot | snapshot_id | Int64 |
| fact_portfolio_snapshot | client_id | Int64 |
| fact_portfolio_snapshot | advisor_id | Int64 |
| fact_portfolio_snapshot | benchmark_id | Int64 |
| fact_portfolio_snapshot | snapshot_date | datetime64[ns] |
| fact_portfolio_snapshot | year | Int64 |
| fact_portfolio_snapshot | month | Int64 |
| fact_portfolio_snapshot | aum | Float64 |
| fact_portfolio_snapshot | return_ytd | Float64 |
| fact_portfolio_snapshot | benchmark_return_ytd | Float64 |
| fact_portfolio_snapshot | active_alpha_ytd | Float64 |
| fact_portfolio_snapshot | cash_pct | Float64 |
| fact_portfolio_snapshot | account_type | string |
| fact_portfolio_snapshot | is_return_suspect | Int64 |
| fact_transactions | txn_id | Int64 |
| fact_transactions | client_id | Int64 |
| fact_transactions | advisor_id | Int64 |
| fact_transactions | security_id | Int64 |
| fact_transactions | txn_date | datetime64[ns] |
| fact_transactions | txn_type | string |
| fact_transactions | shares | Float64 |
| fact_transactions | price | Float64 |
| fact_transactions | amount | Float64 |
| fact_transactions | is_post_departure_txn | Int64 |

## Relationships

| From | To | Active |
|---|---|---|
| fact_transactions[advisor_id] | dim_advisor[advisor_id] | True |
| fact_portfolio_snapshot[advisor_id] | dim_advisor[advisor_id] | True |
| fact_fees[advisor_id] | dim_advisor[advisor_id] | True |
| fact_portfolio_snapshot[benchmark_id] | dim_benchmark[benchmark_id] | True |
| fact_transactions[client_id] | dim_client[client_id] | True |
| fact_portfolio_snapshot[client_id] | dim_client[client_id] | True |
| fact_fees[client_id] | dim_client[client_id] | True |
| fact_transactions[security_id] | dim_security[security_id] | True |
| dim_security[benchmark_id] | dim_benchmark[benchmark_id] | True |
| fact_fees[fee_date] | dim_date[date] | True |
| fact_portfolio_snapshot[snapshot_date] | dim_date[date] | True |
| fact_transactions[txn_date] | dim_date[date] | True |
