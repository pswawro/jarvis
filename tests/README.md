# Jarvis Tests

## Unit Tests (Frontend)

```bash
cd frontend
npm test          # single run
npm run test:watch  # watch mode
```

4 test files, 42 tests. Covers: `filtersToExtra`, `scaleValue`, `scaleLabel`, `comparatorLabel`, `useBookmarks`, `useLongPress`, `useSavedDimensions`.

## AI Consistency Tests (Backend)

Requires a running backend (`python main.py` from `backend/`).

```bash
# Run all AI tests
cd jarvis
python -m pytest tests/ -v

# Run specific test group
python -m pytest tests/ -v -k "ranking"
python -m pytest tests/ -v -k "hallucination"
python -m pytest tests/ -v -k "config"

# Run against a different backend URL
TEST_BASE_URL=http://staging:8000 python -m pytest tests/ -v
```

Results are auto-saved to `tests/results/` as JSON.

### Comparing model configurations

```bash
# 1. Run with Sonnet (default)
python -m pytest tests/ -v
cp -r tests/results tests/results_sonnet
rm -rf tests/results

# 2. Set heavy model to Opus, restart backend, run again
#    export LLM_MODEL_ID_HEAVY=eu.anthropic.claude-opus-4-6
python -m pytest tests/ -v
cp -r tests/results tests/results_opus

# 3. Compare
python tests/compare_runs.py tests/results_sonnet tests/results_opus

# Or just check consistency of a single run
python tests/compare_runs.py tests/results
```

### Debug mode

Set `LLM_DEBUG=true` when starting the backend to log full tool calls, parameters, and responses.

```bash
LLM_DEBUG=true python main.py
```

## Browser E2E Screenshots

Screenshots from Playwright MCP browser tests are in `tests/e2e-screenshots/`. These are captured manually — see `test-report.html` for the full visual report.

## Test Report

Open `tests/test-report.html` in a browser for the full HTML presentation with all results and screenshots.
