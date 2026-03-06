"""
Generate realistic AstraZeneca dummy datasets for the AI30 hackathon prototype.
All revenue figures are based on AZ's actual public investor relations data (2023-2025).
"""

import csv
import random
import os
from datetime import date

random.seed(42)

OUTPUT_DIR = os.path.dirname(os.path.abspath(__file__))

# =============================================================================
# 1. DIMENSION DATA
# =============================================================================

PRODUCTS = [
    # (brand_id, brand_name, therapeutic_area, indication)
    ("TAGRISSO", "Tagrisso", "Oncology", "NSCLC (EGFR-mutated)"),
    ("IMFINZI", "Imfinzi", "Oncology", "Lung cancer, biliary tract cancer"),
    ("LYNPARZA", "Lynparza", "Oncology", "Ovarian, breast, prostate cancer (BRCA)"),
    ("CALQUENCE", "Calquence", "Oncology", "CLL/SLL (blood cancer)"),
    ("ENHERTU", "Enhertu", "Oncology", "HER2+ breast, lung, gastric cancer"),
    ("KOSELUGO", "Koselugo", "Oncology", "Neurofibromatosis type 1"),
    ("TRUQAP", "Truqap", "Oncology", "HR+/HER2- breast cancer"),
    ("FARXIGA", "Farxiga", "CVRM", "Type 2 diabetes, heart failure, CKD"),
    ("BRILINTA", "Brilinta", "CVRM", "Acute coronary syndrome"),
    ("LOKELMA", "Lokelma", "CVRM", "Hyperkalemia"),
    ("CRESTOR", "Crestor", "CVRM", "Cholesterol management"),
    ("SYMBICORT", "Symbicort", "R&I", "Asthma, COPD"),
    ("BREZTRI", "Breztri", "R&I", "COPD triple therapy"),
    ("FASENRA", "Fasenra", "R&I", "Severe eosinophilic asthma"),
    ("SAPHNELO", "Saphnelo", "R&I", "Systemic lupus erythematosus"),
    ("TEZSPIRE", "Tezspire", "R&I", "Severe asthma"),
    ("ULTOMIRIS", "Ultomiris", "Rare Disease", "PNH, aHUS, gMG, NMOSD"),
    ("SOLIRIS", "Soliris", "Rare Disease", "PNH, aHUS"),
    ("STRENSIQ", "Strensiq", "Rare Disease", "Hypophosphatasia"),
    ("BEYFORTUS", "Beyfortus", "V&I", "RSV prevention in infants"),
]

GEOGRAPHIES = [
    ("US", "United States", "North America"),
    ("CN", "China", "International"),
]

# Sub-unit → Unit (management/expense hierarchy)
ORGANIZATION = [
    ("COM_US", "US Commercial", "Commercial"),
    ("COM_CN", "China Commercial", "Commercial"),
    ("COM_MKTG", "Global Marketing", "Commercial"),
    ("COM_ACCESS", "Market Access", "Commercial"),
    ("RD_ONCO", "Oncology R&D", "R&D"),
    ("RD_BIO", "BioPharma R&D", "R&D"),
    ("RD_CLIN", "Clinical Operations", "R&D"),
    ("RD_REG", "Regulatory Affairs", "R&D"),
    ("OPS_US", "US Manufacturing", "Operations"),
    ("OPS_CN", "China Manufacturing", "Operations"),
    ("OPS_SC", "Supply Chain", "Operations"),
    ("OPS_QA", "Quality", "Operations"),
    ("FIN_FPA", "FP&A", "Finance"),
    ("FIN_TREAS", "Treasury & Tax", "Finance"),
    ("FIN_ACCT", "Accounting", "Finance"),
    ("FIN_AUDIT", "Internal Audit", "Finance"),
    ("EN_HR", "HR", "Enabling"),
    ("EN_IT", "IT & Digital", "Enabling"),
    ("EN_LEGAL", "Legal & Compliance", "Enabling"),
    ("EN_COMMS", "Communications", "Enabling"),
]

# =============================================================================
# 2. REAL AZ REVENUE DATA (global, $B) from public investor relations
# =============================================================================

# {brand_id: {year: global_revenue_in_billions}}
BRAND_REVENUES_GLOBAL = {
    "TAGRISSO":  {2023: 5.8, 2024: 6.6, 2025: 7.3},
    "IMFINZI":   {2023: 4.2, 2024: 4.7, 2025: 6.1},
    "LYNPARZA":  {2023: 2.8, 2024: 3.7, 2025: 3.3},
    "CALQUENCE": {2023: 2.5, 2024: 3.1, 2025: 3.5},
    "ENHERTU":   {2023: 1.3, 2024: 2.0, 2025: 2.8},
    "KOSELUGO":  {2023: 0.3, 2024: 0.6, 2025: 0.9},
    "TRUQAP":    {2023: 0.0, 2024: 0.2, 2025: 0.4},
    "FARXIGA":   {2023: 6.0, 2024: 7.7, 2025: 8.4},
    "BRILINTA":  {2023: 1.3, 2024: 1.3, 2025: 0.9},
    "LOKELMA":   {2023: 0.4, 2024: 0.5, 2025: 0.7},
    "CRESTOR":   {2023: 1.1, 2024: 1.2, 2025: 1.1},
    "SYMBICORT": {2023: 2.4, 2024: 2.9, 2025: 2.7},
    "BREZTRI":   {2023: 0.7, 2024: 1.0, 2025: 1.1},
    "FASENRA":   {2023: 1.6, 2024: 1.7, 2025: 1.8},
    "SAPHNELO":  {2023: 0.3, 2024: 0.5, 2025: 0.7},
    "TEZSPIRE":  {2023: 0.3, 2024: 0.7, 2025: 1.0},
    "ULTOMIRIS": {2023: 3.0, 2024: 3.9, 2025: 4.4},
    "SOLIRIS":   {2023: 3.1, 2024: 2.6, 2025: 0.5},
    "STRENSIQ":  {2023: 1.2, 2024: 1.4, 2025: 1.7},
    "BEYFORTUS": {2023: 0.1, 2024: 0.7, 2025: 0.9},
}

# Market split: US ~43% of total AZ revenue, China ~11%.
# In our 2-market universe, normalize: US = 43/(43+11) ≈ 80%, China ≈ 20%
# Some brands skew differently — China-heavy brands get adjusted
MARKET_SPLIT = {
    # brand_id: (US_fraction, CN_fraction) — must sum to 1.0
    "TAGRISSO":  (0.75, 0.25),  # Strong in China (lung cancer)
    "IMFINZI":   (0.80, 0.20),
    "LYNPARZA":  (0.82, 0.18),
    "CALQUENCE": (0.85, 0.15),
    "ENHERTU":   (0.83, 0.17),
    "KOSELUGO":  (0.88, 0.12),
    "TRUQAP":    (0.90, 0.10),  # New, mostly US launch
    "FARXIGA":   (0.78, 0.22),  # Big in China (diabetes)
    "BRILINTA":  (0.72, 0.28),  # Relatively strong in China
    "LOKELMA":   (0.80, 0.20),
    "CRESTOR":   (0.65, 0.35),  # Legacy, big China generic market
    "SYMBICORT": (0.70, 0.30),  # Respiratory big in China
    "BREZTRI":   (0.82, 0.18),
    "FASENRA":   (0.85, 0.15),
    "SAPHNELO":  (0.88, 0.12),
    "TEZSPIRE":  (0.85, 0.15),
    "ULTOMIRIS": (0.82, 0.18),
    "SOLIRIS":   (0.80, 0.20),
    "STRENSIQ":  (0.85, 0.15),
    "BEYFORTUS": (0.82, 0.18),
}

# Quarterly seasonal weights (Q1 lowest, Q4 highest)
QUARTERLY_WEIGHTS = {1: 0.22, 2: 0.24, 3: 0.25, 4: 0.29}
# Monthly weights within a quarter (slight ramp)
MONTHLY_WITHIN_Q = [0.32, 0.33, 0.35]

# COGS as fraction of revenue (varies slightly by brand type)
COGS_RATES = {
    "Oncology": 0.18,
    "CVRM": 0.19,
    "R&I": 0.20,
    "Rare Disease": 0.17,
    "V&I": 0.22,
}

# =============================================================================
# 3. EXPENSE ALLOCATION
# =============================================================================

# Total operating expenses (excl. COGS) scaled to our 20-brand revenue universe ($B)
# Target: ~51% of revenue so that operating margin ≈ 31% (after ~18% COGS)
# Our brand revenues: ~$38.4B / ~$47B / ~$50.2B for 2023/24/25
TOTAL_OPEX = {2023: 19.6, 2024: 24.0, 2025: 25.6}

# How total opex distributes across units (approximate %)
UNIT_EXPENSE_SHARE = {
    "Commercial": 0.35,   # SG&A heavy
    "R&D": 0.40,          # Biggest cost center
    "Operations": 0.12,
    "Finance": 0.06,
    "Enabling": 0.07,
}

# Within each unit, how sub-units split (relative weights)
SUBUNIT_WEIGHTS = {
    "Commercial": {"COM_US": 0.40, "COM_CN": 0.20, "COM_MKTG": 0.25, "COM_ACCESS": 0.15},
    "R&D": {"RD_ONCO": 0.40, "RD_BIO": 0.30, "RD_CLIN": 0.20, "RD_REG": 0.10},
    "Operations": {"OPS_US": 0.35, "OPS_CN": 0.25, "OPS_SC": 0.25, "OPS_QA": 0.15},
    "Finance": {"FIN_FPA": 0.35, "FIN_TREAS": 0.25, "FIN_ACCT": 0.25, "FIN_AUDIT": 0.15},
    "Enabling": {"EN_HR": 0.30, "EN_IT": 0.35, "EN_LEGAL": 0.25, "EN_COMMS": 0.10},
}

# Cost type split within sub-units
COST_TYPE_SPLIT = {
    "Commercial": {"personnel": 0.55, "external": 0.30, "other": 0.15},
    "R&D": {"personnel": 0.40, "external": 0.45, "other": 0.15},
    "Operations": {"personnel": 0.45, "external": 0.35, "other": 0.20},
    "Finance": {"personnel": 0.65, "external": 0.20, "other": 0.15},
    "Enabling": {"personnel": 0.60, "external": 0.20, "other": 0.20},
}

# =============================================================================
# 4. BUDGET/FORECAST VARIANCE PROFILES
# =============================================================================

# Per-brand budget bias: positive = brand beats budget, negative = misses
# These create realistic stories (some brands outperform, others underperform)
BUDGET_BIAS = {
    "TAGRISSO": -0.02,    # Slightly misses (competition)
    "IMFINZI": -0.05,     # Misses budget (slower uptake than planned)
    "LYNPARZA": 0.04,     # Beats budget
    "CALQUENCE": -0.03,
    "ENHERTU": -0.06,     # Fast growth hard to budget — often conservative budget
    "KOSELUGO": -0.04,
    "TRUQAP": -0.08,      # New launch — hardest to predict
    "FARXIGA": 0.03,      # Reliable outperformer
    "BRILINTA": 0.05,     # Declines faster than budgeted
    "LOKELMA": -0.03,
    "CRESTOR": 0.02,
    "SYMBICORT": 0.03,
    "BREZTRI": -0.04,
    "FASENRA": 0.02,
    "SAPHNELO": -0.05,
    "TEZSPIRE": -0.07,    # Hockey stick — conservative budget
    "ULTOMIRIS": -0.03,
    "SOLIRIS": 0.06,      # Declines faster than budgeted
    "STRENSIQ": -0.02,
    "BEYFORTUS": -0.08,   # New launch — budget miss
}

# Expense budget bias per sub-unit
EXPENSE_BUDGET_BIAS = {
    "COM_US": 0.03,       # Overspend vs budget
    "COM_CN": -0.02,
    "COM_MKTG": 0.04,
    "COM_ACCESS": -0.01,
    "RD_ONCO": 0.05,      # R&D often overspends
    "RD_BIO": 0.03,
    "RD_CLIN": 0.06,      # Clinical trials cost overruns
    "RD_REG": -0.02,
    "OPS_US": 0.02,
    "OPS_CN": -0.03,
    "OPS_SC": 0.04,       # Supply chain disruptions
    "OPS_QA": -0.01,
    "FIN_FPA": -0.02,
    "FIN_TREAS": -0.01,
    "FIN_ACCT": 0.01,
    "FIN_AUDIT": -0.03,
    "EN_HR": 0.02,
    "EN_IT": 0.05,        # IT projects tend to overrun
    "EN_LEGAL": 0.03,
    "EN_COMMS": -0.02,
}

# =============================================================================
# 5. COMMERCIAL MARKET DATA
# =============================================================================

# Drug categories and their total market sizes ($B) for US and China
DRUG_CATEGORIES = {
    "TAGRISSO": "EGFR TKI inhibitors",
    "IMFINZI": "PD-1/PD-L1 checkpoint inhibitors",
    "LYNPARZA": "PARP inhibitors",
    "CALQUENCE": "BTK inhibitors",
    "ENHERTU": "HER2-targeted ADCs",
    "KOSELUGO": "MEK inhibitors",
    "TRUQAP": "AKT inhibitors",
    "FARXIGA": "SGLT2 inhibitors",
    "BRILINTA": "P2Y12 antiplatelet agents",
    "LOKELMA": "Potassium binders",
    "CRESTOR": "Statins",
    "SYMBICORT": "ICS/LABA combinations",
    "BREZTRI": "Triple therapy inhalers",
    "FASENRA": "Anti-IL5/IL5R biologics",
    "SAPHNELO": "Anti-IFNAR biologics",
    "TEZSPIRE": "Anti-TSLP biologics",
    "ULTOMIRIS": "Complement C5 inhibitors",
    "SOLIRIS": "Complement C5 inhibitors",
    "STRENSIQ": "Enzyme replacement therapies",
    "BEYFORTUS": "RSV preventive antibodies",
}

# Category market sizes ($B, US) and AZ approximate share
# market_size is for the whole category in a market
CATEGORY_MARKET_DATA = {
    "EGFR TKI inhibitors":           {"us_size": 8.0,  "cn_size": 3.5, "growth": 0.12},
    "PD-1/PD-L1 checkpoint inhibitors": {"us_size": 22.0, "cn_size": 8.0, "growth": 0.15},
    "PARP inhibitors":               {"us_size": 5.5,  "cn_size": 1.5, "growth": 0.08},
    "BTK inhibitors":                {"us_size": 9.0,  "cn_size": 1.8, "growth": 0.10},
    "HER2-targeted ADCs":            {"us_size": 6.0,  "cn_size": 1.5, "growth": 0.25},
    "MEK inhibitors":                {"us_size": 1.2,  "cn_size": 0.3, "growth": 0.18},
    "AKT inhibitors":                {"us_size": 0.8,  "cn_size": 0.1, "growth": 0.30},
    "SGLT2 inhibitors":              {"us_size": 18.0, "cn_size": 5.0, "growth": 0.14},
    "P2Y12 antiplatelet agents":     {"us_size": 4.0,  "cn_size": 2.5, "growth": -0.05},
    "Potassium binders":             {"us_size": 1.5,  "cn_size": 0.4, "growth": 0.12},
    "Statins":                       {"us_size": 12.0, "cn_size": 6.0, "growth": -0.02},
    "ICS/LABA combinations":         {"us_size": 10.0, "cn_size": 4.0, "growth": 0.03},
    "Triple therapy inhalers":       {"us_size": 4.5,  "cn_size": 1.0, "growth": 0.20},
    "Anti-IL5/IL5R biologics":       {"us_size": 5.0,  "cn_size": 0.8, "growth": 0.10},
    "Anti-IFNAR biologics":          {"us_size": 1.0,  "cn_size": 0.2, "growth": 0.35},
    "Anti-TSLP biologics":           {"us_size": 2.5,  "cn_size": 0.5, "growth": 0.40},
    "Complement C5 inhibitors":      {"us_size": 7.0,  "cn_size": 1.5, "growth": 0.08},
    "Enzyme replacement therapies":  {"us_size": 3.0,  "cn_size": 0.5, "growth": 0.06},
    "RSV preventive antibodies":     {"us_size": 3.0,  "cn_size": 0.5, "growth": 0.50},
}

# =============================================================================
# 6. USER ACCESS
# =============================================================================

USER_ACCESS = [
    ("user_001", "Sarah Chen", "CEO", "total_az", "ALL", "ALL", "ALL", True, True),
    ("user_002", "James Miller", "CFO", "total_az", "ALL", "ALL", "ALL", True, True),
    ("user_003", "Maria Rodriguez", "VP Oncology", "therapeutic_area", "ALL", "Oncology", "ALL", True, True),
    ("user_004", "Wei Zhang", "China GM", "market", "CN", "ALL", "ALL", True, True),
    ("user_005", "David Park", "VP CVRM", "therapeutic_area", "ALL", "CVRM", "ALL", True, False),
    ("user_006", "Lisa Thompson", "US Commercial Lead", "unit", "US", "ALL", "Commercial", True, True),
    ("user_007", "Robert Kim", "R&D Director", "unit", "ALL", "ALL", "R&D", False, False),
    ("user_008", "Anna Kowalski", "Finance Director", "unit", "ALL", "ALL", "Finance", True, True),
]


# =============================================================================
# GENERATION FUNCTIONS
# =============================================================================

def get_quarter(month: int) -> str:
    return f"Q{(month - 1) // 3 + 1}"


def get_quarter_num(month: int) -> int:
    return (month - 1) // 3 + 1


def distribute_annual_to_monthly(annual_value: float, year: int) -> list[float]:
    """Distribute an annual value into 12 monthly values with seasonality + noise."""
    monthly = []
    for month in range(1, 13):
        q = get_quarter_num(month)
        month_in_q = (month - 1) % 3  # 0, 1, 2
        q_share = QUARTERLY_WEIGHTS[q]
        m_share = MONTHLY_WITHIN_Q[month_in_q]
        base = annual_value * q_share * m_share
        noise = random.uniform(-0.02, 0.02)
        monthly.append(round(base * (1 + noise), 2))
    return monthly


def generate_dim_product():
    rows = []
    for brand_id, brand_name, ta, indication in PRODUCTS:
        rows.append({
            "brand_id": brand_id,
            "brand_name": brand_name,
            "therapeutic_area": ta,
            "indication": indication,
        })
    write_csv("dim_product.csv", rows, ["brand_id", "brand_name", "therapeutic_area", "indication"])
    return rows


def generate_dim_geography():
    rows = []
    for market_id, market_name, region in GEOGRAPHIES:
        rows.append({
            "market_id": market_id,
            "market_name": market_name,
            "region": region,
        })
    write_csv("dim_geography.csv", rows, ["market_id", "market_name", "region"])
    return rows


def generate_dim_organization():
    rows = []
    for sub_unit_id, sub_unit_name, unit in ORGANIZATION:
        rows.append({
            "sub_unit_id": sub_unit_id,
            "sub_unit_name": sub_unit_name,
            "unit": unit,
        })
    write_csv("dim_organization.csv", rows, ["sub_unit_id", "sub_unit_name", "unit"])
    return rows


def generate_financial_revenue():
    """Generate monthly revenue data by brand × market for 2023-2025."""
    rows = []
    for brand_id, brand_name, ta, indication in PRODUCTS:
        us_frac, cn_frac = MARKET_SPLIT[brand_id]
        cogs_rate = COGS_RATES[ta]

        for year in [2023, 2024, 2025]:
            global_rev = BRAND_REVENUES_GLOBAL[brand_id][year]

            for market_id, market_frac in [("US", us_frac), ("CN", cn_frac)]:
                annual_market_rev = global_rev * market_frac * 1000  # Convert $B to $M
                monthly_revs = distribute_annual_to_monthly(annual_market_rev, year)

                for month_idx, rev in enumerate(monthly_revs):
                    month = month_idx + 1
                    cogs = round(rev * cogs_rate * random.uniform(0.97, 1.03), 2)
                    gross = round(rev - cogs, 2)

                    rows.append({
                        "period_date": f"{year}-{month:02d}-01",
                        "year": year,
                        "quarter": get_quarter(month),
                        "month": month,
                        "brand_id": brand_id,
                        "market_id": market_id,
                        "revenue": rev,
                        "cost_of_sales": cogs,
                        "gross_profit": gross,
                    })

    write_csv("financial_revenue.csv", rows,
              ["period_date", "year", "quarter", "month", "brand_id", "market_id",
               "revenue", "cost_of_sales", "gross_profit"])
    return rows


def generate_financial_expenses():
    """Generate monthly expense data by sub-unit for 2023-2025."""
    rows = []
    for sub_unit_id, sub_unit_name, unit in ORGANIZATION:
        unit_share = UNIT_EXPENSE_SHARE[unit]
        subunit_weight = SUBUNIT_WEIGHTS[unit][sub_unit_id]
        cost_split = COST_TYPE_SPLIT[unit]

        for year in [2023, 2024, 2025]:
            total_opex = TOTAL_OPEX[year]
            annual_subunit_opex = total_opex * unit_share * subunit_weight * 1000  # $B to $M
            monthly_opex = distribute_annual_to_monthly(annual_subunit_opex, year)

            for month_idx, total_exp in enumerate(monthly_opex):
                month = month_idx + 1
                personnel = round(total_exp * cost_split["personnel"] * random.uniform(0.97, 1.03), 2)
                external = round(total_exp * cost_split["external"] * random.uniform(0.95, 1.05), 2)
                other = round(total_exp * cost_split["other"] * random.uniform(0.93, 1.07), 2)
                total_recalc = round(personnel + external + other, 2)

                rows.append({
                    "period_date": f"{year}-{month:02d}-01",
                    "year": year,
                    "quarter": get_quarter(month),
                    "month": month,
                    "sub_unit_id": sub_unit_id,
                    "personnel_costs": personnel,
                    "external_costs": external,
                    "other_costs": other,
                    "total_operating_expenses": total_recalc,
                })

    write_csv("financial_expenses.csv", rows,
              ["period_date", "year", "quarter", "month", "sub_unit_id",
               "personnel_costs", "external_costs", "other_costs", "total_operating_expenses"])
    return rows


def generate_financial_targets(revenue_rows, expense_rows):
    """Generate budget and forecast targets for both revenue and expenses."""
    rows = []

    # Revenue targets
    for rev_row in revenue_rows:
        brand_id = rev_row["brand_id"]
        bias = BUDGET_BIAS[brand_id]
        # Budget: what we planned (actual revenue adjusted by bias)
        # If bias is negative, actual < budget (we missed), so budget = actual / (1 + bias)
        # If bias is positive, actual > budget (we beat), so budget = actual / (1 + bias)
        budget_rev = round(rev_row["revenue"] / (1 + bias + random.uniform(-0.02, 0.02)), 2)
        # Forecast: closer to actuals than budget
        forecast_rev = round(rev_row["revenue"] / (1 + bias * 0.3 + random.uniform(-0.01, 0.01)), 2)

        rows.append({
            "period_date": rev_row["period_date"],
            "target_type": "revenue",
            "entity_id": brand_id,
            "market_id": rev_row["market_id"],
            "budget_amount": budget_rev,
            "forecast_amount": forecast_rev,
        })

    # Expense targets
    for exp_row in expense_rows:
        sub_unit_id = exp_row["sub_unit_id"]
        bias = EXPENSE_BUDGET_BIAS[sub_unit_id]
        # For expenses, positive bias means actual > budget (overspend)
        budget_exp = round(exp_row["total_operating_expenses"] / (1 + bias + random.uniform(-0.02, 0.02)), 2)
        forecast_exp = round(exp_row["total_operating_expenses"] / (1 + bias * 0.3 + random.uniform(-0.01, 0.01)), 2)

        rows.append({
            "period_date": exp_row["period_date"],
            "target_type": "expense",
            "entity_id": sub_unit_id,
            "market_id": "",
            "budget_amount": budget_exp,
            "forecast_amount": forecast_exp,
        })

    write_csv("financial_targets.csv", rows,
              ["period_date", "target_type", "entity_id", "market_id",
               "budget_amount", "forecast_amount"])
    return rows


def generate_commercial_market():
    """Generate commercial market data for 2024-2025 only."""
    rows = []
    for brand_id, brand_name, ta, indication in PRODUCTS:
        category = DRUG_CATEGORIES[brand_id]
        cat_data = CATEGORY_MARKET_DATA[category]
        us_frac, cn_frac = MARKET_SPLIT[brand_id]

        for year in [2024, 2025]:
            global_rev = BRAND_REVENUES_GLOBAL[brand_id][year]
            # Market grows each year
            year_growth_factor = 1.0 if year == 2024 else (1 + cat_data["growth"])

            for market_id, market_frac in [("US", us_frac), ("CN", cn_frac)]:
                base_market_size = cat_data["us_size"] if market_id == "US" else cat_data["cn_size"]
                market_size = base_market_size * year_growth_factor * 1000  # $B to $M
                az_annual_rev = global_rev * market_frac * 1000
                monthly_revs = distribute_annual_to_monthly(az_annual_rev, year)

                for month_idx, az_rev in enumerate(monthly_revs):
                    month = month_idx + 1
                    monthly_market = market_size / 12 * random.uniform(0.95, 1.05)
                    share = round((az_rev / monthly_market) * 100, 1) if monthly_market > 0 else 0
                    # Clamp share to reasonable range
                    share = min(share, 85.0)
                    growth = round(cat_data["growth"] * 100 + random.uniform(-2, 2), 1)

                    rows.append({
                        "period_date": f"{year}-{month:02d}-01",
                        "brand_id": brand_id,
                        "market_id": market_id,
                        "category": category,
                        "total_market_size_usd_m": round(monthly_market, 2),
                        "market_growth_pct": growth,
                        "az_market_share_pct": share,
                        "az_revenue_usd_m": az_rev,
                    })

    write_csv("commercial_market.csv", rows,
              ["period_date", "brand_id", "market_id", "category",
               "total_market_size_usd_m", "market_growth_pct",
               "az_market_share_pct", "az_revenue_usd_m"])
    return rows


def generate_user_access():
    rows = []
    for user in USER_ACCESS:
        rows.append({
            "user_id": user[0],
            "user_name": user[1],
            "role": user[2],
            "access_level": user[3],
            "allowed_markets": user[4],
            "allowed_tas": user[5],
            "allowed_units": user[6],
            "can_see_budget": user[7],
            "can_see_forecast": user[8],
        })
    write_csv("user_access.csv", rows,
              ["user_id", "user_name", "role", "access_level",
               "allowed_markets", "allowed_tas", "allowed_units",
               "can_see_budget", "can_see_forecast"])
    return rows


def write_csv(filename, rows, fieldnames):
    filepath = os.path.join(OUTPUT_DIR, filename)
    with open(filepath, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"  Written {filepath} ({len(rows)} rows)")


# =============================================================================
# MAIN
# =============================================================================

def main():
    print("Generating AZ dummy datasets...\n")

    print("1. Dimension tables:")
    generate_dim_product()
    generate_dim_geography()
    generate_dim_organization()

    print("\n2. Financial revenue:")
    revenue_rows = generate_financial_revenue()

    print("\n3. Financial expenses:")
    expense_rows = generate_financial_expenses()

    print("\n4. Financial targets (budget & forecast):")
    generate_financial_targets(revenue_rows, expense_rows)

    print("\n5. Commercial market data:")
    generate_commercial_market()

    print("\n6. User access:")
    generate_user_access()

    print("\nDone! All datasets generated.")


if __name__ == "__main__":
    main()
