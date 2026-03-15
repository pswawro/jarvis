"""
Generate realistic AstraZeneca dummy datasets for the AI30 hackathon prototype.
All revenue figures are based on AZ's actual public investor relations data (2023-2025).
"""

import csv
import json
import random
import os
from datetime import date, datetime

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

# Sub-unit -> Unit (management/expense hierarchy)
# Added department and management_unit_code for FCT parity
ORGANIZATION = [
    # (sub_unit_id, sub_unit_name, unit, department, mgmt_unit_code)
    ("COM_US", "US Commercial", "Commercial", "Sales & Marketing", "MU_COM_01"),
    ("COM_CN", "China Commercial", "Commercial", "Sales & Marketing", "MU_COM_02"),
    ("COM_MKTG", "Global Marketing", "Commercial", "Sales & Marketing", "MU_COM_03"),
    ("COM_ACCESS", "Market Access", "Commercial", "Sales & Marketing", "MU_COM_04"),
    ("RD_ONCO", "Oncology R&D", "R&D", "Research", "MU_RD_01"),
    ("RD_BIO", "BioPharma R&D", "R&D", "Research", "MU_RD_02"),
    ("RD_CLIN", "Clinical Operations", "R&D", "Development", "MU_RD_03"),
    ("RD_REG", "Regulatory Affairs", "R&D", "Development", "MU_RD_04"),
    ("OPS_US", "US Manufacturing", "Operations", "Manufacturing", "MU_OPS_01"),
    ("OPS_CN", "China Manufacturing", "Operations", "Manufacturing", "MU_OPS_02"),
    ("OPS_SC", "Supply Chain", "Operations", "Supply & Logistics", "MU_OPS_03"),
    ("OPS_QA", "Quality", "Operations", "Quality & Compliance", "MU_OPS_04"),
    ("FIN_FPA", "FP&A", "Finance", "Financial Planning", "MU_FIN_01"),
    ("FIN_TREAS", "Treasury & Tax", "Finance", "Financial Planning", "MU_FIN_02"),
    ("FIN_ACCT", "Accounting", "Finance", "Financial Reporting", "MU_FIN_03"),
    ("FIN_AUDIT", "Internal Audit", "Finance", "Financial Reporting", "MU_FIN_04"),
    ("EN_HR", "HR", "Enabling", "People & Culture", "MU_EN_01"),
    ("EN_IT", "IT & Digital", "Enabling", "Technology", "MU_EN_02"),
    ("EN_LEGAL", "Legal & Compliance", "Enabling", "Legal Affairs", "MU_EN_03"),
    ("EN_COMMS", "Communications", "Enabling", "Corporate Affairs", "MU_EN_04"),
]

# =============================================================================
# 2. REAL AZ REVENUE DATA (global, $B) from public investor relations
# =============================================================================

BRAND_REVENUES_GLOBAL = {
    "TAGRISSO":  {2023: 5.8, 2024: 6.6, 2025: 7.3, 2026: 7.9},
    "IMFINZI":   {2023: 4.2, 2024: 4.7, 2025: 6.1, 2026: 7.2},
    "LYNPARZA":  {2023: 2.8, 2024: 3.7, 2025: 3.3, 2026: 3.0},
    "CALQUENCE": {2023: 2.5, 2024: 3.1, 2025: 3.5, 2026: 3.9},
    "ENHERTU":   {2023: 1.3, 2024: 2.0, 2025: 2.8, 2026: 3.6},
    "KOSELUGO":  {2023: 0.3, 2024: 0.6, 2025: 0.9, 2026: 1.2},
    "TRUQAP":    {2023: 0.0, 2024: 0.2, 2025: 0.4, 2026: 0.7},
    "FARXIGA":   {2023: 6.0, 2024: 7.7, 2025: 8.4, 2026: 9.1},
    "BRILINTA":  {2023: 1.3, 2024: 1.3, 2025: 0.9, 2026: 0.7},
    "LOKELMA":   {2023: 0.4, 2024: 0.5, 2025: 0.7, 2026: 0.9},
    "CRESTOR":   {2023: 1.1, 2024: 1.2, 2025: 1.1, 2026: 1.0},
    "SYMBICORT": {2023: 2.4, 2024: 2.9, 2025: 2.7, 2026: 2.5},
    "BREZTRI":   {2023: 0.7, 2024: 1.0, 2025: 1.1, 2026: 1.3},
    "FASENRA":   {2023: 1.6, 2024: 1.7, 2025: 1.8, 2026: 1.9},
    "SAPHNELO":  {2023: 0.3, 2024: 0.5, 2025: 0.7, 2026: 0.9},
    "TEZSPIRE":  {2023: 0.3, 2024: 0.7, 2025: 1.0, 2026: 1.4},
    "ULTOMIRIS": {2023: 3.0, 2024: 3.9, 2025: 4.4, 2026: 4.9},
    "SOLIRIS":   {2023: 3.1, 2024: 2.6, 2025: 0.5, 2026: 0.3},
    "STRENSIQ":  {2023: 1.2, 2024: 1.4, 2025: 1.7, 2026: 1.9},
    "BEYFORTUS": {2023: 0.1, 2024: 0.7, 2025: 0.9, 2026: 1.2},
}

# Market split: US ~43%, China ~11% of AZ revenue
MARKET_SPLIT = {
    "TAGRISSO":  (0.75, 0.25),
    "IMFINZI":   (0.80, 0.20),
    "LYNPARZA":  (0.82, 0.18),
    "CALQUENCE": (0.85, 0.15),
    "ENHERTU":   (0.83, 0.17),
    "KOSELUGO":  (0.88, 0.12),
    "TRUQAP":    (0.90, 0.10),
    "FARXIGA":   (0.78, 0.22),
    "BRILINTA":  (0.72, 0.28),
    "LOKELMA":   (0.80, 0.20),
    "CRESTOR":   (0.65, 0.35),
    "SYMBICORT": (0.70, 0.30),
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

# COGS as fraction of revenue
COGS_RATES = {
    "Oncology": 0.18,
    "CVRM": 0.19,
    "R&I": 0.20,
    "Rare Disease": 0.17,
    "V&I": 0.22,
}

# =============================================================================
# 2b. GROSS-TO-NET DEDUCTION RATES (as fraction of gross product sales)
# =============================================================================

# US has higher GTN (~30%), China lower (~10%)
GTN_RATES = {
    "US": {
        "returns": 0.03,
        "rebates_negotiable": 0.10,
        "rebates_non_negotiable": 0.06,
        "early_payment_discount": 0.02,
        "patient_programs": 0.05,
        "tax_and_clawbacks": 0.02,
    },
    "CN": {
        "returns": 0.02,
        "rebates_negotiable": 0.03,
        "rebates_non_negotiable": 0.02,
        "early_payment_discount": 0.01,
        "patient_programs": 0.01,
        "tax_and_clawbacks": 0.02,
    },
}

# =============================================================================
# 3. EXPENSE ALLOCATION
# =============================================================================

TOTAL_OPEX = {2023: 19.6, 2024: 24.0, 2025: 25.6, 2026: 27.2}

UNIT_EXPENSE_SHARE = {
    "Commercial": 0.35,
    "R&D": 0.40,
    "Operations": 0.12,
    "Finance": 0.06,
    "Enabling": 0.07,
}

SUBUNIT_WEIGHTS = {
    "Commercial": {"COM_US": 0.40, "COM_CN": 0.20, "COM_MKTG": 0.25, "COM_ACCESS": 0.15},
    "R&D": {"RD_ONCO": 0.40, "RD_BIO": 0.30, "RD_CLIN": 0.20, "RD_REG": 0.10},
    "Operations": {"OPS_US": 0.35, "OPS_CN": 0.25, "OPS_SC": 0.25, "OPS_QA": 0.15},
    "Finance": {"FIN_FPA": 0.35, "FIN_TREAS": 0.25, "FIN_ACCT": 0.25, "FIN_AUDIT": 0.15},
    "Enabling": {"EN_HR": 0.30, "EN_IT": 0.35, "EN_LEGAL": 0.25, "EN_COMMS": 0.10},
}

COST_TYPE_SPLIT = {
    "Commercial": {"personnel": 0.55, "external": 0.30, "other": 0.15},
    "R&D": {"personnel": 0.40, "external": 0.45, "other": 0.15},
    "Operations": {"personnel": 0.45, "external": 0.35, "other": 0.20},
    "Finance": {"personnel": 0.65, "external": 0.20, "other": 0.15},
    "Enabling": {"personnel": 0.60, "external": 0.20, "other": 0.20},
}

# =============================================================================
# 4. BUDGET/FORECAST/MTP/RBU2 VARIANCE PROFILES
# =============================================================================

BUDGET_BIAS = {
    "TAGRISSO": -0.02,
    "IMFINZI": -0.05,
    "LYNPARZA": 0.04,
    "CALQUENCE": -0.03,
    "ENHERTU": -0.06,
    "KOSELUGO": -0.04,
    "TRUQAP": -0.08,
    "FARXIGA": 0.03,
    "BRILINTA": 0.05,
    "LOKELMA": -0.03,
    "CRESTOR": 0.02,
    "SYMBICORT": 0.03,
    "BREZTRI": -0.04,
    "FASENRA": 0.02,
    "SAPHNELO": -0.05,
    "TEZSPIRE": -0.07,
    "ULTOMIRIS": -0.03,
    "SOLIRIS": 0.06,
    "STRENSIQ": -0.02,
    "BEYFORTUS": -0.08,
}

EXPENSE_BUDGET_BIAS = {
    "COM_US": 0.03,
    "COM_CN": -0.02,
    "COM_MKTG": 0.04,
    "COM_ACCESS": -0.01,
    "RD_ONCO": 0.05,
    "RD_BIO": 0.03,
    "RD_CLIN": 0.06,
    "RD_REG": -0.02,
    "OPS_US": 0.02,
    "OPS_CN": -0.03,
    "OPS_SC": 0.04,
    "OPS_QA": -0.01,
    "FIN_FPA": -0.02,
    "FIN_TREAS": -0.01,
    "FIN_ACCT": 0.01,
    "FIN_AUDIT": -0.03,
    "EN_HR": 0.02,
    "EN_IT": 0.05,
    "EN_LEGAL": 0.03,
    "EN_COMMS": -0.02,
}

# =============================================================================
# 4b. FTE DATA — base headcount per sub-unit
# =============================================================================

BASE_FTE = {
    "COM_US": 2800,
    "COM_CN": 1600,
    "COM_MKTG": 650,
    "COM_ACCESS": 400,
    "RD_ONCO": 1800,
    "RD_BIO": 1200,
    "RD_CLIN": 900,
    "RD_REG": 350,
    "OPS_US": 1400,
    "OPS_CN": 950,
    "OPS_SC": 700,
    "OPS_QA": 450,
    "FIN_FPA": 280,
    "FIN_TREAS": 180,
    "FIN_ACCT": 220,
    "FIN_AUDIT": 120,
    "EN_HR": 350,
    "EN_IT": 550,
    "EN_LEGAL": 280,
    "EN_COMMS": 150,
}

# YoY FTE growth rate
FTE_GROWTH_RATE = 0.035  # 3.5% YoY

# =============================================================================
# 5. COMMERCIAL MARKET DATA
# =============================================================================

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
    # (user_id, name, role, access_level, markets, tas, units, can_see_budget, can_see_forecast, can_see_mtp, can_see_rbu2, default_comparator)
    ("user_001", "Sarah Chen", "CEO", "total_az", "ALL", "ALL", "ALL", True, True, True, True, "BUD"),
    ("user_002", "James Miller", "CFO", "total_az", "ALL", "ALL", "ALL", True, True, True, True, "BUD"),
    ("user_003", "Maria Rodriguez", "VP Oncology", "therapeutic_area", "ALL", "Oncology", "ALL", True, True, True, True, "BUD"),
    ("user_004", "Wei Zhang", "China GM", "market", "CN", "ALL", "ALL", True, True, True, False, "BUD"),
    ("user_005", "David Park", "VP CVRM", "therapeutic_area", "ALL", "CVRM", "ALL", True, False, False, False, "BUD"),
    ("user_006", "Lisa Thompson", "US Commercial Lead", "unit", "US", "ALL", "Commercial", True, True, True, True, "MTP"),
    ("user_007", "Robert Kim", "R&D Director", "unit", "ALL", "ALL", "R&D", False, False, False, False, "BUD"),
    ("user_008", "Anna Kowalski", "Finance Director", "unit", "ALL", "ALL", "Finance", True, True, True, True, "BUD"),
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
        month_in_q = (month - 1) % 3
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
    for sub_unit_id, sub_unit_name, unit, department, mgmt_code in ORGANIZATION:
        rows.append({
            "sub_unit_id": sub_unit_id,
            "sub_unit_name": sub_unit_name,
            "unit": unit,
            "department": department,
            "management_unit_code": mgmt_code,
        })
    write_csv("dim_organization.csv", rows,
              ["sub_unit_id", "sub_unit_name", "unit", "department", "management_unit_code"])
    return rows


def generate_financial_revenue():
    """Generate monthly revenue data by brand x market for 2023-2025.

    Now includes gross-to-net breakdown:
    gross_product_sales -> deductions -> revenue (net product sales)
    """
    rows = []
    for brand_id, brand_name, ta, indication in PRODUCTS:
        us_frac, cn_frac = MARKET_SPLIT[brand_id]
        cogs_rate = COGS_RATES[ta]

        for year in [2023, 2024, 2025, 2026]:
            global_rev = BRAND_REVENUES_GLOBAL[brand_id][year]

            for market_id, market_frac in [("US", us_frac), ("CN", cn_frac)]:
                annual_market_rev = global_rev * market_frac * 1000  # $B to $M
                # This is NET revenue; we need to back-calculate gross
                gtn_rates = GTN_RATES[market_id]
                total_gtn_rate = sum(gtn_rates.values())
                # gross * (1 - total_gtn_rate) = net -> gross = net / (1 - total_gtn_rate)
                annual_gross = annual_market_rev / (1 - total_gtn_rate)
                monthly_gross = distribute_annual_to_monthly(annual_gross, year)

                for month_idx, gps in enumerate(monthly_gross):
                    month = month_idx + 1

                    # Calculate each GTN deduction with some noise
                    returns = round(gps * gtn_rates["returns"] * random.uniform(0.90, 1.10), 2)
                    reb_neg = round(gps * gtn_rates["rebates_negotiable"] * random.uniform(0.92, 1.08), 2)
                    reb_non = round(gps * gtn_rates["rebates_non_negotiable"] * random.uniform(0.95, 1.05), 2)
                    epd = round(gps * gtn_rates["early_payment_discount"] * random.uniform(0.90, 1.10), 2)
                    patient = round(gps * gtn_rates["patient_programs"] * random.uniform(0.88, 1.12), 2)
                    tax_claw = round(gps * gtn_rates["tax_and_clawbacks"] * random.uniform(0.90, 1.10), 2)

                    total_deductions = returns + reb_neg + reb_non + epd + patient + tax_claw
                    net_rev = round(gps - total_deductions, 2)
                    cogs = round(net_rev * cogs_rate * random.uniform(0.97, 1.03), 2)
                    gross_profit = round(net_rev - cogs, 2)

                    rows.append({
                        "period_date": f"{year}-{month:02d}-01",
                        "year": year,
                        "quarter": get_quarter(month),
                        "month": month,
                        "brand_id": brand_id,
                        "market_id": market_id,
                        "gross_product_sales": round(gps, 2),
                        "returns": returns,
                        "rebates_negotiable": reb_neg,
                        "rebates_non_negotiable": reb_non,
                        "early_payment_discount": epd,
                        "patient_programs": patient,
                        "tax_and_clawbacks": tax_claw,
                        "revenue": net_rev,
                        "cost_of_sales": cogs,
                        "gross_profit": gross_profit,
                    })

    fields = [
        "period_date", "year", "quarter", "month", "brand_id", "market_id",
        "gross_product_sales", "returns", "rebates_negotiable", "rebates_non_negotiable",
        "early_payment_discount", "patient_programs", "tax_and_clawbacks",
        "revenue", "cost_of_sales", "gross_profit",
    ]
    write_csv("financial_revenue.csv", rows, fields)
    return rows


def generate_financial_expenses():
    """Generate monthly expense data by sub-unit for 2023-2025."""
    rows = []
    for sub_unit_id, sub_unit_name, unit, dept, mgmt in ORGANIZATION:
        unit_share = UNIT_EXPENSE_SHARE[unit]
        subunit_weight = SUBUNIT_WEIGHTS[unit][sub_unit_id]
        cost_split = COST_TYPE_SPLIT[unit]

        for year in [2023, 2024, 2025, 2026]:
            total_opex = TOTAL_OPEX[year]
            annual_subunit_opex = total_opex * unit_share * subunit_weight * 1000
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
    """Generate budget, forecast, MTP, and RBU2 targets for revenue and expenses."""
    rows = []

    # Revenue targets
    for rev_row in revenue_rows:
        brand_id = rev_row["brand_id"]
        bias = BUDGET_BIAS[brand_id]
        actual = rev_row["revenue"]
        month = int(rev_row["period_date"].split("-")[1])

        # Budget: what we planned (actual adjusted by bias)
        budget_rev = round(actual / (1 + bias + random.uniform(-0.02, 0.02)), 2)
        # Forecast: closer to actuals
        forecast_rev = round(actual / (1 + bias * 0.3 + random.uniform(-0.01, 0.01)), 2)
        # MTP: strategic plan, diverges more from actuals (bias * 0.7 + larger noise)
        mtp_rev = round(actual / (1 + bias * 0.7 + random.uniform(-0.04, 0.04)), 2)
        # RBU2: mid-year reforecast — H1 close to actuals, H2 diverges
        rbu2_noise = random.uniform(-0.01, 0.01) if month <= 6 else random.uniform(-0.03, 0.03)
        rbu2_bias = bias * 0.15 if month <= 6 else bias * 0.6
        rbu2_rev = round(actual / (1 + rbu2_bias + rbu2_noise), 2)

        rows.append({
            "period_date": rev_row["period_date"],
            "target_type": "revenue",
            "entity_id": brand_id,
            "market_id": rev_row["market_id"],
            "budget_amount": budget_rev,
            "forecast_amount": forecast_rev,
            "mtp_amount": mtp_rev,
            "rbu2_amount": rbu2_rev,
        })

    # Expense targets
    for exp_row in expense_rows:
        sub_unit_id = exp_row["sub_unit_id"]
        bias = EXPENSE_BUDGET_BIAS[sub_unit_id]
        actual = exp_row["total_operating_expenses"]
        month = int(exp_row["period_date"].split("-")[1])

        budget_exp = round(actual / (1 + bias + random.uniform(-0.02, 0.02)), 2)
        forecast_exp = round(actual / (1 + bias * 0.3 + random.uniform(-0.01, 0.01)), 2)
        mtp_exp = round(actual / (1 + bias * 0.7 + random.uniform(-0.04, 0.04)), 2)
        rbu2_noise = random.uniform(-0.01, 0.01) if month <= 6 else random.uniform(-0.03, 0.03)
        rbu2_bias = bias * 0.15 if month <= 6 else bias * 0.6
        rbu2_exp = round(actual / (1 + rbu2_bias + rbu2_noise), 2)

        rows.append({
            "period_date": exp_row["period_date"],
            "target_type": "expense",
            "entity_id": sub_unit_id,
            "market_id": "",
            "budget_amount": budget_exp,
            "forecast_amount": forecast_exp,
            "mtp_amount": mtp_exp,
            "rbu2_amount": rbu2_exp,
        })

    write_csv("financial_targets.csv", rows,
              ["period_date", "target_type", "entity_id", "market_id",
               "budget_amount", "forecast_amount", "mtp_amount", "rbu2_amount"])
    return rows


def generate_headcount_fte():
    """Generate monthly FTE/headcount data by sub-unit for 2023-2025."""
    rows = []
    for sub_unit_id, sub_unit_name, unit, dept, mgmt in ORGANIZATION:
        base = BASE_FTE[sub_unit_id]

        for year in [2023, 2024, 2025, 2026]:
            # YoY growth from 2023 baseline
            years_from_base = year - 2023
            annual_base = base * ((1 + FTE_GROWTH_RATE) ** years_from_base)

            for month in range(1, 13):
                # Small monthly variation (+/- 1.5%)
                monthly_noise = random.uniform(-0.015, 0.015)
                fte = round(annual_base * (1 + monthly_noise), 1)
                # Headcount is always integer, slightly above FTE (contractors, part-time)
                headcount = int(fte * random.uniform(1.02, 1.08))

                rows.append({
                    "period_date": f"{year}-{month:02d}-01",
                    "year": year,
                    "quarter": get_quarter(month),
                    "month": month,
                    "sub_unit_id": sub_unit_id,
                    "fte_count": fte,
                    "headcount": headcount,
                })

    write_csv("headcount_fte.csv", rows,
              ["period_date", "year", "quarter", "month", "sub_unit_id", "fte_count", "headcount"])
    return rows


def generate_commercial_market():
    """Generate commercial market data for 2024-2026."""
    rows = []
    for brand_id, brand_name, ta, indication in PRODUCTS:
        category = DRUG_CATEGORIES[brand_id]
        cat_data = CATEGORY_MARKET_DATA[category]
        us_frac, cn_frac = MARKET_SPLIT[brand_id]

        for year in [2024, 2025, 2026]:
            global_rev = BRAND_REVENUES_GLOBAL[brand_id][year]
            year_growth_factor = (1 + cat_data["growth"]) ** (year - 2024)

            for market_id, market_frac in [("US", us_frac), ("CN", cn_frac)]:
                base_market_size = cat_data["us_size"] if market_id == "US" else cat_data["cn_size"]
                market_size = base_market_size * year_growth_factor * 1000
                az_annual_rev = global_rev * market_frac * 1000
                monthly_revs = distribute_annual_to_monthly(az_annual_rev, year)

                for month_idx, az_rev in enumerate(monthly_revs):
                    month = month_idx + 1
                    monthly_market = market_size / 12 * random.uniform(0.95, 1.05)
                    share = round((az_rev / monthly_market) * 100, 1) if monthly_market > 0 else 0
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
            "can_see_mtp": user[9],
            "can_see_rbu2": user[10],
            "default_comparator": user[11],
        })
    write_csv("user_access.csv", rows,
              ["user_id", "user_name", "role", "access_level",
               "allowed_markets", "allowed_tas", "allowed_units",
               "can_see_budget", "can_see_forecast", "can_see_mtp", "can_see_rbu2",
               "default_comparator"])
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

    print("\n2. Financial revenue (with GTN breakdown):")
    revenue_rows = generate_financial_revenue()

    print("\n3. Financial expenses:")
    expense_rows = generate_financial_expenses()

    print("\n4. Financial targets (budget, forecast, MTP, RBU2):")
    generate_financial_targets(revenue_rows, expense_rows)

    print("\n5. Headcount / FTE:")
    generate_headcount_fte()

    print("\n6. Commercial market data:")
    generate_commercial_market()

    print("\n7. User access:")
    generate_user_access()

    print("\nDone! All datasets generated.")


if __name__ == "__main__":
    main()
