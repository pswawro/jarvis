# Jarvis Test Results

**Date:** 2026-03-08
**Environment:** macOS, Chrome, Node 22, Vite dev server (localhost:5173 + backend :8000)

---

## Unit Tests (Vitest)

**Run command:** `npm test` (from `frontend/`)
**Framework:** Vitest 4.0.18 + React Testing Library + jsdom
**Result: 42/42 PASSED**

### Test Files

| File | Tests | Status |
|------|-------|--------|
| `src/test/utils.test.ts` | 20 | PASSED |
| `src/test/useBookmarks.test.ts` | 8 | PASSED |
| `src/test/useLongPress.test.ts` | 6 | PASSED |
| `src/test/useSavedDimensions.test.ts` | 8 | PASSED |

### Test Breakdown

#### `utils.test.ts` — Pure utility functions (20 tests)

**filtersToExtra (5 tests)**
- Returns only comparator when all filter arrays are empty
- Includes `market_id` when markets are selected
- Includes `ta` when TAs are selected
- Maps `product` filter to `brand_id` key (key rename)
- Includes all filters when everything is set

**scaleValue (6 tests)**
- Formats millions with 1 decimal place
- Formats billions with 2 decimal places
- Formats thousands as rounded integers with locale separators
- Handles zero correctly across all scales
- Handles negative values
- Falls back to divisor 1 for unknown scale

**scaleLabel (4 tests)**
- Returns `$M` for M, `$K` for K, `$B` for B
- Defaults to `$B` for unknown input

**comparatorLabel (5 tests)**
- Maps BUD → "vs Bgt", MTP → "vs MTP", RBU2 → "vs RBU2", PYACT → "vs PY"
- Defaults to "vs Bgt" for unknown comparator

#### `useBookmarks.test.ts` — Bookmark CRUD + localStorage (8 tests)

- Starts with empty list when localStorage is empty
- Adds a bookmark with correct label
- Persists bookmarks to localStorage
- Loads bookmarks from localStorage on init
- Prepends new bookmarks (most recent first)
- Caps bookmarks at 20 max
- Removes a bookmark by ID
- Handles corrupt localStorage gracefully (returns [])

#### `useLongPress.test.ts` — Touch gesture handling (6 tests)

- Calls callback after configured delay
- Sets `didLongPress` to true after long press fires
- Cancels on touch end before delay
- Cancels on touch move (drag)
- Supports custom delay values
- Resets `didLongPress` on new touch start

#### `useSavedDimensions.test.ts` — Dimension config persistence (8 tests)

- Starts empty when localStorage is empty
- Saves a dimension config with label and levels
- Persists to localStorage
- Generates unique IDs for each saved dimension
- Loads from localStorage on init
- Removes a saved dimension by ID
- Appends new items (not prepends)
- Handles corrupt localStorage gracefully

---

## Browser E2E Tests (Playwright MCP)

All tests run against `http://localhost:5173` with live backend. Screenshots saved in `test-screenshots/`.

### Results Summary

| # | Test | Status | Screenshot |
|---|------|--------|------------|
| 1 | Desktop initial load | PASSED | `01-desktop-initial-load.png` |
| 2 | Tree table expansion (Oncology → brands) | PASSED | `02-tree-expanded-oncology.png` |
| 3 | Scale switching ($B → $K → $M) | PASSED | verified via snapshot |
| 4 | Landing tab navigation | PASSED | `03-landing-tab.png` |
| 5 | Phased tab navigation | PASSED | `04-phased-tab.png` |
| 6 | Filter panel open | PASSED | `05-filter-panel-open.png` |
| 7 | Market filter (US) — data updates | PASSED | `06-us-market-filtered.png` |
| 8 | Assistant drawer (UI only) | PASSED | `07-assistant-drawer-open.png` |
| 9 | Mobile responsive (375px) | PASSED | `08-mobile-375px.png` |
| 10 | Dimension picker | PASSED | `09-dimension-picker.png` |
| 11 | Chart/TreeMap view toggle | PASSED | `10-trend-chart-view.png` |

### Detailed Test Notes

#### Test 1: Desktop Initial Load
- Page title: "Jarvis | AZ Insights"
- Header: logo, "Jarvis", "AstraZeneca", data freshness timestamp (2026-03-08 08:23)
- KPI strip: 4 cards (Total Revenue $B50.20, Gross Profit $B40.92, Total OpEx $B25.60, Op. Margin 30.5%)
- Each KPI shows vs Budget and vs PY variances with correct color coding
- Tree table: 5 TAs (Oncology, CVRM, R&I, Rare Disease, V&I) with Actual, vs Bgt, 12M Trend
- Sparkline trend charts render in each row
- Tabs: Overview (active), Landing, Phased

#### Test 2: Tree Expansion
- Clicked Oncology row → expanded to show 7 brands
- Brands: Calquence, Enhertu, Imfinzi, Koselugo, Lynparza, Tagrisso, Truqap
- Quarterly data (Q1-Q4 + Total) displayed correctly
- Child rows properly indented

#### Test 3: Scale Switching
- $B (default): Total AZ = $50.20B
- $K: Total AZ = $50,196,100K (locale-formatted with commas)
- $M: Total AZ = $50196.1M
- KPI strip values update in sync with table
- Active scale button highlighted

#### Test 4-5: Tab Navigation
- Landing tab: Shows "2025 Scenario Comparison" table with Q1-Q4 columns
- Phased tab: Shows same quarterly layout
- Filter state (scale, year) persists across tabs
- Tree expansion state preserved across tabs

#### Test 6: Filter Panel
- Toggle opens full filter bar below header
- Sections: Year (2023-2025), View By (Yearly/Quarterly/Monthly), Comparator (Budget/MTP/RBU2/PY), Market (US/China), TA (5 options), Product (dropdown)
- Active filters highlighted with filled style
- "Reset all filters" button at bottom right

#### Test 7: Market Filter (US)
- Selecting "United States" filters all data
- Total Revenue drops from $50,196M → $39,970M (correct US-only subset)
- Filter chip appears in header bar: "Market: United States ✕"
- "Clear" button next to chips
- Removing chip restores full data

#### Test 8: Assistant Drawer
- Opens from bottom as a sliding drawer
- Contains: placeholder "Ask anything about your dashboard data..."
- Input field: "Ask a follow-up..."
- Microphone button (voice input) visible
- Send button (disabled when input empty)
- Chat history button (hamburger icon)
- Dark overlay behind drawer

#### Test 9: Mobile Responsive (375px)
- Header compresses: logo + title + buttons fit
- KPI cards: 2x2 grid layout
- Swipe dots replace tab buttons (mobile gesture navigation)
- Tree table: compact rows with Name, Actual, vs Bgt columns
- Data values remain correct
- Dimension picker and scale buttons accessible

#### Test 10: Dimension Picker
- Opens dropdown showing current hierarchy: TA → Brand → Market
- Each level has: move left/right arrows, remove (✕) button
- "+ Region" button to add available levels
- Actions: Apply, Reset, Save as...
- Saved section shows "None yet"

#### Test 11: Chart View
- Toggle from table to chart view via "Show chart" button
- Horizontal bar chart: TAs sized proportionally to revenue
- Each bar shows: label, value ($M/$B), variance percentage
- Color coding: green (CVRM +2.7%), red (Oncology -2.8%, R&I -0.7%, etc.)
- Toggle back with "Show table" button

### Known Issues (Minor)
- React DevTools prop warning in console (cosmetic, non-blocking)
- Filter panel overlay blocks clicks on underlying elements until dismissed (expected UX behavior)
