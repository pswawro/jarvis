# Insight Bookmarks — Design Spec

Pin important insights for quick-access monitoring via a per-user bookmark system.

## Overview

Users can bookmark individual insights to keep them easily accessible. Bookmarked insights display a filled star icon and can be filtered to show only bookmarks. Bookmark state is per-user, stored server-side in a general-purpose user preferences file.

## Storage

File: `data/user_preferences.json` — extensible per-user preferences, starting with insight bookmarks.

```json
{
  "demo_cfo": {
    "insight_bookmarks": ["ins_a1b2c3d4", "ins_e5f6g7h8"]
  },
  "demo_analyst": {
    "insight_bookmarks": []
  }
}
```

All writes use atomic file replacement (write to temp file, then `os.replace`) consistent with other JSON stores in the project.

### UserPreferencesStore

New module: `backend/user_preferences.py`

Methods:
- `get_bookmarks(user_id: str) -> list[str]` — returns list of bookmarked insight IDs
- `add_bookmark(user_id: str, insight_id: str)` — adds insight ID to user's bookmarks (idempotent)
- `remove_bookmark(user_id: str, insight_id: str)` — removes insight ID from user's bookmarks (idempotent)

The store lazily initializes user entries — if a user_id has no entry, it returns empty defaults.

## API Endpoints

Two new endpoints on the existing insights router (`backend/routes/insights_route.py`):

### `POST /api/insights/{id}/bookmark`

Adds insight ID to the requesting user's bookmarks. Idempotent — bookmarking an already-bookmarked insight is a no-op. Returns `{"ok": true}`. Resolves user from `X-User-Id` header (same pattern as `push_subscribe`).

### `POST /api/insights/{id}/unbookmark`

Removes insight ID from the requesting user's bookmarks. Idempotent. Returns `{"ok": true}`. Resolves user from `X-User-Id` header.

### Changes to Existing Endpoints

**`GET /api/insights`** — Each insight in the response gains a `bookmarked: boolean` field. The handler loads the user's bookmark list from `UserPreferencesStore`, then injects `bookmarked: id in bookmarks` into each raw insight dict before passing to `InsightsListResponse`. This must happen before Pydantic serialization since the insights are raw dicts from `InsightStore`.

**`GET /api/insights/stream` (SSE)** — Same injection: load user bookmarks, merge `bookmarked` into each raw dict before `json.dumps`. The SSE generator must also watch `user_preferences.json` mtime (in addition to `insights.json`) so bookmark changes are pushed to the client.

## Frontend

### Types (`frontend/src/types.ts`)

Add `bookmarked: boolean` to the `Insight` interface.

### InsightCard (`frontend/src/components/InsightCard.tsx`)

- Add a star icon button to each card's header row (between the severity chip and timestamp).
- Outline star when not bookmarked, filled star when bookmarked.
- Click toggles bookmark state via API call.
- Optimistic local update: toggle immediately, silently revert on API failure (consistent with `markRead` error handling).
- New prop: `onToggleBookmark: (id: string) => void`.

### InsightsPanel (`frontend/src/components/InsightsPanel.tsx`)

- New prop: `onToggleBookmark: (id: string) => void` — passed through to each `InsightCard`.
- Add a bookmark filter toggle button in the header, alongside the existing "Date" and "Severity" sort buttons.
- Star icon button — when active (highlighted border), only bookmarked insights are shown.
- Default: off (all insights shown).
- Filter is applied before sorting.
- When filter is active and no insights are bookmarked, show "No bookmarked insights" (distinct from the "No insights detected yet" empty state).

### useInsights Hook (`frontend/src/hooks/useInsights.ts`)

- Add `toggleBookmark(id: string)` function.
- Calls `POST /api/insights/{id}/bookmark` or `/unbookmark` based on current `bookmarked` state.
- Optimistic update: toggles `bookmarked` field locally. SSE will confirm on next push.

### App.tsx (`frontend/src/App.tsx`)

- Pass `insights.toggleBookmark` to `InsightsPanel` as `onToggleBookmark` prop.

## Backend Model

Add `bookmarked: bool = False` to `InsightResponse` in `backend/models.py`.

## Data Flow

1. User clicks star on InsightCard
2. `useInsights.toggleBookmark(id)` fires
3. Optimistic local state update (toggle `bookmarked`)
4. API call to bookmark/unbookmark endpoint
5. Backend updates `user_preferences.json` atomically
6. SSE detects `user_preferences.json` mtime change and pushes updated state

## File Structure

```
backend/
  user_preferences.py         # UserPreferencesStore (new)
  routes/
    insights_route.py          # +bookmark/unbookmark endpoints, +bookmarked field in responses

data/
  user_preferences.json        # Per-user preferences (generated)

frontend/src/
  types.ts                     # +bookmarked field on Insight
  hooks/useInsights.ts         # +toggleBookmark
  components/
    InsightCard.tsx             # +star icon + onToggleBookmark prop
    InsightsPanel.tsx           # +bookmark filter toggle + onToggleBookmark prop
    App.tsx                     # +pass toggleBookmark to InsightsPanel
```

## Required Changes to Existing Files

- `backend/routes/insights_route.py` — Add bookmark/unbookmark endpoints, inject `bookmarked` into raw insight dicts in both `list_insights` and SSE stream, watch `user_preferences.json` mtime in SSE generator
- `backend/models.py` — Add `bookmarked: bool` to `InsightResponse`
- `frontend/src/types.ts` — Add `bookmarked: boolean` to `Insight`
- `frontend/src/hooks/useInsights.ts` — Add `toggleBookmark`
- `frontend/src/components/InsightCard.tsx` — Add star icon + `onToggleBookmark` prop
- `frontend/src/components/InsightsPanel.tsx` — Add bookmark filter toggle, add `onToggleBookmark` prop, pass to cards
- `frontend/src/App.tsx` — Pass `insights.toggleBookmark` to `InsightsPanel`
- `.gitignore` — Add `data/user_preferences.json`
