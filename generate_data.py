import calendar
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

SEED = 42
OUTPUT = Path(__file__).resolve().parent / "data" / "expenses.csv"
MONTHS = [(2025, m) for m in (10, 11, 12)] + [(2026, m) for m in range(1, 10)]
PAYMENTS = ["UPI", "Cash", "Card"]
PAYMENT_PROBS = [0.6, 0.2, 0.2]

SPEC = {
    "Food": {
        "count": 170, "amount": (40, 450),
        "merchants": ["Swiggy", "Zomato", "Campus Canteen", "Cafe Coffee Day", "Dominos", "Local Bakery"],
        "notes": ["Lunch", "Team dinner", "Snacks", "Late night order", "Breakfast", "Coffee with friends"],
    },
    "Transport": {
        "count": 70, "amount": (20, 600),
        "merchants": ["Metro", "Uber", "Ola", "KSRTC", "Rapido", "IRCTC"],
        "notes": ["Commute to college", "Airport ride", "Weekend trip", "Auto fare", "Train ticket home"],
    },
    "Utilities": {
        "count": 36, "amount": (150, 1500),
        "merchants": ["KSEB", "Jio", "Airtel", "ACT Fibernet", "Water Authority"],
        "notes": ["Electricity bill", "Mobile recharge", "Wifi bill", "Water bill"],
    },
    "Entertainment": {
        "count": 35, "amount": (100, 1200),
        "merchants": ["Netflix", "BookMyShow", "Spotify", "PVR Cinemas", "Steam"],
        "notes": ["Movie night", "Subscription", "Game purchase", "Concert ticket"],
    },
    "Health": {
        "count": 15, "amount": (150, 2500),
        "merchants": ["Apollo Pharmacy", "MedPlus", "City Clinic"],
        "notes": ["Medicines", "Doctor visit", "Health checkup", "Vitamins"],
    },
    "Education": {
        "count": 20, "amount": (200, 5000),
        "merchants": ["Udemy", "Coursera", "Campus Bookstore", "Xerox Shop", "Amazon"],
        "notes": ["Textbook", "Online course", "Printing", "Exam fee", "Stationery"],
    },
    "Shopping": {
        "count": 42, "amount": (300, 6000),
        "merchants": ["Amazon", "Flipkart", "Myntra", "Decathlon", "Local Market"],
        "notes": ["Clothes", "Headphones", "Shoes", "Backpack", "Gift", "Room supplies"],
    },
}


def random_amount(rng, low, high):
    # Beta skew: many small purchases, a few large ones.
    return round(float(low + (high - low) * rng.beta(1.5, 4)), 2)


def build_rows(rng):
    rows = []

    def add(year, month, day, category, amount, payment, merchant, note):
        rows.append({
            "date": date(year, month, day), "category": category, "amount": amount,
            "payment_method": payment, "merchant": merchant, "note": note,
        })

    # Rent: one large payment per month.
    for i, (y, m) in enumerate(MONTHS):
        add(y, m, int(rng.integers(1, 4)), "Rent", 8500.0 if i < 6 else 9000.0,
            "UPI", "PG Landlord", "Monthly rent")

    for category, spec in SPEC.items():
        n = spec["count"]
        if category == "Utilities":
            month_idx = np.repeat(np.arange(12), 3)
        else:
            month_idx = rng.integers(0, 12, size=n)
        for mi in month_idx:
            y, m = MONTHS[int(mi)]
            if category == "Utilities":
                day = int(rng.integers(5, 21))
            else:
                day = int(rng.integers(1, calendar.monthrange(y, m)[1] + 1))
            low, high = spec["amount"]
            add(
                y, m, day, category, random_amount(rng, low, high),
                str(rng.choice(PAYMENTS, p=PAYMENT_PROBS)),
                str(rng.choice(spec["merchants"])), str(rng.choice(spec["notes"])),
            )
    return rows


def main():
    rng = np.random.default_rng(SEED)
    df = pd.DataFrame(build_rows(rng))
    df = df.sort_values("date", kind="stable").reset_index(drop=True)
    df.insert(0, "id", np.arange(1001, 1001 + len(df)))

    # Intentionally blank about 4% of amounts and 4% of notes (missing-data demo).
    k = int(round(0.04 * len(df)))
    df.loc[rng.choice(len(df), size=k, replace=False), "amount"] = np.nan
    df.loc[rng.choice(len(df), size=k, replace=False), "note"] = np.nan

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUTPUT, index=False)
    print(f"Wrote {len(df)} rows to {OUTPUT}")
    print(f"Blank amounts: {df['amount'].isna().sum()}, blank notes: {df['note'].isna().sum()}")


if __name__ == "__main__":
    main()