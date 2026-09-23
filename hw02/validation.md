# HW2 Validation — fact_transactions EDA

**Author:** Damin Lim

---

## 2A — Known-Answer Benchmarks

| Check | Expected | Your Script Produced | Match? | Notes |
|---|---|---|---|---|
| Dataset shape | (298772, 9) | (298772, 9) | Yes | |
| Null count — `security_id` | 101,597 | 101,597 | Yes | |
| Null count — `amount` | 0 | 0 | Yes | |
| Unique `txn_type` values | 6 | 6 | Yes | |
| Count of `Buy` transactions | 83,556 | 83,556 | Yes | |
| `txn_date` data type | object | str | No | pandas 3.0.5 (installed in this virtual environment) changed the default dtype for text columns from the classic NumPy `object` dtype to a dedicated `str` dtype. The column is still plain text, not a real date type, so the underlying finding the benchmark is checking for is unchanged. |
| Earliest `txn_date` | 2020-01-01 | 2020-01-01 | Yes | |
| Latest `txn_date` | 2024-12-30 | 2024-12-30 | Yes | |
| Duplicate `txn_id` count | 0 | 0 | Yes | |
| Mean `amount` | $54,075.17 | $54,075.17 | Yes | |
| Median `amount` | $41,220.48 | $41,220.49 | No | The exact underlying numbers is 41220.485000000000582... it correctly rounds up to .49. A 1-cent rounding, not a calculation error. |
| Skewness of `amount` | 1.15 | 1.15 | Yes | |
| Correlation `shares`-`amount` | 0.65 | 0.65 | Yes | |
| Correlation `price`-`amount` | 0.64 | 0.64 | Yes | |
| Correlation `shares`-`price` | 0.00 | 0.00 | Yes | |
| Negative `shares` count (Buy only) | 836 | 836 (all Buy) | Yes | |
| Profile file created | Yes | Yes | Yes | |
| Chart files created (3) | Yes | Yes | Yes | |

**Discrepancy investigation (Claude Cowork conversation):**

Both mismatches above were investigated in this same Claude Cowork session that generated the script (not a separate session -- that requirement applies to Part 2B, not 2A). Summary of the investigation:

- *txn_date dtype:* Asked Claude Cowork why `txn_date` printed as `str` instead of `object`. Claude identified that pandas 3.0 (the version installed via `requirements.txt` in this environment) made string-column type inference default to a dedicated `str` dtype instead of the legacy NumPy `object` dtype, and confirmed this with a small reproducible test. Conclusion: environment/library-version difference, not a data or script error.
- *Median amount off by $0.01:* Asked Claude Cowork to check the exact floating-point value behind the median. It computed the median directly and found it equals 41220.485000000000582... (not exactly 41220.485), so standard rounding correctly produces $41,220.49. Conclusion: floating-point representation artifact, not a data or script error.

---

## 2B — Explain the Code and Output

*(To be completed in a NEW Claude Cowork session — not this one.)*

1. Did Claude's predicted outputs (from Prompt 1) match what you actually saw in the terminal? List any discrepancies.
 I was impressed with how cautious Claude was with giving me answers for the sake of giving me answers. It told me that it did not have all the required information it needed to give me the accurate numbers, but gave me a run-down of generally what the output would look like and after comparing the actual terminal output, I found that it was accurate based on the little information that it did have. I did not find any discrepancies. 

2. What did Claude flag as potentially unexpected or worth investigating (from Prompt 2)? 
- It flagged things in order of priority, the first flag being "836 Buy rows have negative shares," second being "Check that amount really equals shares × price," "Dividend amounts are too large," and lastly "Advisory fees are very skewed."

3. Did Claude mention the 101,597 null values in `security_id`? What explanation did it give?
- Yes, it said the following: "Missing values follow the transaction type. The 101,597 nulls in security_id, shares and price add up exactly to Deposit + Advisory Fee + Withdrawal (35,981 + 35,766 + 29,850). Section 13 confirms it: those three types show NaN for shares. Cash movements don't involve a security, so these nulls are expected, not a data problem."

4. Did Claude flag the `txn_date` column as a concern? Why would that matter for a time-series analysis?
- It did not flag it as a significant concern as the format the dates were in was correctly identified/defined in the file. However, it would become an issue if any time based analysis was done such as a time series analyis as it is currently saved as text not date type. As text, txn date column can't be resampled, used for rolling averages, subtracted or split into weekday and quarter.

5. Open your three chart files. Does what you see in each image match Claude's explanation of that section of the output? Note any differences.
- Yes, they all matched what Claude expected the image charts to show. 

6. Paste one follow-up question you asked Claude, and Claude's answer.

- Question: All 836 negative-share rows are Buy transactions, with values as low as -499.63. If this were a real Wildcat Capital dataset, what steps would you take to figure out whether these are data input errors or genuine data entries before deciding how to treat them in an analysis?

- Answer: 

Explanations to test: 

A sign typo (someone entered a minus sign by mistake)
A Sell coded as a Buy
A reversal of an earlier buy
A system or data-load bug
A defined business meaning, such as a transfer out or a corporate action

Checks in the data:

Rate: 836 ÷ 83,556 = exactly 1.00% of buys. That's suspiciously round and suggests planted errors.
Amount: check whether amount = |shares| × price. If yes, only the sign is wrong, which points to a typo.
Size: compare |shares| on the negative rows with normal buys. If the distributions match, it's a flipped sign.
Concentration: group by month, advisor, client and security. Evenly spread suggests random errors. Clustered suggests a system or process issue.
Reversals: look for an earlier Buy with the same client, security and share count. Matches would mean real cancellations.
Positions: add up shares over time. If the negative rows push a holding below zero, they aren't real buys. If flipping the sign gives clean holdings, it's a sign error.

Checks outside the data (real firm only):

The data dictionary: is a negative quantity a defined convention?
Match a sample of 20–30 rows against broker or custodian trade confirmations. This is the most reliable check.
Ask operations and the advisors involved how they enter corrections.
Review data-load (ETL) logs for when these rows came in.
Report the issue to the data owner so it gets fixed at the source.

Decide and document:

If it's a sign error: flip the sign and flag the row.
If it's a reversal: net it against the original buy, or exclude both.
If it's a mislabeled sell: change the type to Sell and flag the row.
If it's unclear: exclude the rows and run key results with and without them.
Always keep the raw data unchanged, and write down the rule you applied.


## 2C — Business Check & Cross-Validation

**Business-reasonableness questions** (answer in your own words):

1. `security_id`, `shares`, and `price` are all null in exactly 101,597 rows. Looking at the `txn_type` value counts, which three transaction types would you expect to have no security -- and why? Do the counts add up to 101,597?

2. There are 83,556 Buy transactions and 59,755 Sell transactions. What does it mean for a wealth management firm to have significantly more Buys than Sells over a five-year period?

3. The `txn_date` column is stored as a string rather than a date. If Claude Coword generated code to compute the average number of days between transactions, what would go wrong if the dates remained as strings?

4. Wildcat Capital has 2,700 clients served by 25 advisors. Is that ratio -- roughly 108 clients per advisor -- plausible for a registered investment advisory firm?

5. 836 `Buy` transactions have negative `shares` values (as low as -499.63), while every other transaction type in the dataset has only positive share values. What are two plausible business explanations for a negative share count on a Buy transaction, and what would you do next to determine which explanation is more likely?

**Cross-validation:**

6. What did each script return?

7. Do the results agree? If not, which one is wrong and why?

8. Why is it useful to verify a count using subtraction rather than direct filtering?

