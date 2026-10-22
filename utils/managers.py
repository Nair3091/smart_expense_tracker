import os
import tempfile
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

COLUMNS = ["id", "date", "category", "amount", "payment_method", "merchant", "note"]
CATEGORIES = [
    "Food", "Rent", "Transport", "Utilities",
    "Entertainment", "Health", "Education", "Shopping",
]
PAYMENT_METHODS = ["UPI", "Cash", "Card"]
TEXT_COLUMNS = ["category", "payment_method", "merchant", "note"]

# Path is built relative to this file, so the app works after a fresh install.
DEFAULT_PATH = Path(__file__).resolve().parent.parent / "data" / "expenses.csv"


def format_rs(value):
    """Format a number as Rs. 1,234.50 (missing values become Rs. 0.00)."""
    try:
        if value is None or pd.isna(value):
            value = 0.0
        return f"Rs. {float(value):,.2f}"
    except (TypeError, ValueError):
        return "Rs. 0.00"


class CSVManager:
    """Base class: owns a protected DataFrame and handles file reading/writing."""

    def __init__(self, path=DEFAULT_PATH, columns=COLUMNS):
        self._path = Path(path)
        self._columns = list(columns)
        self._data = pd.DataFrame(columns=self._columns)
        self.warnings = []

    # Encapsulation: _data is protected and exposed read-only through a property.
    @property
    def data(self):
        return self._data.copy()

    def _empty_frame(self):
        return pd.DataFrame(columns=self._columns)

    def _clean(self, df):
        """Hook for subclasses to fix types after loading."""
        return df

    def _prepare_for_save(self, df):
        """Hook for subclasses to format values before writing."""
        return df

    def load(self):
        """Read the CSV. Handles missing file, empty file and bad content."""
        self.warnings = []
        df = self._empty_frame()
        try:
            if not self._path.exists():
                self._path.parent.mkdir(parents=True, exist_ok=True)
                self._empty_frame().to_csv(self._path, index=False)
                self.warnings.append(
                    "The data file was missing, so a new empty file with headers was created."
                )
            df = pd.read_csv(self._path)
        except pd.errors.EmptyDataError:
            self.warnings.append("The data file was empty, so it was treated as having no records.")
            df = self._empty_frame()
        except (pd.errors.ParserError, UnicodeDecodeError, OSError) as exc:
            self.warnings.append(f"The data file could not be read ({exc}). Showing no records.")
            df = self._empty_frame()
        else:
            missing = [c for c in self._columns if c not in df.columns]
            for col in missing:
                df[col] = np.nan
            if missing:
                self.warnings.append(
                    "Some expected columns were missing and were added as blank: " + ", ".join(missing)
                )
            df = df[self._columns]
        finally:
            self._data = self._clean(df)
        return self.data

    def save(self):
        tmp_path = None
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            out = self._prepare_for_save(self._data.copy())
            fd, tmp_path = tempfile.mkstemp(dir=self._path.parent, suffix=".tmp")
            os.close(fd)
            out.to_csv(tmp_path, index=False)
            os.replace(tmp_path, self._path)
            tmp_path = None
        except OSError as exc:
            return False, f"Could not save the data file: {exc}"
        else:
            return True, "Saved."
        finally:
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass


class ExpenseManager(CSVManager):

    def __init__(self, path=DEFAULT_PATH):
        super().__init__(path, COLUMNS)
        self.load()

    # ------------------------------------------------------------------ cleaning
    def _clean(self, df):
        df = df.copy()

        df["id"] = pd.to_numeric(df["id"], errors="coerce")
        bad = df["id"].isna() | df["id"].duplicated()
        if bad.any():
            self.warnings.append(
                f"{int(bad.sum())} row(s) with a missing or duplicate ID were skipped."
            )
            df = df[~bad].copy()
        df["id"] = df["id"].astype("int64")

        raw_dates = df["date"]
        df["date"] = pd.to_datetime(raw_dates, errors="coerce")
        bad_dates = int((raw_dates.notna() & df["date"].isna()).sum())
        if bad_dates:
            self.warnings.append(f"{bad_dates} date value(s) could not be read and are treated as missing.")

        raw_amount = df["amount"]
        df["amount"] = pd.to_numeric(raw_amount, errors="coerce")
        bad_amounts = int((raw_amount.notna() & df["amount"].isna()).sum())
        if bad_amounts:
            self.warnings.append(
                f"{bad_amounts} amount value(s) were not numeric and are treated as missing."
            )

        for col in TEXT_COLUMNS:
            df[col] = df[col].apply(
                lambda v: np.nan if pd.isna(v) or str(v).strip() == "" else str(v).strip()
            )
        return df.reset_index(drop=True)

    def _prepare_for_save(self, df):
        df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.strftime("%Y-%m-%d")
        return df

    # ---------------------------------------------------------------- validation
    @staticmethod
    def _text(value):
        return "" if value is None or pd.isna(value) else str(value).strip()

    def _validate(self, record):
        """Return (clean_record, None) or (None, error_message)."""
        try:
            raw_id = float(record.get("id"))
            if raw_id != int(raw_id):
                return None, "ID must be a whole number."
            rid = int(raw_id)
        except (TypeError, ValueError):
            return None, "ID must be a whole number."
        if rid <= 0:
            return None, "ID must be a positive whole number."

        date_val = pd.to_datetime(record.get("date"), errors="coerce")
        if pd.isna(date_val):
            return None, "Please provide a valid date."

        category = self._text(record.get("category"))
        if not category:
            return None, "Category is required."

        try:
            amount = float(record.get("amount"))
        except (TypeError, ValueError):
            return None, "Amount must be a number."
        if not np.isfinite(amount) or amount <= 0:
            return None, "Amount must be greater than zero."

        payment = self._text(record.get("payment_method"))
        if not payment:
            return None, "Payment method is required."

        merchant = self._text(record.get("merchant"))
        if not merchant:
            return None, "Merchant is required."

        note = self._text(record.get("note"))
        clean = {
            "id": rid,
            "date": pd.Timestamp(date_val).normalize(),
            "category": category,
            "amount": round(amount, 2),
            "payment_method": payment,
            "merchant": merchant,
            "note": note if note else np.nan,
        }
        return clean, None

    def _find(self, rid):
        try:
            rid = int(rid)
        except (TypeError, ValueError):
            return None
        matches = self._data.index[self._data["id"] == rid]
        return matches[0] if len(matches) else None

    # ---------------------------------------------------------------------- CRUD
    def next_id(self):
        if self._data.empty:
            return 1001
        return int(self._data["id"].max()) + 1

    def get(self, rid):
        idx = self._find(rid)
        return None if idx is None else self._data.loc[idx].copy()

    def create(self, record):
        clean, error = self._validate(record)
        if error:
            return False, error
        if self._find(clean["id"]) is not None:
            return False, f"ID {clean['id']} already exists. Please choose a different ID."

        backup = self._data.copy()
        new_row = pd.DataFrame([clean], columns=COLUMNS)
        if self._data.empty:
            self._data = self._clean(new_row)
        else:
            self._data = self._clean(pd.concat([self._data, new_row], ignore_index=True))
        ok, message = self.save()
        if not ok:
            self._data = backup
            return False, message
        return True, f"Expense {clean['id']} was added."

    def read(self, date_range=None, categories=None, payment_methods=None,
             merchant_query="", nan_mode="exclude"):
        """Return a filtered copy of the data. Does not change the stored data."""
        df = self._data.copy()

        if date_range is not None:
            start, end = pd.Timestamp(date_range[0]), pd.Timestamp(date_range[1])
            df = df[(df["date"] >= start) & (df["date"] <= end)]
        if categories:
            df = df[df["category"].isin(categories)]
        if payment_methods:
            df = df[df["payment_method"].isin(payment_methods)]
        if merchant_query and merchant_query.strip():
            mask = df["merchant"].fillna("").str.contains(merchant_query.strip(), case=False, regex=False)
            df = df[mask]

        df = df.copy()
        if nan_mode == "fill":
            medians = self._data.groupby("category")["amount"].median()
            overall = self._data["amount"].median()
            overall = 0.0 if pd.isna(overall) else float(overall)
            df["amount"] = df["amount"].fillna(df["category"].map(medians)).fillna(overall)
        else:
            df = df[df["amount"].notna()]
        return df.reset_index(drop=True)

    def update(self, rid, fields):
        idx = self._find(rid)
        if idx is None:
            return False, f"No expense found with ID {rid}."
        current = self._data.loc[idx].to_dict()
        merged = {**current, **fields, "id": current["id"]}
        clean, error = self._validate(merged)
        if error:
            return False, error

        backup = self._data.copy()
        for col in COLUMNS:
            self._data.at[idx, col] = clean[col]
        self._data = self._clean(self._data)
        ok, message = self.save()
        if not ok:
            self._data = backup
            return False, message
        return True, f"Expense {clean['id']} was updated."

    def delete(self, rid):
        idx = self._find(rid)
        if idx is None:
            return False, f"No expense found with ID {rid}."
        backup = self._data.copy()
        self._data = self._data.drop(index=idx).reset_index(drop=True)
        ok, message = self.save()
        if not ok:
            self._data = backup
            return False, message
        return True, f"Expense {int(rid)} was deleted."

    # ------------------------------------------------------------------ analysis
    def summary(self, df=None):
        if df is None:
            df = self._data
        amounts = df["amount"].dropna().to_numpy(dtype=float)
        total = float(np.sum(amounts)) if amounts.size else 0.0
        average = float(np.mean(amounts)) if amounts.size else 0.0
        median = float(np.median(amounts)) if amounts.size else 0.0
        maximum = float(np.max(amounts)) if amounts.size else 0.0

        if df.empty:
            by_cat = pd.DataFrame(columns=["category", "Transactions", "Total", "Average", "Share (%)"])
        else:
            by_cat = (
                df.groupby("category")
                .agg(Transactions=("id", "count"), Total=("amount", "sum"), Average=("amount", "mean"))
                .sort_values("Total", ascending=False)
                .reset_index()
            )
            by_cat["Share (%)"] = np.where(total > 0, by_cat["Total"] / total * 100, 0.0)
            cols = ["Total", "Average", "Share (%)"]
            by_cat[cols] = by_cat[cols].round(2)

        top_category = by_cat.iloc[0]["category"] if (not by_cat.empty and total > 0) else "N/A"

        merchants = df.groupby("merchant")["amount"].sum() if not df.empty else pd.Series(dtype=float)
        top_merchant = merchants.idxmax() if (not merchants.empty and total > 0) else "N/A"

        dated = df.dropna(subset=["date", "amount"])
        if dated.empty:
            monthly = pd.DataFrame(columns=["month", "amount"])
        else:
            monthly = (
                dated.assign(month=dated["date"].dt.to_period("M").astype(str))
                .groupby("month", as_index=False)["amount"].sum()
            )

        mom_change = None
        if len(monthly) >= 2:
            last, prev = float(monthly["amount"].iloc[-1]), float(monthly["amount"].iloc[-2])
            if prev != 0:
                mom_change = (last - prev) / prev * 100

        return {
            "total": total,
            "average": average,
            "median": median,
            "maximum": maximum,
            "count": int(len(df)),
            "top_category": top_category,
            "top_merchant": top_merchant,
            "mom_change": mom_change,
            "by_category": by_cat,
            "monthly": monthly,
        }

    # -------------------------------------------------------------------- report
    def report(self, df, filters, stats=None):
        """Build a plain-text report."""
        stats = stats or self.summary(df)
        line = "-" * 44
        mom = "Not enough data" if stats["mom_change"] is None else f"{stats['mom_change']:+.2f}%"
        lines = [
            "SMART EXPENSE TRACKER - REPORT",
            "=" * 44,
            f"Generated at   : {datetime.now():%Y-%m-%d %H:%M:%S}",
            f"Rows in report : {len(df)}",
            "",
            "APPLIED FILTERS",
            line,
        ]
        for key, value in filters.items():
            lines.append(f"{key}: {value}")
        lines += [
            "",
            "SUMMARY STATISTICS",
            line,
            f"Total spend             : {format_rs(stats['total'])}",
            f"Average per transaction : {format_rs(stats['average'])}",
            f"Median transaction      : {format_rs(stats['median'])}",
            f"Largest transaction     : {format_rs(stats['maximum'])}",
            f"Transaction count       : {stats['count']}",
            f"Top category            : {stats['top_category']}",
            f"Top merchant            : {stats['top_merchant']}",
            f"Month-over-month change : {mom} (latest two months in the filtered data)",
            "",
            "SPEND BY CATEGORY",
            line,
        ]
        if stats["by_category"].empty:
            lines.append("No data for the selected filters.")
        else:
            lines.append(stats["by_category"].to_string(index=False))
        return "\n".join(lines)