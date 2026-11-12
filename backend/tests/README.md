# Paired spring/autumn verification

`test_paired.py` — offline algorithm checks: row-order invariance, unequal N at the
same m, missing spring/autumn pairs, empty vs insufficient pairs, backfill stability,
fixed-seed reproducibility, CSV shape, m above common limit, same-survey rejection.

`test_api_paired.py` — FastAPI + worker path on a throwaway SQLite database with
eager Celery: POST /runs/paired, pairing union, CSV export, backfill rerun, role
guards, failed-export guard, single-survey regression.

Run from `backend/`:

    JWT_SECRET=test python3 tests/test_paired.py
    JWT_SECRET=test python3 tests/test_api_paired.py

Both print `RESULT ALL PASS` and exit non-zero on failure.
