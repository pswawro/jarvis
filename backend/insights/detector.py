"""Statistical anomaly detection methods."""

import numpy as np
import pandas as pd


def _infer_window_rows(df: pd.DataFrame, window_months: int) -> int:
    """Convert a window expressed in months to a row count based on data frequency.

    Infers frequency from the median gap between consecutive period_date values.
    Monthly data → window_months rows.  Weekly → ~4× more.  Daily → ~30× more.
    Returns at least 2 rows.
    """
    dates = sorted(df["period_date"].unique())
    if len(dates) < 2:
        return max(window_months, 2)

    gaps = np.diff([d.timestamp() if hasattr(d, 'timestamp') else pd.Timestamp(d).timestamp() for d in dates])
    median_gap_days = float(np.median(gaps)) / 86400

    if median_gap_days < 1:
        median_gap_days = 1

    # How many rows fit in the requested number of months (≈30.44 days/month)
    rows = int(round(window_months * 30.44 / median_gap_days))
    return max(rows, 1)


def detect_outliers(
    df: pd.DataFrame,
    value_col: str,
    entity_type: str,
    group_cols: list[str],
    profile: dict,
    data_domain: str,
) -> list[dict]:
    """Trend-line residual outlier detection (both tails).

    Fits a linear trend on the history and checks whether the latest point
    deviates significantly from the trend projection in *either* direction.
    A revenue drop below trend is just as important as a spike above it.

    Uses sample std (ddof=1) and enforces a minimum residual std floor of
    1% of the history mean to prevent tiny denominators from inflating
    scores on very-smooth series.
    """
    threshold = profile["zscore_notable"]
    anomalies = []

    for keys, group in df.groupby(group_cols):
        if not isinstance(keys, tuple):
            keys = (keys,)
        group = group.sort_values("period_date")
        if len(group) < 6:            # need enough history for a meaningful fit
            continue

        values = group[value_col].values
        latest = values[-1]
        history = values[:-1]
        n = len(history)
        x = np.arange(n, dtype=float)

        # Fit linear trend on history
        coeffs = np.polyfit(x, history, 1)  # [slope, intercept]
        trend_vals = np.polyval(coeffs, x)
        residuals = history - trend_vals

        # Sample std with floor to avoid tiny denominators
        std = residuals.std(ddof=1)
        floor = abs(history.mean()) * 0.01   # 1% of mean as minimum
        std = max(std, floor)
        if np.isnan(std) or std == 0:
            continue        # Project trend one step and compute residual
        predicted = np.polyval(coeffs, float(n))
        residual = latest - predicted

        # Both tails: flag points significantly above OR below trend
        zscore = abs(residual) / std
        direction = "above" if residual > 0 else "below"

        if zscore >= threshold:
            entity = {"type": entity_type}
            for col, val in zip(group_cols, keys):
                entity[col] = val

            anomalies.append({
                "entity": entity,
                "detection_type": "outlier",
                "data_domain": data_domain,
                "statistical_score": round(zscore, 2),                "raw_stats": {
                    "current_value": round(float(latest), 2),
                    "trend_predicted": round(float(predicted), 2),
                    "residual": round(float(residual), 2),
                    "residual_std": round(float(std), 2),
                    "trend_slope": round(float(coeffs[0]), 4),
                    "zscore": round(zscore, 2),
                    "direction": direction,
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
    """Drift detection via slope change relative to the series scale.

    Compares the slope in the recent window to the slope in the pre-window
    history.  The slope change is expressed as a percentage of the series
    mean — this gives an intuitive, scale-independent measure:

        drift_pct = |slope_recent - slope_historical| / series_mean × 100

    A drift_pct of 10 means the growth rate shifted by 10% of the average
    value per month — a genuinely material change in trajectory.

    Scoring: drift_pct is mapped to the z-score scale by dividing by 3
    (so a 7.5% shift ≈ zscore 2.5 at the "low" sensitivity threshold).
    """
    window = _infer_window_rows(df, profile["rolling_window_months"])
    threshold = profile["zscore_notable"]
    anomalies = []

    for keys, group in df.groupby(group_cols):
        if not isinstance(keys, tuple):
            keys = (keys,)
        group = group.sort_values("period_date")
        if len(group) < window + 4:
            continue

        values = group[value_col].values
        n = len(values)
        pre_end = n - window
        pre_values = values[:pre_end]
        recent_values = values[pre_end:]

        if len(pre_values) < 4:
            continue

        series_mean = abs(values.mean())
        if series_mean == 0:
            continue

        # Fit slopes on each segment
        x_pre = np.arange(len(pre_values), dtype=float)
        slope_pre = np.polyfit(x_pre, pre_values, 1)[0]

        x_recent = np.arange(len(recent_values), dtype=float)
        slope_recent = np.polyfit(x_recent, recent_values, 1)[0]

        slope_change = slope_recent - slope_pre
        drift_pct = abs(slope_change) / series_mean * 100

        # Map to z-score scale: 3% drift_pct ≈ 1.0 score
        drift_score = drift_pct / 3.0

        if drift_score >= threshold:
            entity = {"type": entity_type}
            for col, val in zip(group_cols, keys):
                entity[col] = val

            direction = "accelerating" if slope_change > 0 else "decelerating"

            anomalies.append({
                "entity": entity,
                "detection_type": "drift",
                "data_domain": data_domain,
                "statistical_score": round(drift_score, 2),
                "raw_stats": {
                    "slope_recent": round(float(slope_recent), 4),
                    "slope_historical": round(float(slope_pre), 4),
                    "slope_change": round(float(slope_change), 4),
                    "drift_pct": round(drift_pct, 2),
                    "drift_score": round(drift_score, 2),
                    "direction": direction,
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
    """Detect significant period-over-period market share changes.

    Compares the average share in the most recent period-window to the
    preceding period-window.  For monthly data the window is 1 (last month
    vs. prior month); for weekly/daily data it auto-scales so we compare
    roughly month-sized windows rather than single rows.
    """
    delta_threshold = profile["market_share_delta_pct"]
    window = _infer_window_rows(commercial_df, 1)  # 1-month equivalent
    anomalies = []

    for (brand, market), group in commercial_df.groupby(["brand_id", "market_id"]):
        group = group.sort_values("period_date")
        if len(group) < window * 2:
            continue

        shares = group["az_market_share_pct"].values
        recent_avg = shares[-window:].mean()
        previous_avg = shares[-2 * window:-window].mean()
        delta = recent_avg - previous_avg

        if abs(delta) >= delta_threshold:
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
                    "current_share": round(float(recent_avg), 2),
                    "previous_share": round(float(previous_avg), 2),
                    "delta_pct": round(float(delta), 2),
                    "category": group["category"].iloc[-1],
                },
            })

    return anomalies
