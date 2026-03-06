"""Load all CSV datasets into pandas DataFrames at startup."""

import pandas as pd
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"

products: pd.DataFrame
geographies: pd.DataFrame
organization: pd.DataFrame
revenue: pd.DataFrame
expenses: pd.DataFrame
targets: pd.DataFrame
commercial: pd.DataFrame
users: pd.DataFrame


def load_all():
    global products, geographies, organization, revenue, expenses, targets, commercial, users

    products = pd.read_csv(DATA_DIR / "dim_product.csv")
    geographies = pd.read_csv(DATA_DIR / "dim_geography.csv")
    organization = pd.read_csv(DATA_DIR / "dim_organization.csv")
    revenue = pd.read_csv(DATA_DIR / "financial_revenue.csv")
    expenses = pd.read_csv(DATA_DIR / "financial_expenses.csv")
    targets = pd.read_csv(DATA_DIR / "financial_targets.csv")
    commercial = pd.read_csv(DATA_DIR / "commercial_market.csv")
    users = pd.read_csv(DATA_DIR / "user_access.csv")

    for df in [revenue, expenses, targets, commercial]:
        df["period_date"] = pd.to_datetime(df["period_date"])
