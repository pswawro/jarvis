# Push Insights Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add proactive anomaly detection, AI-powered analysis, an insights panel UI, and Web Push notifications to Jarvis.

**Architecture:** A `backend/insights/` module runs statistical detection across all data dimensions, deduplicates via fingerprinting, sends above-threshold anomalies to Bedrock for AI analysis (reusing the existing assistant's client and tools), and stores results in `data/insights.json`. The frontend adds a lightbulb icon in the TopBar that opens a slide-out InsightsPanel with severity-tagged cards. Web Push via Service Worker delivers critical alerts.

**Tech Stack:** Python/Pandas (detection), AnthropicBedrock (AI analysis), pywebpush (push delivery), React/TypeScript/Framer Motion (frontend panel), Service Worker + Push API (browser push).

**Spec:** `docs/superpowers/specs/2026-03-13-push-insights-design.md`

---

## Chunk 1: Configuration, Storage, and Detection Engine

### Task 1: Sensitivity Config and Insight Storage Utilities

**Files:**
- Create: `data/insights_config.json`
- Create: `backend/insights/__init__.py`
- Create: `backend/insights/config.py`
- Create: `backend/insights/store.py`
- Create: `tests/test_insights_config.py`
- Create: `tests/test_insights_store.py`

- [ ] **Step 1: Create sensitivity config JSON**

Create `data/insights_config.json`:

```json
{
  "active_profile": "medium",
  "profiles": {
    "high": {
      "zscore_critical": 2.5,
      "zscore_notable": 1.5,
      "rolling_window_months": 3,
      "target_miss_pct": 0.08,
      "market_share_delta_pct": 1.5
    },
    "medium": {
      "zscore_critical": 3.0,
      "zscore_notable": 2.0,
      "rolling_window_months": 3,
      "target_miss_pct": 0.12,
      "market_share_delta_pct": 2.5
    },
    "low": {
      "zscore_critical": 3.5,
      "zscore_notable": 2.5,
      "rolling_window_months": 3,
      "target_miss_pct": 0.15,
      "market_share_delta_pct": 3.5
    }
  }
}
```

- [ ] **Step 2: Create `backend/insights/__init__.py`**

Empty file to make the module importable.

- [ ] **Step 3: Write failing test for config loader**

Create `tests/test_insights_config.py`:

```python
"""Tests for insights configuration loading."""

import os
import pytest
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from insights.config import load_sensitivity_profile


def test_load_default_profile():
    profile = load_sensitivity_profile()
    assert profile["zscore_critical"] == 3.0
    assert profile["zscore_notable"] == 2.0
    assert profile["rolling_window_months"] == 3
    assert profile["target_miss_pct"] == 0.12
    assert profile["market_share_delta_pct"] == 2.5


def test_load_high_profile_via_env(monkeypatch):
    monkeypatch.setenv("INSIGHT_SENSITIVITY", "high")
    profile = load_sensitivity_profile()
    assert profile["zscore_critical"] == 2.5


def test_invalid_profile_falls_back_to_default():
    profile = load_sensitivity_profile("nonexistent")
    assert profile["zscore_critical"] == 3.0
```

- [ ] **Step 4: Run test to verify it fails**

Run: `cd backend && python -m pytest ../tests/test_insights_config.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'insights.config'`

- [ ] **Step 5: Implement config loader**

Create `backend/insights/config.py`:

```python
"""Load sensitivity profiles from data/insights_config.json."""

import json
import os
from pathlib import Path

_CONFIG_PATH = Path(__file__).parent.parent.parent / "data" / "insights_config.json"


def load_sensitivity_profile(profile_name: str | None = None) -> dict:
    """Load a sensitivity profile by name.

    Priority: profile_name arg > INSIGHT_SENSITIVITY env var > JSON active_profile.
    Falls back to JSON active_profile if the requested profile doesn't exist.
    """
    raw = json.loads(_CONFIG_PATH.read_text())
    profiles = raw["profiles"]

    name = profile_name or os.getenv("INSIGHT_SENSITIVITY", "") or raw["active_profile"]
    if name not in profiles:
        name = raw["active_profile"]

    return profiles[name]
```

- [ ] **Step 6: Run test to verify it passes**

Run: `cd backend && python -m pytest ../tests/test_insights_config.py -v`
Expected: PASS

- [ ] **Step 7: Write failing test for insight store**

Create `tests/test_insights_store.py`:

```python
"""Tests for insight JSON store with atomic writes."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from insights.store import InsightStore


@pytest.fixture
def store(tmp_path):
    return InsightStore(tmp_path / "insights.json")


def test_empty_store_returns_empty_list(store):
    assert store.load_all() == []


def test_save_and_load_insight(store):
    insight = {
        "id": "ins_test1",
        "fingerprint": "brand_X_revenue_outlier",
        "status": "active",
        "read": False,
    }
    store.save_all([insight])
    loaded = store.load_all()
    assert len(loaded) == 1
    assert loaded[0]["id"] == "ins_test1"


def test_atomic_write_creates_valid_json(store):
    insights = [{"id": f"ins_{i}", "status": "active"} for i in range(5)]
    store.save_all(insights)
    # Verify the file is valid JSON
    raw = json.loads(store.path.read_text())
    assert len(raw) == 5


def test_mark_read(store):
    insights = [
        {"id": "ins_a", "read": False, "status": "active"},
        {"id": "ins_b", "read": False, "status": "active"},
    ]
    store.save_all(insights)
    result = store.mark_read("ins_a")
    assert result is True
    loaded = store.load_all()
    assert loaded[0]["read"] is True
    assert loaded[1]["read"] is False


def test_mark_read_nonexistent_returns_false(store):
    store.save_all([{"id": "ins_a", "read": False, "status": "active"}])
    result = store.mark_read("ins_nonexistent")
    assert result is False
```

- [ ] **Step 8: Run test to verify it fails**

Run: `cd backend && python -m pytest ../tests/test_insights_store.py -v`
Expected: FAIL — `ImportError: cannot import name 'InsightStore'`

- [ ] **Step 9: Implement insight store**

Create `backend/insights/store.py`:

```python
"""Atomic JSON file store for insights."""

import json
import os
import tempfile
from pathlib import Path


class InsightStore:
    def __init__(self, path: Path | str):
        self.path = Path(path)

    def load_all(self) -> list[dict]:
        if not self.path.exists():
            return []
        try:
            return json.loads(self.path.read_text())
        except (json.JSONDecodeError, FileNotFoundError):
            return []

    def save_all(self, insights: list[dict]) -> None:
        """Atomic write: write to temp file, then os.replace."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(
            dir=self.path.parent, suffix=".tmp", prefix=".insights_"
        )
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(insights, f, indent=2, default=str)
            os.replace(tmp, self.path)
        except BaseException:
            if os.path.exists(tmp):
                os.unlink(tmp)
            raise

    def mark_read(self, insight_id: str) -> bool:
        """Mark a single insight as read. Returns True if found."""
        insights = self.load_all()
        for ins in insights:
            if ins["id"] == insight_id:
                ins["read"] = True
                self.save_all(insights)
                return True
        return False
```

- [ ] **Step 10: Run test to verify it passes**

Run: `cd backend && python -m pytest ../tests/test_insights_store.py -v`
Expected: PASS

- [ ] **Step 11: Commit**

```bash
git add data/insights_config.json backend/insights/ tests/test_insights_config.py tests/test_insights_store.py
git commit -m "feat(insights): add sensitivity config and atomic JSON store"
```

---

### Task 2: Fingerprinting and Deduplication

**Files:**
- Create: `backend/insights/dedup.py`
- Create: `tests/test_insights_dedup.py`

- [ ] **Step 1: Write failing test for fingerprinting**

Create `tests/test_insights_dedup.py`:

```python
"""Tests for insight fingerprinting and deduplication."""

import pytest
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from insights.dedup import make_fingerprint, deduplicate


def test_fingerprint_brand_outlier():
    anomaly = {
        "entity": {"type": "brand", "brand_id": "TAGRISSO", "market_id": "US"},
        "detection_type": "outlier",
        "data_domain": "revenue",
    }
    fp = make_fingerprint(anomaly)
    assert fp == "brand_TAGRISSO_US_revenue_outlier"


def test_fingerprint_ta_drift():
    anomaly = {
        "entity": {"type": "ta", "ta": "Oncology"},
        "detection_type": "drift",
        "data_domain": "revenue",
    }
    fp = make_fingerprint(anomaly)
    assert fp == "ta_Oncology_revenue_drift"


def test_fingerprint_unit_target_miss():
    anomaly = {
        "entity": {"type": "unit", "unit": "Commercial"},
        "detection_type": "target_miss",
        "data_domain": "expenses",
    }
    fp = make_fingerprint(anomaly)
    assert fp == "unit_Commercial_expenses_target_miss"


def test_deduplicate_new_anomaly():
    existing = []
    anomalies = [{
        "entity": {"type": "brand", "brand_id": "X", "market_id": "US"},
        "detection_type": "outlier",
        "data_domain": "revenue",
        "statistical_score": 3.5,
    }]
    new, updated, seen_fps = deduplicate(anomalies, existing)
    assert len(new) == 1
    assert len(updated) == 0
    assert "brand_X_US_revenue_outlier" in seen_fps


def test_deduplicate_suppresses_existing():
    existing = [{
        "id": "ins_old",
        "fingerprint": "brand_X_US_revenue_outlier",
        "status": "active",
        "statistical_score": 3.0,
        "read": True,
    }]
    anomalies = [{
        "entity": {"type": "brand", "brand_id": "X", "market_id": "US"},
        "detection_type": "outlier",
        "data_domain": "revenue",
        "statistical_score": 3.1,  # similar, not worsened
    }]
    new, updated, seen_fps = deduplicate(anomalies, existing)
    assert len(new) == 0
    assert len(updated) == 0  # last_seen updated in place, but not "escalated"


def test_deduplicate_escalates_worsened():
    existing = [{
        "id": "ins_old",
        "fingerprint": "brand_X_US_revenue_outlier",
        "status": "active",
        "statistical_score": 2.5,
        "read": True,
        "severity": "notable",
    }]
    anomalies = [{
        "entity": {"type": "brand", "brand_id": "X", "market_id": "US"},
        "detection_type": "outlier",
        "data_domain": "revenue",
        "statistical_score": 4.0,  # significantly worse
    }]
    new, updated, seen_fps = deduplicate(anomalies, existing)
    assert len(new) == 0
    assert len(updated) == 1
    assert updated[0]["read"] is False  # re-flagged as unread
    assert updated[0]["statistical_score"] == 4.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest ../tests/test_insights_dedup.py -v`
Expected: FAIL — `ImportError`

- [ ] **Step 3: Implement dedup module**

Create `backend/insights/dedup.py`:

```python
"""Fingerprinting and deduplication for detected anomalies."""

from datetime import datetime, timezone


def make_fingerprint(anomaly: dict) -> str:
    """Create a stable fingerprint from entity + domain + detection type."""
    entity = anomaly["entity"]
    etype = entity["type"]
    detection = anomaly["detection_type"]
    domain = anomaly["data_domain"]

    parts = [etype]
    # Add identifying fields based on entity type
    if etype == "brand":
        parts.append(entity.get("brand_id", ""))
        if entity.get("market_id"):
            parts.append(entity["market_id"])
    elif etype == "ta":
        parts.append(entity.get("ta", ""))
    elif etype == "total":
        pass  # just "total"
    elif etype == "unit":
        parts.append(entity.get("unit", ""))
    elif etype == "sub_unit":
        parts.append(entity.get("sub_unit", ""))
    elif etype == "brand_market":
        parts.append(entity.get("brand_id", ""))
        parts.append(entity.get("market_id", ""))

    parts.append(domain)
    parts.append(detection)
    return "_".join(p for p in parts if p)


def deduplicate(
    anomalies: list[dict],
    existing_insights: list[dict],
    escalation_factor: float = 1.3,
) -> tuple[list[dict], list[dict], set[str]]:
    """Compare new anomalies against existing insights.

    Returns:
        new: anomalies that have no matching active insight
        updated: existing insights that were escalated (severity worsened)
        seen_fingerprints: all fingerprints from this detection run
    """
    now = datetime.now(timezone.utc).isoformat()
    active_by_fp = {
        ins["fingerprint"]: ins
        for ins in existing_insights
        if ins.get("status") == "active"
    }

    new = []
    updated = []
    seen_fps = set()

    for anomaly in anomalies:
        fp = make_fingerprint(anomaly)
        seen_fps.add(fp)

        if fp in active_by_fp:
            existing = active_by_fp[fp]
            existing["last_seen"] = now

            # Escalate if significantly worse
            if anomaly["statistical_score"] > existing.get("statistical_score", 0) * escalation_factor:
                existing["statistical_score"] = anomaly["statistical_score"]
                existing["read"] = False  # re-flag as unread
                existing["raw_stats"] = anomaly.get("raw_stats", existing.get("raw_stats"))
                updated.append(existing)
        else:
            new.append(anomaly)

    return new, updated, seen_fps
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest ../tests/test_insights_dedup.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/insights/dedup.py tests/test_insights_dedup.py
git commit -m "feat(insights): add fingerprinting and deduplication"
```

---

### Task 3: Statistical Detection Engine

**Files:**
- Create: `backend/insights/detector.py`
- Create: `tests/test_insights_detector.py`

- [ ] **Step 1: Write failing test for outlier detection**

Create `tests/test_insights_detector.py`:

```python
"""Tests for statistical anomaly detection."""

import pandas as pd
import numpy as np
import pytest
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from insights.detector import detect_outliers, detect_drift, detect_target_misses, detect_competitive_shifts


@pytest.fixture
def revenue_df():
    """Monthly revenue with one outlier month."""
    dates = pd.date_range("2024-01-01", periods=12, freq="MS")
    values = [100, 102, 98, 101, 99, 103, 100, 97, 101, 100, 99, 150]  # Dec is outlier
    return pd.DataFrame({
        "period_date": dates,
        "brand_id": "DRUG_A",
        "market_id": "US",
        "actual_amount": values,
    })


@pytest.fixture
def profile():
    return {
        "zscore_critical": 3.0,
        "zscore_notable": 2.0,
        "rolling_window_months": 3,
        "target_miss_pct": 0.12,
        "market_share_delta_pct": 2.5,
    }


def test_detect_outliers_finds_spike(revenue_df, profile):
    anomalies = detect_outliers(
        revenue_df, "actual_amount", "brand",
        group_cols=["brand_id", "market_id"],
        profile=profile,
        data_domain="revenue",
    )
    assert len(anomalies) >= 1
    outlier = anomalies[0]
    assert outlier["detection_type"] == "outlier"
    assert outlier["entity"]["brand_id"] == "DRUG_A"
    assert outlier["statistical_score"] > profile["zscore_notable"]


def test_detect_outliers_no_anomaly_in_flat_data(profile):
    dates = pd.date_range("2024-01-01", periods=12, freq="MS")
    df = pd.DataFrame({
        "period_date": dates,
        "brand_id": "DRUG_B",
        "market_id": "US",
        "actual_amount": [100] * 12,
    })
    anomalies = detect_outliers(
        df, "actual_amount", "brand",
        group_cols=["brand_id", "market_id"],
        profile=profile,
        data_domain="revenue",
    )
    assert len(anomalies) == 0


def test_detect_drift_finds_upward_trend(profile):
    dates = pd.date_range("2024-01-01", periods=12, freq="MS")
    # Baseline has natural variance; last 3 months well above historical mean
    values = [100, 102, 98, 101, 99, 103, 97, 101, 100, 120, 125, 130]
    df = pd.DataFrame({
        "period_date": dates,
        "unit": "Sales",
        "actual_amount": values,
    })
    anomalies = detect_drift(
        df, "actual_amount", "unit",
        group_cols=["unit"],
        profile=profile,
        data_domain="expenses",
    )
    assert len(anomalies) >= 1
    assert anomalies[0]["detection_type"] == "drift"


def test_detect_target_misses(profile):
    dates = pd.date_range("2024-01-01", periods=3, freq="MS")
    revenue = pd.DataFrame({
        "period_date": dates,
        "brand_id": "DRUG_A",
        "market_id": "US",
        "actual_amount": [80, 85, 70],
    })
    targets = pd.DataFrame({
        "period_date": dates,
        "brand_id": "DRUG_A",
        "market_id": "US",
        "budget_amount": [100, 100, 100],
    })
    anomalies = detect_target_misses(
        revenue, targets, "actual_amount", "budget_amount",
        entity_type="brand",
        group_cols=["brand_id", "market_id"],
        profile=profile,
    )
    # 70 vs 100 is a 30% miss, should be flagged
    assert any(a["raw_stats"]["miss_pct"] >= 0.12 for a in anomalies)


def test_detect_competitive_shifts(profile):
    dates = pd.date_range("2024-01-01", periods=6, freq="MS")
    df = pd.DataFrame({
        "period_date": dates,
        "brand_id": "DRUG_A",
        "market_id": "US",
        "category": "Oncology",
        "az_market_share_pct": [50, 50, 50, 50, 50, 44],  # 6pt drop last month
    })
    anomalies = detect_competitive_shifts(df, profile)
    assert len(anomalies) >= 1
    assert anomalies[0]["detection_type"] == "competitive_shift"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest ../tests/test_insights_detector.py -v`
Expected: FAIL — `ImportError`

- [ ] **Step 3: Implement detection engine**

Create `backend/insights/detector.py`:

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest ../tests/test_insights_detector.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/insights/detector.py tests/test_insights_detector.py
git commit -m "feat(insights): add statistical detection engine (outliers, drift, target miss, competitive shifts)"
```

---

### Task 4: Role Scoping

**Files:**
- Modify: `backend/assistant/roles/default.json`
- Modify: `backend/assistant/roles/cfo.json`
- Modify: `backend/assistant/roles/commercial.json`
- Modify: `backend/assistant/roles/market_lead.json`
- Create: `backend/insights/scoping.py`
- Create: `tests/test_insights_scoping.py`

- [ ] **Step 1: Add `insight_scope` to role configs**

Add the `insight_scope` field to each existing role JSON file, preserving all existing fields. Full updated `default.json`:

```json
{
  "id": "default",
  "label": "Enterprise Analyst",
  "prompt_context": "",
  "default_page": "overview",
  "tools": ["*"],
  "insight_scope": {
    "revenue": ["brand", "ta", "total"],
    "expenses": ["sub_unit", "unit", "total"],
    "market": ["brand_market"]
  }
}
```

For `cfo.json`, add `insight_scope` to the existing JSON (keep `id`, `label`, `prompt_context`, `default_page`, `tools`):

```json
"insight_scope": {
  "revenue": ["total", "ta"],
  "expenses": ["total", "unit"],
  "market": ["brand_market"]
}
```

For `commercial.json`, add to existing JSON:

```json
"insight_scope": {
  "revenue": ["brand", "ta"],
  "expenses": [],
  "market": ["brand_market"]
}
```

For `market_lead.json`, add to existing JSON:

```json
"insight_scope": {
  "revenue": ["brand", "ta", "total"],
  "expenses": [],
  "market": ["brand_market"]
}
```

- [ ] **Step 2: Write failing test for scoping**

Create `tests/test_insights_scoping.py`:

```python
"""Tests for role-based insight filtering."""

import pytest
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from insights.scoping import filter_by_role_scope


@pytest.fixture
def sample_insights():
    return [
        {"id": "1", "entity": {"type": "brand"}, "data_domain": "revenue"},
        {"id": "2", "entity": {"type": "ta"}, "data_domain": "revenue"},
        {"id": "3", "entity": {"type": "total"}, "data_domain": "revenue"},
        {"id": "4", "entity": {"type": "unit"}, "data_domain": "expenses"},
        {"id": "5", "entity": {"type": "brand_market"}, "data_domain": "market"},
    ]


def test_cfo_scope(sample_insights):
    scope = {"revenue": ["total", "ta"], "expenses": ["total", "unit"], "market": ["brand_market"]}
    filtered = filter_by_role_scope(sample_insights, scope)
    ids = [i["id"] for i in filtered]
    assert "1" not in ids  # brand-level revenue hidden
    assert "2" in ids      # ta-level revenue visible
    assert "3" in ids      # total revenue visible
    assert "4" in ids      # unit expenses visible
    assert "5" in ids      # market visible


def test_default_scope_sees_everything(sample_insights):
    scope = {
        "revenue": ["brand", "ta", "total"],
        "expenses": ["sub_unit", "unit", "total"],
        "market": ["brand_market"],
    }
    filtered = filter_by_role_scope(sample_insights, scope)
    assert len(filtered) == 5


def test_empty_scope_hides_domain(sample_insights):
    scope = {"revenue": ["brand"], "expenses": [], "market": []}
    filtered = filter_by_role_scope(sample_insights, scope)
    ids = [i["id"] for i in filtered]
    assert "1" in ids
    assert "4" not in ids
    assert "5" not in ids
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd backend && python -m pytest ../tests/test_insights_scoping.py -v`
Expected: FAIL — `ImportError`

- [ ] **Step 4: Implement scoping**

Create `backend/insights/scoping.py`:

```python
"""Role-based insight filtering."""

# Domain mapping: which data_domain values map to which scope categories
_DOMAIN_TO_SCOPE = {
    "revenue": "revenue",
    "expenses": "expenses",
    "market": "market",
}


def filter_by_role_scope(insights: list[dict], scope: dict) -> list[dict]:
    """Filter insights by role scope configuration.

    scope format: {"revenue": ["total", "ta"], "expenses": ["unit"], "market": ["brand_market"]}
    An insight is visible if its entity.type is in the scope list for its data_domain.
    """
    result = []
    for ins in insights:
        domain = ins.get("data_domain", "")
        scope_key = _DOMAIN_TO_SCOPE.get(domain)
        if scope_key is None:
            continue

        allowed_types = scope.get(scope_key, [])
        entity_type = ins.get("entity", {}).get("type", "")
        if entity_type in allowed_types:
            result.append(ins)

    return result
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd backend && python -m pytest ../tests/test_insights_scoping.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/assistant/roles/ backend/insights/scoping.py tests/test_insights_scoping.py
git commit -m "feat(insights): add role scoping with insight_scope config"
```

---

## Chunk 2: AI Analyzer, Trigger Script, API Route, and Existing File Changes

### Task 5: AI Insight Analyzer

**Files:**
- Create: `backend/insights/analyzer.py`
- Create: `backend/assistant/prompts/insight_analysis.txt`

- [ ] **Step 1: Create insight analysis prompt template**

Create `backend/assistant/prompts/insight_analysis.txt`:

```text
You are an analytics insight engine for AstraZeneca's Jarvis platform. You are analyzing an automatically detected data anomaly.

## Anomaly Details
- **Detection type:** {{detection_type}}
- **Entity:** {{entity_description}}
- **Statistical summary:** {{raw_stats}}
- **Data domain:** {{data_domain}}

## Your Task
1. Use the available tools to investigate this anomaly. Query related data to understand context.
2. Provide a concise explanation of what is happening and why.
3. Assess the business impact and assign a severity level.
4. Determine whether this warrants a push notification to the user.

## Response Format
Respond with EXACTLY this JSON structure (no other text):
```json
{
  "explanation": "2-4 sentence narrative explaining the anomaly and its likely cause",
  "revised_severity": "critical|notable|informational",
  "push": true|false
}
```

## Severity Guidelines
- **critical**: Significant business impact requiring immediate attention. Revenue shortfalls >15%, major market share losses, expense overruns threatening margins.
- **notable**: Worth attention but not urgent. Moderate variances, gradual trends, seasonal patterns that need monitoring.
- **informational**: Minor fluctuation with benign explanation. Seasonal effects, known business cycles, one-off events with no lasting impact.

You may RAISE severity if contextual evidence suggests the situation is worse than the raw numbers indicate (e.g., a revenue dip combined with market share loss and competitor activity).
You may LOWER severity if you find a benign explanation (e.g., flu drug revenue drops because flu season ended).

Set `push: true` ONLY for genuinely urgent findings. When in doubt, set `push: false`.
```

- [ ] **Step 2: Implement analyzer module**

Create `backend/insights/analyzer.py`:

```python
"""AI-powered insight analysis using Bedrock (same client as assistant)."""

import asyncio
import json
import logging
from pathlib import Path

from anthropic import AnthropicBedrock

import config
from assistant.tool_dispatch import TOOL_DISPATCH, UI_TOOLS
from assistant.prompt_builder import load_role

log = logging.getLogger(__name__)

_TOOLS_PATH = Path(__file__).parent.parent / "assistant" / "tools.json"
_PROMPT_PATH = Path(__file__).parent.parent / "assistant" / "prompts" / "insight_analysis.txt"


def _build_analysis_prompt(anomaly: dict) -> str:
    """Build the system prompt for analyzing a single anomaly."""
    template = _PROMPT_PATH.read_text()
    entity = anomaly["entity"]

    # Build entity description
    parts = [entity["type"]]
    for k, v in entity.items():
        if k != "type":
            parts.append(f"{k}={v}")
    entity_desc = ", ".join(parts)

    return (template
            .replace("{{detection_type}}", anomaly["detection_type"])
            .replace("{{entity_description}}", entity_desc)
            .replace("{{raw_stats}}", json.dumps(anomaly.get("raw_stats", {}), indent=2))
            .replace("{{data_domain}}", anomaly.get("data_domain", "")))


def _get_data_tools() -> list[dict]:
    """Load tool schemas, excluding UI-only tools."""
    tools = json.loads(_TOOLS_PATH.read_text())
    return [t for t in tools if t["name"] not in UI_TOOLS]


def analyze_insight(anomaly: dict) -> dict | None:
    """Run AI analysis on a single anomaly.

    Returns dict with 'explanation', 'revised_severity', 'push' or None on failure.
    """
    client = AnthropicBedrock(
        aws_region=config.LLM_AWS_REGION,
        aws_access_key=config.AWS_ACCESS_KEY_ID,
        aws_secret_key=config.AWS_SECRET_ACCESS_KEY,
        aws_session_token=config.AWS_SESSION_TOKEN,
    )

    system = _build_analysis_prompt(anomaly)
    tools = _get_data_tools()
    messages = [{"role": "user", "content": "Analyze this anomaly and provide your assessment."}]

    try:
        for iteration in range(config.LLM_MAX_ITERATIONS):
            model = config.LLM_MODEL_ID_HEAVY if iteration >= 2 else config.LLM_MODEL_ID
            log.info("Insight analysis iter %d for %s (%s)",
                     iteration, anomaly.get("fingerprint", "?"), model)

            response = client.messages.create(
                model=model,
                max_tokens=config.LLM_MAX_TOKENS,
                temperature=config.LLM_TEMPERATURE,
                system=system,
                tools=tools,
                messages=messages,
            )

            tool_uses = []
            text_content = ""

            for block in response.content:
                if block.type == "tool_use":
                    tool_uses.append(block)
                elif block.type == "text":
                    text_content += block.text

            if not tool_uses:
                # Parse the JSON response
                try:
                    # Extract JSON from possible markdown code block
                    text = text_content.strip()
                    if "```json" in text:
                        text = text.split("```json")[1].split("```")[0].strip()
                    elif "```" in text:
                        text = text.split("```")[1].split("```")[0].strip()
                    result = json.loads(text)
                    # Validate required fields
                    if all(k in result for k in ("explanation", "revised_severity", "push")):
                        return result
                    log.warning("AI response missing required fields: %s", result)
                    return None
                except (json.JSONDecodeError, IndexError) as e:
                    log.warning("Failed to parse AI response: %s — text: %s", e, text_content[:200])
                    return None

            # Execute tool calls
            tool_results = []
            for tool_block in tool_uses:
                name = tool_block.name
                if name in TOOL_DISPATCH:
                    params = {k: v for k, v in tool_block.input.items() if v is not None}
                    try:
                        result = TOOL_DISPATCH[name](params)
                        log.info("Insight tool %s returned %d chars", name, len(result))
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": tool_block.id,
                            "content": result,
                        })
                    except Exception as e:
                        log.error("Insight tool %s failed: %s", name, e)
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": tool_block.id,
                            "content": f"Error: {type(e).__name__}",
                            "is_error": True,
                        })
                else:
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tool_block.id,
                        "content": "Tool not available for insight analysis.",
                        "is_error": True,
                    })

            messages.append({"role": "assistant", "content": response.content})
            messages.append({"role": "user", "content": tool_results})

    except Exception as e:
        log.exception("AI analysis failed for anomaly: %s", anomaly.get("fingerprint", "?"))
        return None

    log.warning("AI analysis hit max iterations for %s", anomaly.get("fingerprint", "?"))
    return None
```

- [ ] **Step 3: Commit**

```bash
git add backend/insights/analyzer.py backend/assistant/prompts/insight_analysis.txt
git commit -m "feat(insights): add AI insight analyzer with Bedrock integration"
```

---

### Task 6: Trigger Script (Orchestrator)

**Files:**
- Create: `backend/insights/run.py`

- [ ] **Step 1: Implement trigger script**

Create `backend/insights/run.py`:

```python
"""Insight detection trigger script.

Usage: cd backend && python -m insights.run
"""

import json
import logging
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

# Ensure backend is on sys.path when run as module
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent.parent / ".env")

import data_loader
from insights.config import load_sensitivity_profile
from insights.detector import detect_outliers, detect_drift, detect_target_misses, detect_competitive_shifts
from insights.dedup import make_fingerprint, deduplicate
from insights.analyzer import analyze_insight
from insights.store import InsightStore

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

STORE_PATH = Path(__file__).parent.parent.parent / "data" / "insights.json"


def _make_insight(anomaly: dict, run_id: str, ai_result: dict | None, profile: dict) -> dict:
    """Build a full insight record from an anomaly and optional AI analysis."""
    now = datetime.now(timezone.utc).isoformat()
    fp = make_fingerprint(anomaly)

    if ai_result:
        severity = ai_result["revised_severity"]
        push = ai_result["push"]
    else:
        # Fallback: assign severity from statistical score
        score = anomaly.get("statistical_score", 0)
        if score >= profile["zscore_critical"]:
            severity = "critical"
        elif score >= profile["zscore_notable"]:
            severity = "notable"
        else:
            severity = "informational"
        push = False

    return {
        "id": f"ins_{uuid.uuid4().hex[:8]}",
        "fingerprint": fp,
        "detected_at": now,
        "last_seen": now,
        "run_id": run_id,
        "entity": anomaly["entity"],
        "detection_type": anomaly["detection_type"],
        "data_domain": anomaly.get("data_domain", ""),
        "statistical_score": anomaly.get("statistical_score", 0),
        "status": "active",
        "read": False,
        "push": push,
        "severity": severity,
        "ai_analysis": ai_result,
        "raw_stats": anomaly.get("raw_stats", {}),
    }


def run():
    run_id = f"run_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
    log.info("=== Insight detection run: %s ===", run_id)

    # Load data
    data_loader.load_all()
    profile = load_sensitivity_profile()
    threshold = profile["zscore_notable"]
    log.info("Profile: %s (threshold=%.1f)", profile, threshold)

    # Run all detectors
    all_anomalies = []

    # Revenue outliers & drift by brand+market
    rev = data_loader.revenue
    all_anomalies.extend(detect_outliers(
        rev, "revenue", "brand", ["brand_id", "market_id"], profile, "revenue"))
    all_anomalies.extend(detect_drift(
        rev, "revenue", "brand", ["brand_id", "market_id"], profile, "revenue"))

    # Revenue by TA (aggregate)
    rev_by_ta = rev.merge(data_loader.products[["brand_id", "therapeutic_area"]], on="brand_id")
    ta_monthly = rev_by_ta.groupby(["period_date", "therapeutic_area"]).agg(
        revenue=("revenue", "sum")).reset_index()
    ta_monthly.rename(columns={"therapeutic_area": "ta"}, inplace=True)
    all_anomalies.extend(detect_outliers(
        ta_monthly, "revenue", "ta", ["ta"], profile, "revenue"))
    all_anomalies.extend(detect_drift(
        ta_monthly, "revenue", "ta", ["ta"], profile, "revenue"))

    # Revenue total
    total_monthly = rev.groupby("period_date").agg(revenue=("revenue", "sum")).reset_index()
    total_monthly["_total"] = "total"
    all_anomalies.extend(detect_outliers(
        total_monthly, "revenue", "total", ["_total"], profile, "revenue"))
    all_anomalies.extend(detect_drift(
        total_monthly, "revenue", "total", ["_total"], profile, "revenue"))

    # Target misses (revenue vs budget)
    # Targets CSV uses entity_id, not brand_id — rename for merge compatibility
    tgt = data_loader.targets.rename(columns={"entity_id": "brand_id"})
    all_anomalies.extend(detect_target_misses(
        rev, tgt, "revenue", "budget_amount", "brand", ["brand_id", "market_id"], profile))

    # Expense outliers & drift by sub_unit
    # Expenses CSV uses sub_unit_id and total_operating_expenses columns
    exp = data_loader.expenses
    all_anomalies.extend(detect_outliers(
        exp, "total_operating_expenses", "sub_unit", ["sub_unit_id"], profile, "expenses"))
    all_anomalies.extend(detect_drift(
        exp, "total_operating_expenses", "sub_unit", ["sub_unit_id"], profile, "expenses"))

    # Expense by unit (aggregate) — join with organization to get unit column
    exp_with_unit = exp.merge(
        data_loader.organization[["sub_unit_id", "unit"]], on="sub_unit_id", how="left")
    unit_monthly = exp_with_unit.groupby(["period_date", "unit"]).agg(
        total_operating_expenses=("total_operating_expenses", "sum")).reset_index()
    all_anomalies.extend(detect_outliers(
        unit_monthly, "total_operating_expenses", "unit", ["unit"], profile, "expenses"))
    all_anomalies.extend(detect_drift(
        unit_monthly, "total_operating_expenses", "unit", ["unit"], profile, "expenses"))

    # Competitive shifts
    all_anomalies.extend(detect_competitive_shifts(data_loader.commercial, profile))

    log.info("Detected %d raw anomalies", len(all_anomalies))

    # Dedup against existing insights
    store = InsightStore(STORE_PATH)
    existing = store.load_all()
    new_anomalies, escalated, seen_fps = deduplicate(all_anomalies, existing)

    log.info("After dedup: %d new, %d escalated", len(new_anomalies), len(escalated))

    # Separate above/below threshold
    above = [a for a in new_anomalies if a.get("statistical_score", 0) >= threshold]
    below = [a for a in new_anomalies if a.get("statistical_score", 0) < threshold]

    log.info("Above threshold (will analyze): %d, Below (informational): %d", len(above), len(below))

    # AI analysis for above-threshold anomalies
    new_insights = []
    for anomaly in above:
        log.info("Analyzing: %s", make_fingerprint(anomaly))
        ai_result = analyze_insight(anomaly)
        new_insights.append(_make_insight(anomaly, run_id, ai_result, profile))

    # Below threshold: store as informational without AI
    for anomaly in below:
        new_insights.append(_make_insight(anomaly, run_id, None, profile))

    # Re-analyze escalated insights
    for ins in escalated:
        log.info("Re-analyzing escalated: %s", ins["fingerprint"])
        ai_result = analyze_insight(ins)
        if ai_result:
            ins["ai_analysis"] = ai_result
            ins["severity"] = ai_result["revised_severity"]
            ins["push"] = ai_result["push"]

    # Transition inactive
    inactive_count = 0
    for ins in existing:
        if ins["status"] == "active" and ins["fingerprint"] not in seen_fps:
            ins["status"] = "inactive"
            inactive_count += 1

    # Merge and save
    all_insights = existing + new_insights
    store.save_all(all_insights)

    log.info("=== Run complete: %d new, %d escalated, %d inactive ===",
             len(new_insights), len(escalated), inactive_count)

    return {
        "run_id": run_id,
        "detected": len(all_anomalies),
        "new": len(new_insights),
        "escalated": len(escalated),
        "inactive": inactive_count,
    }


if __name__ == "__main__":
    run()
```

- [ ] **Step 2: Run a smoke test manually**

Run: `cd backend && python -m insights.run`
Expected: Logs showing detection counts. `data/insights.json` created with insights.

- [ ] **Step 3: Commit**

```bash
git add backend/insights/run.py
git commit -m "feat(insights): add trigger script orchestrating full detection pipeline"
```

---

### Task 7: API Route for Insights

**Files:**
- Create: `backend/routes/insights_route.py`
- Modify: `backend/main.py` — mount router, update CORS headers
- Modify: `backend/models.py` — add Pydantic models for insights API

- [ ] **Step 1: Add Pydantic models for insights**

Add to the end of `backend/models.py`:

```python
class InsightEntity(BaseModel):
    type: str
    brand_id: str | None = None
    market_id: str | None = None
    ta: str | None = None
    unit: str | None = None
    sub_unit: str | None = None


class InsightResponse(BaseModel):
    id: str
    fingerprint: str
    detected_at: str
    last_seen: str
    run_id: str
    entity: InsightEntity
    detection_type: str
    data_domain: str
    statistical_score: float
    status: str
    read: bool
    push: bool
    severity: str
    ai_analysis: dict | None = None
    raw_stats: dict = {}


class InsightsListResponse(BaseModel):
    insights: list[InsightResponse]
    unread_count: int
    unread_critical_count: int
```

- [ ] **Step 2: Implement insights route**

Create `backend/routes/insights_route.py`:

```python
"""API endpoints for insights and push subscriptions."""

import json
import logging
from pathlib import Path

from fastapi import APIRouter, Header, Query

from models import InsightsListResponse
from insights.store import InsightStore
from insights.scoping import filter_by_role_scope
from assistant.prompt_builder import load_role

log = logging.getLogger(__name__)

router = APIRouter()

_STORE_PATH = Path(__file__).parent.parent.parent / "data" / "insights.json"
_SUBS_PATH = Path(__file__).parent.parent.parent / "data" / "push_subscriptions.json"
_DEFAULT_USER_ID = "demo_analyst"
_DEFAULT_ROLE = "default"

# User-to-role mapping for mock auth
_USER_ROLES = {
    "demo_analyst": "default",
    "demo_cfo": "cfo",
    "demo_commercial": "commercial",
    "demo_market_lead": "market_lead",
}


def _resolve_user(x_user_id: str | None) -> tuple[str, str]:
    """Resolve user ID and role from header."""
    user_id = x_user_id or _DEFAULT_USER_ID
    role_id = _USER_ROLES.get(user_id, _DEFAULT_ROLE)
    return user_id, role_id


@router.get("/insights")
def list_insights(
    sort: str = Query("date", pattern="^(date|severity)$"),
    status: str = Query("active", pattern="^(active|inactive|all)$"),
    limit: int = Query(50, ge=1, le=200),
    x_user_id: str | None = Header(None, alias="X-User-Id"),
):
    user_id, role_id = _resolve_user(x_user_id)
    role = load_role(role_id)
    scope = role.get("insight_scope", {
        "revenue": ["brand", "ta", "total"],
        "expenses": ["sub_unit", "unit", "total"],
        "market": ["brand_market"],
    })

    store = InsightStore(_STORE_PATH)
    insights = store.load_all()

    # Filter by status
    if status != "all":
        insights = [i for i in insights if i.get("status") == status]

    # Filter by role scope
    insights = filter_by_role_scope(insights, scope)

    # Sort
    severity_order = {"critical": 0, "notable": 1, "informational": 2}
    if sort == "severity":
        insights.sort(key=lambda i: severity_order.get(i.get("severity", ""), 3))
    else:
        insights.sort(key=lambda i: i.get("detected_at", ""), reverse=True)

    # Count before limiting
    unread = [i for i in insights if not i.get("read")]
    unread_critical = [i for i in unread if i.get("severity") == "critical"]

    return InsightsListResponse(
        insights=insights[:limit],
        unread_count=len(unread),
        unread_critical_count=len(unread_critical),
    )


@router.post("/insights/{insight_id}/read")
def mark_read(insight_id: str):
    store = InsightStore(_STORE_PATH)
    found = store.mark_read(insight_id)
    return {"ok": found}


@router.post("/insights/{insight_id}/chat")
def insight_to_chat(insight_id: str):
    """Return insight as an AssistantContext-compatible object."""
    store = InsightStore(_STORE_PATH)
    insights = store.load_all()
    ins = next((i for i in insights if i["id"] == insight_id), None)
    if not ins:
        return {"error": "Insight not found"}

    return {
        "source": "insight",
        "page": "overview",
        "period": {"year": 2025, "quarter": None},
        "filters": {},
        "dataPoint": {
            "node_id": ins.get("entity", {}).get("brand_id") or ins.get("entity", {}).get("unit") or "",
            "node_name": ins.get("entity", {}).get("brand_id") or ins.get("entity", {}).get("ta") or "",
            "insight_id": ins["id"],
            "detection_type": ins["detection_type"],
            "severity": ins.get("severity", ""),
            "explanation": (ins.get("ai_analysis") or {}).get("explanation", ""),
            "raw_stats": ins.get("raw_stats", {}),
        },
    }


@router.post("/push/subscribe")
def push_subscribe(
    body: dict,
    x_user_id: str | None = Header(None, alias="X-User-Id"),
):
    user_id, role_id = _resolve_user(x_user_id)
    subs = _load_subs()

    # Remove existing subscription for this user
    subs = [s for s in subs if s["user_id"] != user_id]
    subs.append({
        "user_id": user_id,
        "role": role_id,
        "subscription": body.get("subscription", {}),
    })
    _save_subs(subs)
    return {"ok": True}


@router.post("/push/unsubscribe")
def push_unsubscribe(
    x_user_id: str | None = Header(None, alias="X-User-Id"),
):
    user_id, _ = _resolve_user(x_user_id)
    subs = _load_subs()
    subs = [s for s in subs if s["user_id"] != user_id]
    _save_subs(subs)
    return {"ok": True}


def _load_subs() -> list[dict]:
    if not _SUBS_PATH.exists():
        return []
    try:
        return json.loads(_SUBS_PATH.read_text())
    except (json.JSONDecodeError, FileNotFoundError):
        return []


def _save_subs(subs: list[dict]):
    _SUBS_PATH.parent.mkdir(parents=True, exist_ok=True)
    _SUBS_PATH.write_text(json.dumps(subs, indent=2))
```

- [ ] **Step 3: Update `backend/main.py`**

Add `X-User-Id` to CORS headers and mount the insights router.

At line 15, add to the imports:
```python
from routes import kpi, brand, region, unit, chart, market, assistant, config_route, export, landing, phased, tree_generic, insights_route
```

At line 39, update CORS:
```python
allow_headers=["Content-Type", "X-User-Id"],
```

After line 53, add:
```python
app.include_router(insights_route.router, prefix="/api")
```

- [ ] **Step 4: Run the backend and test the endpoint**

Run: `cd backend && python -m uvicorn main:app --port 8000`
Then: `curl http://localhost:8000/api/insights`
Expected: `{"insights":[],"unread_count":0,"unread_critical_count":0}`

- [ ] **Step 5: Commit**

```bash
git add backend/routes/insights_route.py backend/models.py backend/main.py
git commit -m "feat(insights): add API route with role-scoped filtering and mock auth"
```

---

### Task 8: Web Push Delivery and Config Updates

**Files:**
- Create: `backend/insights/pusher.py`
- Modify: `backend/requirements.txt` — add `pywebpush`
- Modify: `backend/config.py` — add VAPID config
- Modify: `.env.example` — add VAPID and sensitivity vars
- Modify: `QUICKSTART.md` — add trigger script instructions

- [ ] **Step 1: Add VAPID config to `backend/config.py`**

Add after line 22 (after `PORT`):

```python
# Push Notifications (VAPID)
VAPID_PUBLIC_KEY = _optional("VAPID_PUBLIC_KEY")
VAPID_PRIVATE_KEY = _optional("VAPID_PRIVATE_KEY")
VAPID_CLAIMS_EMAIL = os.getenv("VAPID_CLAIMS_EMAIL", "admin@example.com")

# Insights
INSIGHT_SENSITIVITY = _optional("INSIGHT_SENSITIVITY")
```

- [ ] **Step 2: Add `pywebpush` to requirements**

Add to `backend/requirements.txt`:

```
pywebpush>=2.0,<3.0
```

- [ ] **Step 3: Implement push delivery**

Create `backend/insights/pusher.py`:

```python
"""Web Push notification delivery."""

import json
import logging
from pathlib import Path

import config

log = logging.getLogger(__name__)

_SUBS_PATH = Path(__file__).parent.parent.parent / "data" / "push_subscriptions.json"


def _load_subs() -> list[dict]:
    if not _SUBS_PATH.exists():
        return []
    try:
        return json.loads(_SUBS_PATH.read_text())
    except (json.JSONDecodeError, FileNotFoundError):
        return []


def send_push_for_insights(insights: list[dict], role_scopes: dict[str, dict]) -> int:
    """Send push notifications for push-eligible insights.

    Args:
        insights: list of insight dicts with push=True
        role_scopes: mapping of role_id -> insight_scope config

    Returns: number of notifications sent
    """
    if not config.VAPID_PRIVATE_KEY:
        log.warning("VAPID_PRIVATE_KEY not set — skipping push notifications")
        return 0

    try:
        from pywebpush import webpush, WebPushException
    except ImportError:
        log.warning("pywebpush not installed — skipping push notifications")
        return 0

    subs = _load_subs()
    if not subs:
        log.info("No push subscriptions registered")
        return 0

    from insights.scoping import filter_by_role_scope

    vapid_claims = {"sub": f"mailto:{config.VAPID_CLAIMS_EMAIL}"}
    sent = 0

    for sub in subs:
        role_id = sub.get("role", "default")
        scope = role_scopes.get(role_id, {})

        # Filter insights this user should see
        visible = filter_by_role_scope(insights, scope)
        push_eligible = [i for i in visible if i.get("push")]

        for insight in push_eligible:
            payload = json.dumps({
                "title": "Jarvis Insight",
                "body": insight.get("ai_analysis", {}).get("explanation", "New insight detected")[:200],
                "severity": insight.get("severity", "notable"),
                "insight_id": insight["id"],
            })

            try:
                webpush(
                    subscription_info=sub["subscription"],
                    data=payload,
                    vapid_private_key=config.VAPID_PRIVATE_KEY,
                    vapid_claims=vapid_claims,
                )
                sent += 1
                log.info("Push sent to %s for insight %s", sub["user_id"], insight["id"])
            except WebPushException as e:
                log.error("Push failed for %s: %s", sub["user_id"], e)
            except Exception as e:
                log.error("Unexpected push error for %s: %s", sub["user_id"], e)

    return sent
```

- [ ] **Step 4: Wire push delivery into trigger script**

Add to `backend/insights/run.py`, after the `store.save_all(all_insights)` line:

```python
    # Send push notifications for push-eligible new insights
    push_insights = [i for i in new_insights if i.get("push")]
    if push_insights:
        from insights.pusher import send_push_for_insights
        from assistant.prompt_builder import load_role

        # Build role scopes map
        role_scopes = {}
        for role_file in (Path(__file__).parent.parent / "assistant" / "roles").glob("*.json"):
            role = json.loads(role_file.read_text())
            role_scopes[role["id"]] = role.get("insight_scope", {})

        sent = send_push_for_insights(push_insights, role_scopes)
        log.info("Sent %d push notifications", sent)
```

- [ ] **Step 5: Update `.env.example`**

Add at the end:

```
# Push Insights
INSIGHT_SENSITIVITY=medium
VAPID_PUBLIC_KEY=
VAPID_PRIVATE_KEY=
VAPID_CLAIMS_EMAIL=admin@example.com
```

- [ ] **Step 6: Update `QUICKSTART.md`**

Add a "Push Insights" section before the "Both at once" section:

```markdown
## Push Insights

Run the insight detection engine to scan for anomalies:

```bash
cd backend
python -m insights.run
```

This analyzes all data for outliers, drift, target misses, and competitive shifts, then uses AI to explain significant anomalies. Results are stored in `data/insights.json`.

To reset insights, delete or empty `data/insights.json`.

Sensitivity can be adjusted via `INSIGHT_SENSITIVITY` env var (`high`, `medium`, `low`) or by editing `data/insights_config.json`.
```

- [ ] **Step 7: Commit**

```bash
git add backend/insights/pusher.py backend/config.py backend/requirements.txt backend/insights/run.py .env.example QUICKSTART.md
git commit -m "feat(insights): add web push delivery, VAPID config, and quickstart docs"
```

---

## Chunk 3: Frontend — Insights Panel, TopBar, and Push

### Task 9: TypeScript Types and useInsights Hook

**Files:**
- Modify: `frontend/src/types.ts` — add insight types and extend `AssistantContext`
- Create: `frontend/src/hooks/useInsights.ts`

- [ ] **Step 1: Add insight types to `types.ts`**

Add at the end of `frontend/src/types.ts`:

```typescript
// Push Insights
export interface InsightEntity {
  type: string;
  brand_id?: string;
  market_id?: string;
  ta?: string;
  unit?: string;
  sub_unit?: string;
}

export interface Insight {
  id: string;
  fingerprint: string;
  detected_at: string;
  last_seen: string;
  run_id: string;
  entity: InsightEntity;
  detection_type: string;
  data_domain: string;
  statistical_score: number;
  status: "active" | "inactive";
  read: boolean;
  push: boolean;
  severity: "critical" | "notable" | "informational";
  ai_analysis: { explanation: string; revised_severity: string; push: boolean } | null;
  raw_stats: Record<string, number | string>;
}

export interface InsightsListResponse {
  insights: Insight[];
  unread_count: number;
  unread_critical_count: number;
}
```

Extend the `AssistantContext.source` union (find the existing type and update):

```typescript
source: "tree_row" | "treemap_bar" | "time_chart_point" | "header" | "insight";
```

- [ ] **Step 2: Create `useInsights` hook**

Create `frontend/src/hooks/useInsights.ts`:

```typescript
import { useState, useEffect, useCallback, useRef } from "react";
import type { InsightsListResponse, Insight } from "../types";

const POLL_INTERVAL = 30_000; // 30 seconds

export function useInsights() {
  const [data, setData] = useState<InsightsListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetchInsights = useCallback(async () => {
    try {
      const resp = await fetch("/api/insights");
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const json: InsightsListResponse = await resp.json();
      setData(json);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load insights");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    let cancelled = false;

    const doFetch = async () => {
      if (cancelled) return;
      await fetchInsights();
    };

    doFetch();
    intervalRef.current = setInterval(doFetch, POLL_INTERVAL);

    return () => {
      cancelled = true;
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [fetchInsights]);

  const markRead = useCallback(async (id: string) => {
    await fetch(`/api/insights/${id}/read`, { method: "POST" });
    setData((prev) => {
      if (!prev) return prev;
      return {
        ...prev,
        insights: prev.insights.map((i) =>
          i.id === id ? { ...i, read: true } : i
        ),
        unread_count: Math.max(0, prev.unread_count - 1),
        unread_critical_count:
          prev.insights.find((i) => i.id === id)?.severity === "critical"
            ? Math.max(0, prev.unread_critical_count - 1)
            : prev.unread_critical_count,
      };
    });
  }, []);

  const getInsightContext = useCallback(async (id: string) => {
    const resp = await fetch(`/api/insights/${id}/chat`, { method: "POST" });
    return resp.json();
  }, []);

  return {
    insights: data?.insights ?? [],
    unreadCount: data?.unread_count ?? 0,
    unreadCriticalCount: data?.unread_critical_count ?? 0,
    loading,
    error,
    markRead,
    getInsightContext,
    refresh: fetchInsights,
  };
}
```

- [ ] **Step 3: Commit**

```bash
cd frontend && git add src/types.ts src/hooks/useInsights.ts
git commit -m "feat(insights): add insight types and useInsights polling hook"
```

---

### Task 10: InsightCard Component

**Files:**
- Create: `frontend/src/components/InsightCard.tsx`

- [ ] **Step 1: Implement InsightCard**

Create `frontend/src/components/InsightCard.tsx`:

```tsx
import clsx from "clsx";
import type { Insight } from "../types";

interface Props {
  insight: Insight;
  onAddToChat: (id: string) => void;
}

const SEVERITY_STYLES = {
  critical: { chip: "text-red-400 bg-red-400/15", border: "border-l-red-500" },
  notable: { chip: "text-amber-400 bg-amber-400/15", border: "border-l-amber-500" },
  informational: { chip: "text-white/40 bg-white/8", border: "border-l-white/20" },
};

function relativeTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

export function InsightCard({ insight, onAddToChat }: Props) {
  const isInactive = insight.status === "inactive";
  const hasAI = !!insight.ai_analysis;
  const styles = SEVERITY_STYLES[insight.severity] ?? SEVERITY_STYLES.informational;

  return (
    <div
      className={clsx(
        "rounded-[10px] p-3 border-l-[3px] transition-opacity",
        styles.border,
        isInactive ? "bg-white/[0.02] opacity-50" : insight.read ? "bg-white/[0.04] opacity-75" : "bg-white/[0.06]"
      )}
    >
      {/* Header row */}
      <div className="flex items-center gap-1.5 mb-1.5">
        {isInactive ? (
          <span className="text-[9px] font-bold text-white/40 bg-white/8 px-1.5 py-0.5 rounded uppercase">
            Inactive
          </span>
        ) : (
          <span className={clsx("text-[9px] font-bold px-1.5 py-0.5 rounded uppercase", styles.chip)}>
            {insight.severity}
          </span>
        )}
        <span className="text-[10px] text-white/30">{relativeTime(insight.detected_at)}</span>
        {!insight.read && !isInactive && (
          <div className="w-1.5 h-1.5 rounded-full bg-blue-400 ml-auto" title="Unread" />
        )}
      </div>

      {/* Title — build from entity + detection type */}
      <div className="text-[13px] font-medium text-white mb-1 leading-snug">
        {_buildTitle(insight)}
      </div>

      {/* Explanation */}
      <div className="text-[11px] text-white/50 leading-relaxed">
        {hasAI ? insight.ai_analysis!.explanation : "Statistical detection only — no AI analysis"}
      </div>

      {/* Actions */}
      <div className="flex gap-1.5 mt-2">
        <button
          onClick={() => onAddToChat(insight.id)}
          className="text-[10px] text-blue-400/80 hover:text-blue-400 transition-colors"
        >
          {hasAI ? "Add to chat →" : "Add to chat & analyze →"}
        </button>
      </div>
    </div>
  );
}

function _buildTitle(ins: Insight): string {
  const entity = ins.entity;
  const name = entity.brand_id || entity.ta || entity.unit || entity.sub_unit || "Total";
  const market = entity.market_id ? ` ${entity.market_id}` : "";
  const domain = ins.data_domain === "revenue" ? "revenue" : ins.data_domain === "expenses" ? "OpEx" : "market share";

  switch (ins.detection_type) {
    case "outlier": {
      const stats = ins.raw_stats;
      const dir = (stats.current_value as number) > (stats.mean as number) ? "above" : "below";
      return `${name}${market} ${domain} ${dir} average (z=${stats.zscore})`;
    }
    case "drift":
      return `${name}${market} ${domain} trending away from baseline`;
    case "target_miss":
      return `${name}${market} ${domain} ${((ins.raw_stats.miss_pct as number) * 100).toFixed(0)}% below target`;
    case "competitive_shift": {
      const delta = ins.raw_stats.delta_pct as number;
      const dir = delta > 0 ? "gained" : "lost";
      return `${name}${market} ${dir} ${Math.abs(delta).toFixed(1)}pp market share`;
    }
    default:
      return `${name}${market} anomaly detected`;
  }
}
```

- [ ] **Step 2: Commit**

```bash
cd frontend && git add src/components/InsightCard.tsx
git commit -m "feat(insights): add InsightCard component with severity chips and actions"
```

---

### Task 11: InsightsPanel Component

**Files:**
- Create: `frontend/src/components/InsightsPanel.tsx`

- [ ] **Step 1: Implement InsightsPanel**

Create `frontend/src/components/InsightsPanel.tsx`. Uses a bottom slide-up pattern (same as AssistantDrawer) with drag-to-dismiss, optimized for mobile-first design:

```tsx
import { useState } from "react";
import { motion, AnimatePresence, type PanInfo } from "framer-motion";
import type { Insight } from "../types";
import { InsightCard } from "./InsightCard";

interface Props {
  open: boolean;
  onClose: () => void;
  insights: Insight[];
  onAddToChat: (id: string) => void;
}

type SortBy = "date" | "severity";

const SEVERITY_ORDER: Record<string, number> = { critical: 0, notable: 1, informational: 2 };

export function InsightsPanel({ open, onClose, insights, onAddToChat }: Props) {
  const [sortBy, setSortBy] = useState<SortBy>("date");

  const sorted = [...insights].sort((a, b) => {
    if (sortBy === "severity") {
      return (SEVERITY_ORDER[a.severity] ?? 3) - (SEVERITY_ORDER[b.severity] ?? 3);
    }
    return new Date(b.detected_at).getTime() - new Date(a.detected_at).getTime();
  });

  const handleDragEnd = (_: unknown, info: PanInfo) => {
    if (info.offset.y > 100) onClose();
  };

  return (
    <AnimatePresence>
      {open && (
        <>
          {/* Backdrop */}
          <motion.div
            className="fixed inset-0 bg-black/60 z-40"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
          />

          {/* Panel */}
          <motion.div
            className="fixed inset-x-0 bottom-0 z-50 bg-[#0f1225] rounded-t-2xl max-h-[85vh] flex flex-col"
            initial={{ y: "100%" }}
            animate={{ y: 0 }}
            exit={{ y: "100%" }}
            transition={{ type: "spring", damping: 25, stiffness: 300 }}
            drag="y"
            dragConstraints={{ top: 0 }}
            dragElastic={0.2}
            onDragEnd={handleDragEnd}
          >
            {/* Drag handle */}
            <div className="flex justify-center pt-3 pb-2 cursor-grab active:cursor-grabbing">
              <div className="w-10 h-1 rounded-full bg-white/20" />
            </div>

            {/* Header */}
            <div className="flex items-center justify-between px-4 pb-3">
              <div className="flex items-center gap-2">
                <span className="text-[15px]">💡</span>
                <span className="text-white font-semibold text-[15px]">Push Insights</span>
              </div>
              <div className="flex gap-1.5">
                <button
                  onClick={() => setSortBy("date")}
                  className={`text-[11px] px-2 py-0.5 rounded-xl border transition-colors ${
                    sortBy === "date"
                      ? "border-white/30 text-white/70"
                      : "border-white/10 text-white/40 hover:border-white/20"
                  }`}
                >
                  Date ↓
                </button>
                <button
                  onClick={() => setSortBy("severity")}
                  className={`text-[11px] px-2 py-0.5 rounded-xl border transition-colors ${
                    sortBy === "severity"
                      ? "border-white/30 text-white/70"
                      : "border-white/10 text-white/40 hover:border-white/20"
                  }`}
                >
                  Severity
                </button>
              </div>
            </div>

            {/* Insight list */}
            <div className="flex-1 overflow-y-auto px-4 pb-6 space-y-2">
              {sorted.length === 0 ? (
                <div className="text-center text-white/30 text-sm py-12">
                  No insights detected yet
                </div>
              ) : (
                sorted.map((ins) => (
                  <InsightCard key={ins.id} insight={ins} onAddToChat={onAddToChat} />
                ))
              )}
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}
```

- [ ] **Step 2: Commit**

```bash
cd frontend && git add src/components/InsightsPanel.tsx
git commit -m "feat(insights): add InsightsPanel slide-up drawer with sort controls"
```

---

### Task 12: TopBar Lightbulb Icon and App Wiring

**Files:**
- Modify: `frontend/src/components/TopBar.tsx` — add lightbulb icon
- Modify: `frontend/src/App.tsx` — wire up insights panel + "Add to chat" flow

- [ ] **Step 1: Add lightbulb icon to TopBar**

In `frontend/src/components/TopBar.tsx`, add `onInsightsOpen` and `unreadInsightCount` / `hasUnreadCritical` to the Props interface:

```typescript
interface Props {
  onAssistantOpen?: () => void;
  onExport?: () => void;
  onInsightsOpen?: () => void;
  hasNotification?: boolean;
  unreadInsightCount?: number;
  hasUnreadCritical?: boolean;
}
```

Add the lightbulb button between the export button and the assistant button (after the export `</button>` closing tag, before the assistant `{onAssistantOpen &&` block):

```tsx
{onInsightsOpen && (
  <button
    onClick={onInsightsOpen}
    className={clsx(
      "relative w-8 h-8 rounded-lg flex items-center justify-center transition-colors",
      hasUnreadCritical
        ? "bg-amber-500/20 border border-amber-500/40 hover:bg-amber-500/30"
        : "bg-white/10 hover:bg-white/20"
    )}
    title="Push Insights"
  >
    <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor">
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={1.5}
        d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5.002 5.002 0 117.072 0l.46 2.298a1 1 0 01-.981 1.197h-6.078a1 1 0 01-.981-1.197l.46-2.298z"
        className={hasUnreadCritical ? "text-amber-400" : "text-white/70"}
      />
    </svg>
    {(unreadInsightCount ?? 0) > 0 && (
      <span className="absolute -top-0.5 -right-0.5 min-w-[16px] h-4 rounded-full bg-red-500 flex items-center justify-center border-2 border-az-navy">
        <span className="text-white text-[8px] font-bold">{unreadInsightCount}</span>
      </span>
    )}
  </button>
)}
```

Add `import clsx from "clsx";` to the top of `TopBar.tsx` (not currently imported).

Update the component destructuring:
```typescript
export function TopBar({ onAssistantOpen, onExport, onInsightsOpen, hasNotification, unreadInsightCount, hasUnreadCritical }: Props) {
```

- [ ] **Step 2: Wire up insights in App.tsx**

Add imports at the top of `frontend/src/App.tsx`:

```typescript
import { useInsights } from "./hooks/useInsights";
import { InsightsPanel } from "./components/InsightsPanel";
```

Add state and hook after the existing `assistantOpen` state:

```typescript
const [insightsOpen, setInsightsOpen] = useState(false);
const insights = useInsights();
```

Add the "Add to chat" handler after `handleAssistantOpen`:

```typescript
const handleInsightToChat = useCallback(async (insightId: string) => {
  // Mark as read
  await insights.markRead(insightId);
  // Get insight context for assistant
  const ctx = await insights.getInsightContext(insightId);
  // Close insights, open assistant with new thread seeded with context
  setInsightsOpen(false);
  const question = ctx.dataPoint?.explanation
    ? `Analyze this insight: ${ctx.dataPoint.explanation}`
    : "Analyze this data anomaly and provide recommendations.";
  assistant.newChat(ctx);  // pass context directly — newChat accepts optional context
  setAssistantOpen(true);
  // Send the initial question after a tick to ensure drawer is open
  setTimeout(() => assistant.sendQuestion(question), 100);
}, [insights, assistant]);
```

Update the `<TopBar>` component to pass new props:

```tsx
<TopBar
  onAssistantOpen={handleAssistantOpen}
  onExport={handleExport}
  onInsightsOpen={() => setInsightsOpen(true)}
  hasNotification={assistant.hasNotification}
  unreadInsightCount={insights.unreadCount}
  hasUnreadCritical={insights.unreadCriticalCount > 0}
/>
```

Add the `<InsightsPanel>` component after `<AssistantDrawer>`:

```tsx
<InsightsPanel
  open={insightsOpen}
  onClose={() => setInsightsOpen(false)}
  insights={insights.insights}
  onAddToChat={handleInsightToChat}
/>
```

- [ ] **Step 3: Run frontend build to check for type errors**

Run: `cd frontend && npm run build`
Expected: Build succeeds with no TypeScript errors

- [ ] **Step 4: Commit**

```bash
cd frontend && git add src/components/TopBar.tsx src/App.tsx
git commit -m "feat(insights): wire up TopBar lightbulb, InsightsPanel, and Add to Chat flow"
```

---

### Task 13: Service Worker for Push Notifications

**Files:**
- Create: `frontend/public/sw.js`

- [ ] **Step 1: Create the Service Worker**

Create `frontend/public/sw.js`:

```javascript
/* Service Worker for Jarvis Push Insights */

self.addEventListener("push", (event) => {
  let data = { title: "Jarvis Insight", body: "New insight detected" };
  try {
    data = event.data.json();
  } catch (e) {
    // fallback to defaults
  }

  const options = {
    body: data.body,
    icon: "/favicon.ico",
    badge: "/favicon.ico",
    tag: data.insight_id || "jarvis-insight",
    data: { insightId: data.insight_id },
    actions: [{ action: "view", title: "View" }],
  };

  event.waitUntil(self.registration.showNotification(data.title, options));
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  event.waitUntil(
    clients.matchAll({ type: "window" }).then((windowClients) => {
      // Focus existing tab or open new one
      for (const client of windowClients) {
        if (client.url.includes(self.location.origin) && "focus" in client) {
          client.focus();
          client.postMessage({ type: "open-insights", insightId: event.notification.data?.insightId });
          return;
        }
      }
      return clients.openWindow("/?insights=open");
    })
  );
});
```

- [ ] **Step 2: Add push subscription logic to `useInsights.ts`**

Add to the end of the `useInsights` hook, before the return statement:

```typescript
const subscribeToPush = useCallback(async () => {
  if (!("serviceWorker" in navigator) || !("PushManager" in window)) return;

  try {
    const reg = await navigator.serviceWorker.register("/sw.js");
    const permission = await Notification.requestPermission();
    if (permission !== "granted") return;

    // Get VAPID public key from backend config
    const configResp = await fetch("/api/config");
    const config = await configResp.json();
    if (!config.vapid_public_key) return;

    const subscription = await reg.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: config.vapid_public_key,
    });

    await fetch("/api/push/subscribe", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ subscription: subscription.toJSON() }),
    });
  } catch (e) {
    console.warn("Push subscription failed:", e);
  }
}, []);
```

Add `subscribeToPush` to the return object:

```typescript
return {
  insights: data?.insights ?? [],
  unreadCount: data?.unread_count ?? 0,
  unreadCriticalCount: data?.unread_critical_count ?? 0,
  loading,
  error,
  markRead,
  getInsightContext,
  refresh: fetchInsights,
  subscribeToPush,
};
```

- [ ] **Step 3: Add VAPID public key to config endpoint**

In `backend/routes/config_route.py`, add `import config as app_config` at the top, then in the `get_config` function, add `cfg["vapid_public_key"] = app_config.VAPID_PUBLIC_KEY` after the existing `cfg["data_refreshed_at"]` line and before the return statement.

- [ ] **Step 4: Commit**

```bash
git add frontend/public/sw.js frontend/src/hooks/useInsights.ts backend/routes/config_route.py
git commit -m "feat(insights): add Service Worker, push subscription, and VAPID config endpoint"
```

---

### Task 14: Add generated files to `.gitignore`

**Files:**
- Modify: `.gitignore`

- [ ] **Step 1: Add generated insight files to `.gitignore`**

Add to `.gitignore`:

```
# Insights (generated)
data/insights.json
data/push_subscriptions.json
```

- [ ] **Step 2: Commit**

```bash
git add .gitignore
git commit -m "chore: ignore generated insight data files"
```

---

### Task 15: Final Integration Smoke Test

- [ ] **Step 1: Run backend**

Run: `cd backend && pip install -r requirements.txt && python -m uvicorn main:app --reload --port 8000`

- [ ] **Step 2: Run insight detection**

In another terminal: `cd backend && python -m insights.run`
Expected: Logs showing detected anomalies, AI analysis calls, and summary.

- [ ] **Step 3: Verify API**

Run: `curl http://localhost:8000/api/insights`
Expected: JSON with insights array populated.

- [ ] **Step 4: Run frontend**

Run: `cd frontend && npm run dev`
Open `http://localhost:5173`
Expected: Lightbulb icon visible in TopBar with unread badge. Clicking opens InsightsPanel with insight cards.

- [ ] **Step 5: Test "Add to chat"**

Click "Add to chat →" on an insight card.
Expected: Insights panel closes, assistant drawer opens with a new thread seeded with the insight context.

- [ ] **Step 6: Run all tests**

Run: `cd frontend && npm test`
Run: `cd backend && python -m pytest ../tests/test_insights_*.py -v`
Expected: All tests pass.

- [ ] **Step 7: Final commit**

```bash
git add -A
git commit -m "feat(insights): complete push insights integration"
```
