# Push Insights — Design Spec

Proactive analytics for Jarvis: detect data anomalies, explain them with AI, and push critical findings to users.

## Overview

Instead of waiting for users to ask questions, Jarvis periodically scans financial, commercial, and operational data for anomalies, runs AI analysis to explain them, and surfaces findings in a dedicated insights panel. Critical insights trigger Web Push notifications.

## Pipeline

```
trigger script → load data → detect anomalies → fingerprint & dedup → threshold check → AI analyze (above threshold) → AI assigns severity + push flag → store → push notifications (push=true)
```

The trigger script runs on demand (`python -m backend.insights.run`). The architecture supports periodic scheduling but the prototype uses manual triggering. A reset is done by emptying `data/insights.json`.

## Detection Engine

Module: `backend/insights/`

Four detection methods, all pure Pandas (no scipy):

1. **Point outliers** — Z-score against the series mean/std. Catches single-month spikes or drops.
2. **Drift** — Current value vs 3-month rolling mean/std. Catches gradual shifts that aren't dramatic in any single month but represent a changing trend.
3. **Target variance** — Actual vs budget/MTP/RBU2 percentage miss beyond threshold. Reuses variance calculation logic from `routes/shared.py`.
4. **Competitive shifts** — Month-over-month change in `az_market_share_pct` and `market_growth_pct` from `commercial_market.csv`.

Detection runs across all entities at all hierarchy levels (leaf through total). Role-based filtering happens at read time, not detection time.

### Sensitivity Profiles

Stored in `data/insights_config.json`:

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

Active profile selectable via `INSIGHT_SENSITIVITY` env var, falling back to the `active_profile` field in the JSON. Rolling window is fixed at 3 months. All threshold values are configurable in the JSON without code changes.

### Threshold

A single threshold divides anomalies into two groups:
- **Above threshold** — sent for AI analysis
- **Below threshold** — stored as-is with `severity: informational`, no AI analysis, `push: false`

The threshold is derived from the sensitivity profile (the `zscore_notable` value serves as the cutoff for statistical score).

## AI Analysis

Above-threshold anomalies are sent to Bedrock using the same client, tools, and tool dispatch infrastructure as the existing assistant. The prompt is curated for insight analysis rather than conversational Q&A.

AI returns for each anomaly:
- **explanation** — narrative describing the anomaly and its likely cause
- **severity** — `critical`, `notable`, or `informational` (AI can raise or lower the statistical assessment based on contextual evidence)
- **push** — boolean, whether this warrants a push notification

The AI prompt instructs Claude:
- Use available tools to investigate context (related metrics, trends, market conditions)
- Assign severity based on business impact, not just statistical magnitude
- May raise severity if contextual evidence suggests a worsening situation (e.g., market share trend reinforcing revenue decline)
- May lower severity if the anomaly has a benign explanation (e.g., seasonal pattern, known business cycle)
- Set `push: true` only for genuinely urgent findings requiring immediate attention

## Deduplication

Each anomaly gets a fingerprint hash based on: entity identifier + metric + detection type (e.g., `brand_Tagrisso_US_revenue_outlier`).

Before storing a new insight:
1. Check if an active insight with the same fingerprint exists
2. If match found: update `last_seen` timestamp, suppress duplicate
3. If severity worsened: update the insight, re-flag as unread, re-trigger AI analysis
4. If no match: create new insight

### Inactive Transition

After each detection run, any active insight whose fingerprint was NOT detected in the current run is automatically transitioned to `inactive` status. This handles anomalies that resolve themselves.

## Storage

File: `data/insights.json` — flat JSON array, readable and clearable.

### Insight Schema

```json
{
  "id": "ins_001",
  "fingerprint": "brand_Tagrisso_US_revenue_outlier",
  "detected_at": "2026-03-13T10:00:00Z",
  "last_seen": "2026-03-13T10:00:00Z",
  "run_id": "run_20260313_100000",
  "entity": {
    "type": "brand",
    "brand_id": "TAGRISSO",
    "market_id": "US"
  },
  "detection_type": "outlier",
  "statistical_score": 3.2,
  "status": "active",
  "read": false,
  "push": true,
  "severity": "critical",
  "ai_analysis": {
    "explanation": "Tagrisso US revenue dropped 18% below the rolling 3-month average...",
    "revised_severity": "critical",
    "push": true
  },
  "raw_stats": {
    "current_value": 280.5,
    "rolling_mean": 342.1,
    "rolling_std": 19.2,
    "zscore": 3.2
  }
}
```

### Push Subscriptions

File: `data/push_subscriptions.json` — array of subscription objects keyed by user ID:

```json
[
  {
    "user_id": "demo_cfo",
    "role": "cfo",
    "subscription": {
      "endpoint": "https://fcm.googleapis.com/fcm/send/...",
      "keys": { "p256dh": "...", "auth": "..." }
    }
  }
]
```

## API Endpoints

### `GET /api/insights`

Returns insights filtered by the requesting user's role scope. Supports query params:
- `sort=date|severity` (default: date descending)
- `status=active|inactive|all` (default: active)

### `PATCH /api/insights/{id}/read`

Marks an insight as read. Body: `{ "read": true }`.

### `POST /api/insights/{id}/chat`

Returns the insight formatted as an assistant conversation starter context. Used by the frontend to seed a new chat thread. Response includes the insight summary, raw stats, and AI analysis (if available) formatted for the assistant system prompt.

### `POST /api/push/subscribe`

Registers a push subscription for the authenticated user. Body: `{ "subscription": { "endpoint": "...", "keys": {...} } }`.

### `POST /api/push/unsubscribe`

Removes push subscription for the authenticated user.

## Authentication

### Architecture

All endpoints receive an authenticated user context with `user_id` and `role`. Role determines insight visibility via `insight_scope` in role config. Push subscriptions are keyed by user ID.

### Mock Implementation (Hackathon)

A middleware reads `X-User-Id` header (defaults to a configured demo user). Role resolved from user-to-role mapping in config. Designed for Entra ID swap: replace the middleware with MSAL token validation, everything downstream stays the same.

### Entra ID Integration Path

When ready: add MSAL.js on frontend for login flow, add token validation middleware on backend extracting user ID and role from Entra ID claims/groups. No changes needed to insight engine, storage, API contracts, or push infrastructure.

## Role Scoping

Each role config (`backend/assistant/roles/*.json`) gains an `insight_scope` field:

```json
{
  "role": "cfo",
  "insight_scope": {
    "revenue": ["total", "ta"],
    "expenses": ["total", "unit"],
    "market": ["brand_market"]
  }
}
```

Detection runs on all levels. `GET /api/insights` filters by the requesting user's role scope. Configurable per role without code changes.

## Frontend

### TopBar

Lightbulb icon placed between Export and Assistant icons. Badge shows unread insight count. Amber border/glow when unread critical insights exist.

### Insights Panel

Slides in from right (same pattern as AssistantDrawer). Independent surface from the assistant.

Contents:
- Sort controls: by date (default descending) or severity
- Insight cards with:
  - **Severity chip**: Critical (red), Notable (amber), Info (gray)
  - **Inactive chip**: Replaces severity chip when anomaly resolved
  - **Timestamp**: relative (e.g., "2h ago")
  - **Unread dot**: blue, disappears on read
  - **Title**: concise anomaly description
  - **AI explanation**: narrative from AI analysis (or "Statistical detection only" for informational)
  - **"Add to chat →"** action (analyzed insights)
  - **"Add to chat & analyze →"** action (informational insights, triggers on-demand analysis)

### Visual States

- **Unread + Active**: Full brightness, blue dot, severity chip
- **Read + Active**: Dimmed, no blue dot, severity chip
- **Inactive**: Clearly dimmed, "Inactive" chip

### "Add to Chat" Flow

1. Close insights panel
2. Open assistant drawer
3. Start a new conversation thread seeded with the insight context
4. For informational insights, this also triggers on-demand AI analysis
5. User can ask follow-up questions immediately

### Push Notifications

- Service Worker (`frontend/public/sw.js`) handles push events
- Shows native browser notification for `push: true` insights
- Requests notification permission on first push-eligible insight
- Notification click opens Jarvis and navigates to insights panel
- VAPID public key provided to frontend for subscription registration

## Web Push Infrastructure

- **Library**: `pywebpush` added to `backend/requirements.txt`
- **VAPID keys**: Generated once at setup, stored in `.env` (`VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY`, `VAPID_CLAIMS_EMAIL`)
- **Delivery**: Trigger script, after storing insights, sends Web Push to eligible users based on role scope for each `push: true` insight

## Trigger Script

Entry point: `python -m backend.insights.run`

Behavior:
1. Loads data via `data_loader.py`
2. Loads sensitivity profile from `data/insights_config.json`
3. Runs all 4 detection methods across all entities and hierarchy levels
4. Deduplicates against existing `data/insights.json`
5. Sends above-threshold anomalies to Bedrock for AI analysis
6. Stores results in `data/insights.json`
7. Transitions unmatched active insights to inactive
8. Sends Web Push for `push: true` insights
9. Logs summary to stdout: X detected, Y new, Z escalated, W inactive

Reset: delete or empty `data/insights.json`.

Instructions added to QUICKSTART.md.

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `INSIGHT_SENSITIVITY` | *(from JSON)* | Active sensitivity profile: `high`, `medium`, or `low` |
| `VAPID_PUBLIC_KEY` | — | Web Push VAPID public key |
| `VAPID_PRIVATE_KEY` | — | Web Push VAPID private key |
| `VAPID_CLAIMS_EMAIL` | — | Contact email for VAPID claims |

## Dependencies

**Backend** (added to `requirements.txt`):
- `pywebpush` — Web Push notification delivery

**Frontend** (no new npm packages):
- Service Worker API (browser native)
- Push API (browser native)
- Notification API (browser native)

## File Structure

```
backend/
  insights/
    __init__.py
    run.py              # Trigger script entry point
    detector.py         # Statistical detection methods
    dedup.py            # Fingerprinting and deduplication
    analyzer.py         # AI analysis via Bedrock
    pusher.py           # Web Push delivery
    config.py           # Sensitivity profile loader

data/
  insights.json         # Insight store (generated)
  insights_config.json  # Sensitivity profiles
  push_subscriptions.json  # Push subscription store (generated)

backend/routes/
  insights_route.py     # API endpoints for insights + push

frontend/src/
  components/
    InsightsPanel.tsx    # Slide-out insights panel
    InsightCard.tsx      # Individual insight card
  hooks/
    useInsights.ts       # Fetch + polling for insights
  public/
    sw.js               # Service Worker for push
```
