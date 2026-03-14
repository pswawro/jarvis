"""Statistical anomaly detection methods."""

import numpy as np
import pandas as pd


def detect_outliers(
    df: pd.DataFrame,
    value_col: str,
    entity_type: str,
    group_cols: list[str],
    profile: dict,
    data_domain: str,
) -> list[dict]:
    """Z-score outlier detection per group. Returns anomalies for the latest month."""
    threshold = profile["zscore_notable"]
    anomalies = []

    for keys, group in df.groupby(group_cols):
        if not isinstance(keys, tuple):
            keys = (keys,)
        group = group.sort_values("period_date")
        if len(group) < 4:
            continue

        values = group[value_col].values
        mean, std = values.mean(), values.std()
        if std == 0 or np.isnan(std):
            continue

        latest = values[-1]
        zscore = abs((latest - mean) / std)

        if zscore >= threshold:
            entity = {"type": entity_type}
            for col, val in zip(group_cols, keys):
                entity[col] = val

            anomalies.append({
                "entity": entity,
                "detection_type": "outlier",
                "data_domain": data_domain,
                "statistical_score": round(zscore, 2),
                "raw_stats": {
                    "current_value": round(float(latest), 2),
                    "mean": round(float(mean), 2),
                    "std": round(float(std), 2),
                    "zscore": round(zscore, 2),
                },
            })

    return anomalies


def detect_drift(
    df: pd.DataFrame,
    value_col: str,
    entity_type: str,
    group_cols: list[str],
    profile: dict,
    data_domain: str,
) -> list[dict]:
    """Rolling mean drift detection. Compares recent window to overall baseline."""
    window = profile["rolling_window_months"]
    threshold = profile["zscore_notable"]
    anomalies = []

    for keys, group in df.groupby(group_cols):
        if not isinstance(keys, tuple):
            keys = (keys,)
        group = group.sort_values("period_date")
        if len(group) < window + 3:
            continue

        values = group[value_col].values
        overall_mean = values[:-window].mean()
        overall_std = values[:-window].std()
        if overall_std == 0 or np.isnan(overall_std):
            continue

        rolling_mean = values[-window:].mean()
        drift_score = abs((rolling_mean - overall_mean) / overall_std)

        if drift_score >= threshold:
            entity = {"type": entity_type}
            for col, val in zip(group_cols, keys):
                entity[col] = val

            anomalies.append({
                "entity": entity,
                "detection_type": "drift",
                "data_domain": data_domain,
                "statistical_score": round(drift_score, 2),
                "raw_stats": {
                    "rolling_mean": round(float(rolling_mean), 2),
                    "overall_mean": round(float(overall_mean), 2),
                    "overall_std": round(float(overall_std), 2),
                    "drift_score": round(drift_score, 2),
                    "window_months": window,
                },
            })

    return anomalies


def detect_target_misses(
    actuals_df: pd.DataFrame,
    targets_df: pd.DataFrame,
    actual_col: str,
    target_col: str,
    entity_type: str,
    group_cols: list[str],
    profile: dict,
) -> list[dict]:
    """Detect months where actual misses target beyond threshold."""
    miss_threshold = profile["target_miss_pct"]
    anomalies = []

    merged = actuals_df.merge(
        targets_df,
        on=["period_date"] + group_cols,
        how="inner",
        suffixes=("", "_target"),
    )

    for keys, group in merged.groupby(group_cols):
        if not isinstance(keys, tuple):
            keys = (keys,)
        group = group.sort_values("period_date")
        latest = group.iloc[-1]

        actual = latest[actual_col]
        target = latest[target_col]
        if target == 0:
            continue

        miss_pct = (target - actual) / target
        if miss_pct >= miss_threshold:
            entity = {"type": entity_type}
            for col, val in zip(group_cols, keys):
                entity[col] = val

            # Score: map miss_pct to comparable scale with z-scores
            score = miss_pct / miss_threshold

            anomalies.append({
                "entity": entity,
                "detection_type": "target_miss",
                "data_domain": "revenue",
                "statistical_score": round(score, 2),
                "raw_stats": {
                    "actual": round(float(actual), 2),
                    "target": round(float(target), 2),
                    "miss_pct": round(miss_pct, 4),
                    "comparator": target_col.replace("_amount", "").upper(),
                },
            })

    return anomalies


def detect_competitive_shifts(
    commercial_df: pd.DataFrame,
    profile: dict,
) -> list[dict]:
    """Detect significant month-over-month market share changes."""
    delta_threshold = profile["market_share_delta_pct"]
    anomalies = []

    for (brand, market), group in commercial_df.groupby(["brand_id", "market_id"]):
        group = group.sort_values("period_date")
        if len(group) < 2:
            continue

        shares = group["az_market_share_pct"].values
        delta = shares[-1] - shares[-2]

        if abs(delta) >= delta_threshold:
            # Score: map delta to comparable scale
            score = abs(delta) / delta_threshold

            anomalies.append({
                "entity": {
                    "type": "brand_market",
                    "brand_id": brand,
                    "market_id": market,
                },
                "detection_type": "competitive_shift",
                "data_domain": "market",
                "statistical_score": round(score, 2),
                "raw_stats": {
                    "current_share": round(float(shares[-1]), 2),
                    "previous_share": round(float(shares[-2]), 2),
                    "delta_pct": round(float(delta), 2),
                    "category": group["category"].iloc[-1],
                },
            })

    return anomalies
