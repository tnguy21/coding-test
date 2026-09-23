# Duration

```text
Started: 2026-09-23 11:18 UTC+1
Stopped: 2026-09-23 13:24 UTC+1
```

# Design decisions

## Implemented features
I have implemented step 1, 2 and 6 under the *what we would like* steps, thus giving a PoC that can be used to demo the behavior of a basic systems. This contains the essentials:
1) A backend that has a REST API used to access information gathered from the CSVs
2) A simple frontend that provides a quick overview of all the portfolios, with functionality to get everything that a non-technical (No manual API calls) person would want

### Frontend
Provides the most essential features i.e. searching for a specific portfolio, getting statistics across all portfolios sorted by be `loss-ratio`. This performance metric can chosen, because it encapsulates a better picture of a portfolio - So it is not just sorted by how big the portfolio is

Incase the user does not know all existing portfolios, there is a button that displays all available portfoliosd


### Backend 
Implementes the 2 essential API endspoints, used to retrieve individual things about an portfolio and all the statistics. Incase a portfolio does not exist, I decided to give an error that simply states that the portfolio with the provided ID does not exist. This makes it easy to understand that it either does not exist *yet*, or there must have been a typo.


### Data cleaning
Because there are different time formats in the CSV files, some in YYYY-MM-DD and others in DD-MM-YYYY into the format 

Also in some states, there are whitespace, so these whitespaces are simply stripped.

Some prices are in EUR and others in DKK, where I chose to convert them to DKK based on the fx_rates for the month that this happened

## Non-implemented features
Under the time limit of the project, I spent most time trying to look at the csv files, gather ideas and having the architecture in place, before writing any code - This included planning with CLAUDE.

### Database and sorting through data
These are steps 4, 5 and 8, which were omitted due to these typically being part of "just 1 step" i.e. implementing database interaction. Adding a database can easily make it possible to query/sort data dumped from the provided CSV files onto the database.

Due to the time crunch, the database interaction was not implemented, however it should be fast to implement it, given that the CSV files are already structures. 