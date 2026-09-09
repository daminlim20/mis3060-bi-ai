Prompt Engineering 

Question; What are the most important metrics for measuring credit risk in a consumer loan portfolio?

Zero Shot:
The complete prompt you sent (copy it exactly)
The first 150 words of Claude's response:
"Based on the wildcat_loans_clean.csv file (2,340 loans, ~$160M in outstanding balances), a few metrics stand out as the most important for gauging credit risk in this portfolio, and the data itself shows why. Credit score is the single strongest signal here. Loans in the "Poor" band (below 580) default at 17.8% and go delinquent at another 22.5% — meaning roughly 4 in 10 of those loans are troubled. That falls off sharply as scores rise: the "Good" band (670–739) defaults at only 2.2%, and the portfolio's weighted-average credit score is 677. Score is also driving pricing — credit score and interest rate have a -0.84 correlation, so the lender is clearly using risk-based pricing (average rate on defaulted loans is 14.2% vs. 11.4% on current loans). Default rate and delinquency rate are the two headline portfolio-health numbers, and it's worth tracking them separately rather than combined: this portfolio's default rate..."

Your evaluation: what did this strategy do well? What was missing or generic?
I think that despite Claude not having a more defined context in which I was asking this question, it did well in pulling numbers from the file to back its answers. and reasoning behind it. I don't particularly see the answer missing any details as at the conclusion it actually gives me a ranked list of which data is most helpful in measuring credit risk. "So the ranked list from this data would be: credit score (strongest predictor and pricing driver), delinquency rate as a leading indicator, default/charge-off rate as the lagging outcome measure, and exposure concentration (by loan purpose and geography) as the portfolio-level risk to watch — with DTI flagged as a metric that isn't adding much predictive value in this particular dataset."

Role Assigned:
The complete prompt you sent: Using the attached csv file in the directory, Imagine you are a senior portfolio manager what are the most important metrics for measuring credit risk in a consumer loan portfolio?

The first 150 words of Claude's response:
"Looking at your Wildcat loan portfolio file (2,340 loans, $160M in outstanding balance, spanning 2015–2025 originations), here's how I'd think about this as a portfolio manager, with your own numbers as the illustration.

Default and delinquency rates, split by count and by dollar exposure. These are the headline numbers, but they need to be read two ways because they rarely agree. In your book, 4.5% of loans (106) are in Default and another 10.6% (248) are Delinquent — a 15.1% combined "at-risk" rate by count. On a dollar basis that drops to 13.3%, because the bad loans skew slightly smaller than average. A PM watches both: if the dollar rate runs meaningfully above the count rate, your larger loans are the ones going bad, which is a concentration problem, not just..."

Your evaluation: what did this strategy do well? What was missing or generic?
This strategy definitely gave a similar response to the xero shot, but tailored the answer to the view of a PM explaining exactly what a PM would look for and explained in detail why. The answers were also structured differently, split into almost like a check list of what a PM would compare different default rate, debt-to-income ratios and concentration risk.


Few Shot:
The complete prompt you sent (copy it exactly): "Using the csv file attached in the file directory answer the following question is a concise bulleted point list,  what are the most important metrics for measuring credit risk in a consumer loan portfolio?"
The first 150 words of Claude's response:
Based on the fields in wildcat_loans_clean.csv (credit_score, debt_to_income_ratio, loan_status, interest_rate, loan_amount, annual_income, origination_date, loan_purpose, state), here are the metrics that matter most for assessing credit risk in a consumer loan portfolio:

Default rate – the share of loans in "Default" status (106/2,341 ≈ 4.5% here); the core measure of realized credit losses.
Delinquency rate – loans past due but not yet charged off ("Delinquent" status, 248/2,341 ≈ 10.6% here); an early warning signal that often precedes default.
Weighted average credit score (WAC) – the portfolio's exposure-weighted credit_score; lower average scores signal higher aggregate risk, and tracking the distribution (not just the mean) shows how much exposure sits in subprime tiers.
Debt-to-income (DTI) ratio – average and distribution of debt_to_income_ratio; high DTI borrowers have less cushion to absorb payment shocks.
Your evaluation: what did this strategy do well? What was missing or generic?
Something it did well it actually used the real data instead of just theory — pulled real column names and even ran the numbers (4.5% default rate, 10.6% delinquency) instead of guessing. It also called out that LTV isn't in this dataset, so it wasn't just dumping a generic list but it did not specify or ask who the list was for.

Conclusion section (required): Write 3–5 sentences comparing the three strategies. Which produced the most useful output for a BI analyst, and why?

I can definitely see the distinction in responses for each strategy. Out of the three responses, I think that the second response where I assigned the role was the most accurate and helpful as the response was tailored to the actual role. However, it is important that you give Claude better context to what you are looking for so that it knows what information to look for. 
