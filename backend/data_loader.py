"""Load all CSV datasets and config into pandas DataFrames at startup."""

import json
import pandas as pd
from pathlib import Path
from datetime import datetime

DATA_DIR = Path(__file__).parent.parent / "data"


class DataStore:
    """Encapsulates all loaded data as typed attributes."""

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

    def load_all(self):
        self.products = pd.read_csv(DATA_DIR / "dim_product.csv")
        self.geographies = pd.read_csv(DATA_DIR / "dim_geography.csv")
        self.organization = pd.read_csv(DATA_DIR / "dim_organization.csv")
        self.revenue = pd.read_csv(DATA_DIR / "financial_revenue.csv")
        self.expenses = pd.read_csv(DATA_DIR / "financial_expenses.csv")
        self.targets = pd.read_csv(DATA_DIR / "financial_targets.csv")
        self.commercial = pd.read_csv(DATA_DIR / "commercial_market.csv")
        self.users = pd.read_csv(DATA_DIR / "user_access.csv")
        self.headcount = pd.read_csv(DATA_DIR / "headcount_fte.csv")

        with open(DATA_DIR / "config.json") as f:
            self.app_config = json.load(f)

        for name in ["revenue", "expenses", "targets", "commercial", "headcount"]:
            df = getattr(self, name)
            df = df.copy()
            df["period_date"] = pd.to_datetime(df["period_date"])
            setattr(self, name, df)

        self.data_refreshed_at = datetime.now().strftime("%Y-%m-%d %H:%M")


store = DataStore()


def load_all():
    store.load_all()


def __getattr__(name: str):
    return getattr(store, name)
