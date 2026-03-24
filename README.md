# Delivery Order Router

FastAPI service that assigns incoming delivery orders to available dashers using a greedy load-balanced algorithm backed by in-memory SQLite — the correctness layer that ML-based ETA prediction and surge-pricing models depend on to receive clean assignment data.

## Demo

```bash
python -m venv .venv && source .venv/bin/activate
pip install fastapi uvicorn httpx matplotlib pytest pytest-asyncio pydantic
uvicorn main:app       # starts on :8000
pytest tests/          # 6/6 invariant tests
python benchmark.py    # 1,000 requests → reports/
```

## Invariants

- Every submitted order is assigned exactly once — no double-assignment possible
- No dasher ever exceeds declared capacity
- Both enforced by 6 deterministic pytest tests; no mocks, no stubs

## Benchmark

1,000 requests | p50 = 0.703 ms | p95 = 1.02 ms | 1,145 req/s | 0 errors

Full results: `reports/benchmark.json` | Histogram: `reports/benchmark.png`
