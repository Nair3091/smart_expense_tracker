"""Expenses page: full CRUD, analysis, charts and report."""

import sys
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd
import plotly.express as px
import streamlit as st

from utils.managers import CATEGORIES, COLUMNS, PAYMENT_METHODS, ExpenseManager, format_rs

st.set_page_config(page_title="Expenses - Smart Expense Tracker", layout="wide")
st.title("Expenses")

NAN_OPTIONS = {
    "Exclude rows with missing amount": "exclude",
    "Fill missing amount with category median": "fill",
}
NAN_MESSAGES = {
    "exclude": "Rows with a missing amount are excluded from totals, tables and charts.",
    "fill": "Missing amounts are filled with the median amount of the same category.",
}


def options_with(current, base):
    options = list(base)
    if isinstance(current, str) and current and current not in options:
        options.append(current)
    return options


def index_of(current, options):
    return options.index(current) if isinstance(current, str) and current in options else 0


def text_or_blank(value):
    return "" if value is None or pd.isna(value) else str(value)


def flash_and_rerun(message):
    st.session_state["flash"] = message
    st.rerun()


manager = ExpenseManager()
all_data = manager.data

flash = st.session_state.pop("flash", None)
if flash:
    st.success(flash)
for warning in manager.warnings:
    st.warning(warning)

# ------------------------------------------------------------------- sidebar
st.sidebar.header("Filters")

valid_dates = all_data["date"].dropna()
if valid_dates.empty:
    min_d = max_d = date.today()
else:
    min_d, max_d = valid_dates.min().date(), valid_dates.max().date()

date_sel = st.sidebar.date_input("Date range", value=(min_d, max_d))
if isinstance(date_sel, (tuple, list)):
    if len(date_sel) == 2:
        start, end = date_sel
    elif len(date_sel) == 1:
        start = end = date_sel[0]
    else:
        start, end = min_d, max_d
else:
    start = end = date_sel

category_options = sorted(set(CATEGORIES) | set(all_data["category"].dropna()))
sel_categories = st.sidebar.multiselect("Category (empty = all)", category_options)

payment_options = sorted(set(PAYMENT_METHODS) | set(all_data["payment_method"].dropna()))
sel_payments = st.sidebar.multiselect("Payment method (empty = all)", payment_options)

merchant_query = st.sidebar.text_input("Merchant search")

nan_label = st.sidebar.radio("Missing amount handling", list(NAN_OPTIONS.keys()))
nan_mode = NAN_OPTIONS[nan_label]
st.sidebar.info(NAN_MESSAGES[nan_mode])

df = manager.read(
    date_range=(start, end),
    categories=sel_categories,
    payment_methods=sel_payments,
    merchant_query=merchant_query,
    nan_mode=nan_mode,
)
stats = manager.summary(df)

filters_used = {
    "Date range": f"{start:%Y-%m-%d} to {end:%Y-%m-%d}",
    "Categories": ", ".join(sel_categories) if sel_categories else "All",
    "Payment methods": ", ".join(sel_payments) if sel_payments else "All",
    "Merchant search": merchant_query.strip() or "None",
    "Missing data handling": NAN_MESSAGES[nan_mode],
}

# --------------------------------------------------------------- top metrics
m1, m2, m3, m4 = st.columns(4)
m1.metric("Total spend", format_rs(stats["total"]))
m2.metric("Average per transaction", format_rs(stats["average"]))
m3.metric("Transactions", f"{stats['count']:,}")
m4.metric("Top category", stats["top_category"])
st.caption(NAN_MESSAGES[nan_mode])

tab_view, tab_add, tab_edit, tab_delete, tab_charts, tab_report = st.tabs(
    ["View", "Add", "Edit", "Delete", "Charts", "Report"]
)

# ---------------------------------------------------------------------- VIEW
with tab_view:
    st.subheader("Transactions")
    if df.empty:
        st.info("No records match the current filters.")
    else:
        c1, c2 = st.columns([2, 1])
        sort_col = c1.selectbox("Sort by", COLUMNS, index=COLUMNS.index("date"))
        order = c2.radio("Order", ["Ascending", "Descending"], index=1, horizontal=True)
        view = df.sort_values(sort_col, ascending=(order == "Ascending"), na_position="last").copy()
        view["date"] = view["date"].dt.strftime("%Y-%m-%d")
        st.dataframe(view, hide_index=True)

        st.subheader("Summary by category")
        st.dataframe(stats["by_category"], hide_index=True)

        s1, s2, s3 = st.columns(3)
        s1.metric("Top merchant", stats["top_merchant"])
        s2.metric("Largest transaction", format_rs(stats["maximum"]))
        if stats["mom_change"] is None:
            s3.metric("Month-over-month change", "Not enough data")
        else:
            s3.metric("Month-over-month change", f"{stats['mom_change']:+.2f}%")

# ----------------------------------------------------------------------- ADD
with tab_add:
    st.subheader("Add a new expense")
    nonce = st.session_state.get("add_nonce", 0)
    with st.form(f"add_form_{nonce}"):
        a1, a2 = st.columns(2)
        new_id = a1.number_input("ID", min_value=1, value=manager.next_id(), step=1)
        new_date = a2.date_input("Date", value=date.today())
        new_category = a1.selectbox("Category", CATEGORIES)
        new_amount = a2.number_input("Amount (Rs.)", min_value=0.0, value=0.0, step=10.0, format="%.2f")
        new_payment = a1.selectbox("Payment method", PAYMENT_METHODS)
        new_merchant = a2.text_input("Merchant")
        new_note = st.text_input("Note (optional)")
        add_clicked = st.form_submit_button("Add expense")

    if add_clicked:
        ok, message = manager.create({
            "id": new_id, "date": new_date, "category": new_category, "amount": new_amount,
            "payment_method": new_payment, "merchant": new_merchant, "note": new_note,
        })
        if ok:
            st.session_state["add_nonce"] = nonce + 1
            flash_and_rerun(message)
        else:
            st.error(message)

# ---------------------------------------------------------------------- EDIT
default_id = int(all_data["id"].max()) if not all_data.empty else 1

with tab_edit:
    st.subheader("Edit an expense")
    edit_id = st.number_input("Expense ID to edit", min_value=1, value=default_id, step=1, key="edit_id")
    record = manager.get(edit_id)
    if record is None:
        st.error(f"No expense found with ID {edit_id}. Please check the ID and try again.")
    else:
        cat_opts = options_with(record["category"], CATEGORIES)
        pay_opts = options_with(record["payment_method"], PAYMENT_METHODS)
        current_date = record["date"].date() if pd.notna(record["date"]) else date.today()
        current_amount = float(record["amount"]) if pd.notna(record["amount"]) else 0.0
        if pd.isna(record["amount"]):
            st.caption("The amount for this record is currently missing. Enter a value to fix it.")

        with st.form(f"edit_form_{edit_id}"):
            e1, e2 = st.columns(2)
            e_date = e1.date_input("Date", value=current_date)
            e_category = e2.selectbox("Category", cat_opts, index=index_of(record["category"], cat_opts))
            e_amount = e1.number_input("Amount (Rs.)", min_value=0.0, value=current_amount,
                                       step=10.0, format="%.2f")
            e_payment = e2.selectbox("Payment method", pay_opts,
                                     index=index_of(record["payment_method"], pay_opts))
            e_merchant = e1.text_input("Merchant", value=text_or_blank(record["merchant"]))
            e_note = e2.text_input("Note (optional)", value=text_or_blank(record["note"]))
            save_clicked = st.form_submit_button("Save changes")

        if save_clicked:
            ok, message = manager.update(edit_id, {
                "date": e_date, "category": e_category, "amount": e_amount,
                "payment_method": e_payment, "merchant": e_merchant, "note": e_note,
            })
            if ok:
                flash_and_rerun(message)
            else:
                st.error(message)

# -------------------------------------------------------------------- DELETE
with tab_delete:
    st.subheader("Delete an expense")
    del_id = st.number_input("Expense ID to delete", min_value=1, value=default_id, step=1, key="del_id")
    record = manager.get(del_id)
    if record is None:
        st.error(f"No expense found with ID {del_id}. Please check the ID and try again.")
    else:
        st.warning("You are about to permanently delete this record:")
        preview = pd.DataFrame([{
            "id": str(int(record["id"])),
            "date": record["date"].strftime("%Y-%m-%d") if pd.notna(record["date"]) else "",
            "category": text_or_blank(record["category"]),
            "amount": "" if pd.isna(record["amount"]) else f"{float(record['amount']):.2f}",
            "payment_method": text_or_blank(record["payment_method"]),
            "merchant": text_or_blank(record["merchant"]),
            "note": text_or_blank(record["note"]),
        }])
        st.dataframe(preview, hide_index=True)
        confirm = st.checkbox("Yes, delete", key=f"del_confirm_{del_id}")
        if st.button("Delete record", disabled=not confirm):
            ok, message = manager.delete(del_id)
            if ok:
                flash_and_rerun(message)
            else:
                st.error(message)

# -------------------------------------------------------------------- CHARTS
with tab_charts:
    st.subheader("Charts")
    st.caption("Charts are rebuilt from the currently filtered data.")
    if df.empty:
        st.info("No data to chart for the current filters.")
    else:
        row1 = st.columns(2)
        by_cat = stats["by_category"]
        fig_bar = px.bar(by_cat, x="category", y="Total", title="Spend by category",
                         labels={"category": "Category", "Total": "Total spend (Rs.)"})
        row1[0].plotly_chart(fig_bar)

        monthly = stats["monthly"]
        if monthly.empty:
            row1[1].info("No dated records for a monthly trend.")
        else:
            fig_line = px.line(monthly, x="month", y="amount", markers=True, title="Monthly spending trend",
                               labels={"month": "Month", "amount": "Total spend (Rs.)"})
            row1[1].plotly_chart(fig_line)

        row2 = st.columns(2)
        by_pay = df.groupby("payment_method", as_index=False)["amount"].sum()
        fig_pie = px.pie(by_pay, names="payment_method", values="amount", title="Spend by payment method")
        row2[0].plotly_chart(fig_pie)

        fig_hist = px.histogram(df.dropna(subset=["amount"]), x="amount", nbins=30,
                                title="Distribution of transaction amounts",
                                labels={"amount": "Amount (Rs.)"})
        row2[1].plotly_chart(fig_hist)

# -------------------------------------------------------------------- REPORT
with tab_report:
    st.subheader("Report")
    report_text = manager.report(df, filters_used, stats)
    st.code(report_text, language="text")
    st.download_button(
        "Download report (.txt)",
        data=report_text,
        file_name=f"expense_report_{datetime.now():%Y%m%d_%H%M%S}.txt",
        mime="text/plain",
    )