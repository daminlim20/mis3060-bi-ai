HW Part 1

Business Context Exploration-
1. The exact prompt you sent: "Great can you use that csv file as reference to answer the following question "Wildcat's loan status field treats Delinquent and Default as parallel categories, but in lending these are usually sequential.  Delinquency is a borrower falling behind on payments, while default is a lender's declaration that the loan has failed and triggers different consequences (collections, charge-off, credit reporting). What is Wildcat's actual definition of each status ?  Is there a specific days-past-due threshold where a loan moves from Delinquent to Default"
2. A summary of Claude's response: The "wildcat__loans_clean.csv" file does not define delinquent or default loans, it is simply a flat label. There are no fields indicating the days past the payment date or payment history to help define the loan status. Despite there being four status categories of current, paid off, delinquent , and default, the dataset treats the two (delinquent and default) as parallel categories with no way to verify whether or where a sequential cut off for when defaults applies.
3. One follow-up question the response raised for you: Because the data does not identify when or why a loan's status changed, how would we know if a default loan went through a delinquent phase first?

