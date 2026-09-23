# EDA Script Specification

Please create one single Python script that performs the complete exploratory data analysis workflow described below. The script should run from start to finish in one execution. Do not split the work into separate scripts or separate files.

Use `data/raw/fact_transactions.csv` as the input dataset.

Please make sure the script does all of the following:

1. Load `data/raw/fact_transactions.csv` into a pandas DataFrame.

2. Print the shape of the dataset in rows × columns format.

3. Print every column name along with its data type.

4. Print the number of missing values in every column.

5. Print descriptive statistics for all numeric columns. The output should include count, mean, standard deviation, minimum, 25th percentile, median, 75th percentile, and maximum.

6. For the `txn_type` column, print both the value counts and the percentage of total rows represented by each value. Sort the results from most frequent to least frequent.

7. Print the number of unique clients, advisors, and securities referenced in the dataset. Use the appropriate columns in the file for each of these entities.

8. Print the earliest and latest values in `txn_date` so the dataset's date range is clearly shown.

9. Check for duplicate records based on `txn_id` and print the number of duplicates found.

10. For the `amount` column, print the mean, median, and skewness.

11. Group the data by `txn_type` and, for each transaction type, print the row count, mean `amount`, and median `amount`. Round the mean and median amounts to two decimal places, and sort the result by mean amount from highest to lowest.

12. Compute the correlation matrix for `shares`, `price`, and `amount`. Round the matrix values to two decimal places and print the matrix. Also identify and print the three strongest correlations between different variables, excluding each variable's correlation with itself. Do not count the same variable pair twice.

13. For the `shares` column, print the minimum value, maximum value, and number of negative values for each `txn_type`.

14. Verify the dataset shape against the expected shape of `(298772, 9)`. If the actual shape is different, print a clear warning message.

15. Create the following three charts and save them in the `hw02/charts/` folder:
   - A histogram of `amount` with clearly labeled vertical lines showing the mean and median. Save it as `hw02/charts/hist_amount.png`.
   - A horizontal box plot of `amount` grouped by `txn_type`. Save it as `hw02/charts/box_amount_by_type.png`.
   - A scatter plot with `shares` on the x-axis and `amount` on the y-axis, with points colored by `txn_type`. Save it as `hw02/charts/scatter_shares_amount.png`.

16. Save a plain-text summary containing the outputs from requirements 2 through 13 to `hw02/hw02_profile.txt`. The information written to this file should match the analysis results printed by the script for those requirements.

17. Add a comment block at the top of the Python script that identifies:
   - the script,
   - the dataset,
   - the author (Damin Lim),
   - and the generation date.

A few implementation expectations to keep in mind:

- This must be one Python script, not seventeen separate scripts.
- All seventeen requirements must execute together when that one script is run.
- The script should create `hw02/charts/` if the folder does not already exist.
- Keep the console output organized and readable so each section of the analysis is easy to identify.
- Make sure the saved charts have clear titles and axis labels where appropriate.
- Do not omit any requirement listed above.
