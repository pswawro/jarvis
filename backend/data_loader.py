"""Load all CSV datasets and config into pandas DataFrames at startup."""

import json
import pandas as pd
from pathlib import Path
from datetime import datetime

DATA_DIR = Path(__file__).parent.parent / "data"

products: pd.DataFrame
geographies: pd.DataFrame
organization: pd.DataFrame
revenue: pd.DataFrame
expenses: pd.DataFrame
targets: pd.DataFrame
commercial: pd.DataFrame
users: pd.DataFrame
headcount: pd.DataFrame
app_config: dict
data_refreshed_at: str


def load_all():
    global products, geographies, organization, revenue, expenses, targets
    global commercial, users, headcount, app_config, data_refreshed_at

    products = pd.read_csv(DATA_DIR / "dim_product.csv")
    geographies = pd.read_csv(DATA_DIR / "dim_geography.csv")
    organization = pd.read_csv(DATA_DIR / "dim_organization.csv")
    revenue = pd.read_csv(DATA_DIR / "financial_revenue.csv")
    expenses = pd.read_csv(DATA_DIR / "financial_expenses.csv")
    targets = pd.read_csv(DATA_DIR / "financial_targets.csv")
    commercial = pd.read_csv(DATA_DIR / "commercial_market.csv")
    users = pd.read_csv(DATA_DIR / "user_access.csv")
    headcount = pd.read_csv(DATA_DIR / "headcount_fte.csv")

    with open(DATA_DIR / "config.json") as f:
        app_config = json.load(f)

    for df in [revenue, expenses, targets, commercial, headcount]:
        df["period_date"] = pd.to_datetime(df["period_date"])

    data_refreshed_at = datetime.now().strftime("%Y-%m-%d %H:%M")
