"""Landing page for the Smart Expense Tracker."""

import streamlit as st

from utils.managers import ExpenseManager, format_rs

st.set_page_config(page_title="Smart Expense Tracker", layout="wide")

st.title("Smart Expense Tracker")
st.write(
    "A web application for recording, managing, analyzing and visualizing personal expenses. "
    "All data is stored in a single CSV file, and the app follows one core loop: "
    "input data, update the CSV, read and analyze it, then visualize the result."
)

manager = ExpenseManager()
for warning in manager.warnings:
    st.warning(warning)

df = manager.read(nan_mode="exclude")
stats = manager.summary(df)

st.subheader("At a glance")
c1, c2, c3 = st.columns(3)
c1.metric("Total spend", format_rs(stats["total"]))
c2.metric("Transactions", f"{stats['count']:,}")
c3.metric("Top category", stats["top_category"])
st.caption("Totals exclude records with a missing amount.")

st.subheader("Sustainable Development Goals")
st.markdown(
    """
**SDG 1 - No Poverty (primary).** Tracking spending, staying within budgets and building
financial awareness are basic steps toward financial security.

**SDG 8 - Decent Work and Economic Growth.** Financial literacy and responsible money
management support long-term economic well-being.
"""
)

st.subheader("How to use this app")
st.markdown(
    """
Open the **Expenses** page (sidebar or the link below). It contains six tabs:

1. **View** - sortable table with a group-by summary per category.
2. **Add** - record a new expense with validation and duplicate-ID checks.
3. **Edit** - update an existing expense by ID.
4. **Delete** - remove an expense after confirming.
5. **Charts** - bar, line, pie and histogram charts based on your filters.
6. **Report** - download a text report with timestamp, row count, filters and statistics.

Use the sidebar filters on the Expenses page to narrow down the data. They apply to every tab.
"""
)
st.page_link("pages/Expenses.py", label="Open the Expenses page")