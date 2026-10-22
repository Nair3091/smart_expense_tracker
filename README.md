# Smart Expense Tracker

Streamlit web app for recording, managing, analyzing and visualizing personal expenses
stored in a CSV file. Course: 22AIE205 - Introduction to Python (Term Project).

## Features
- Create, read, update and delete expenses (with validation and duplicate-ID checks)
- Sidebar filters: date range, category, payment method, merchant search, missing-data handling
- Summary statistics, group-by category table, month-over-month change
- Four dynamic charts: bar, line, pie, histogram
- Downloadable text report (timestamp, row count, filters, statistics)
- Safe CSV writes (temp file, then replace) and friendly error messages

## Setup
1. Create and activate a virtual environment:
   - Windows: `python -m venv venv` then `venv\Scripts\activate`
   - macOS/Linux: `python3 -m venv venv` then `source venv/bin/activate`
2. Install dependencies: `pip install -r requirements.txt`
3. Generate the dataset: `python generate_data.py`
4. Run the app: `streamlit run Home.py`

## Project structure
- `Home.py` - landing page
- `pages/1_Expenses.py` - CRUD, analysis, charts, report
- `utils/managers.py` - CSVManager (base class) and ExpenseManager
- `generate_data.py` - creates `data/expenses.csv` (about 400 rows)
- `data/expenses.csv` - dataset

## Design notes
- `CSVManager` keeps a protected `_data` DataFrame exposed through a `@property` and
  provides `load()` and `save()`. `ExpenseManager` inherits from it and adds
  `create()`, `read()`, `update()`, `delete()` and `summary()`.
- About 4% of `amount` and `note` values are blank on purpose to demonstrate NaN handling.