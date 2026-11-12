"""API-level verification for spring/autumn pairing, worker execution and CSV export."""
import os
import sys
import tempfile
from datetime import date
from pathlib import Path

os.environ.setdefault("JWT_SECRET", "test-secret")
os.environ.setdefault("DATABASE_URL", "sqlite:///" + tempfile.mktemp(suffix=".db"))
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("ARTIFACT_DIR", tempfile.mkdtemp(prefix="paired-artifacts-"))
os.environ.setdefault("SEED_DEMO", "false")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient
from src.config.database import Base, engine, SessionLocal
from src.main import app
from src.models import Survey, Transect, SpeciesCount, User
from src.services.audit import record
from src.utils.security import hash_password
from src.utils.serialize import row
from src.constants.species import SPECIES
from src.worker import analyze_run
from src.worker import app as celery_app
celery_app.conf.task_always_eager = True
celery_app.conf.task_eager_propagates = True

CODES = list(SPECIES)
failures = []

def check(label, condition, detail=""):
    print(("PASS " if condition else "FAIL ") + label + (" — " + detail if detail and not condition else ""))
    if not condition:
        failures.append(label)

def add_transect(db, survey, reference, n):
    t = Transect(survey_id=survey.id, reference=reference, name=reference, habitat="林缘")
    db.add(t); db.flush()
    counts = {code: 0 for code in CODES}
    if n:
        base = n // len(CODES)
        for i, code in enumerate(CODES):
            counts[code] = base + (1 if i < n - base * len(CODES) else 0)
    db.add_all([SpeciesCount(transect_id=t.id, species=c, count=v) for c, v in counts.items()])
    return t

Base.metadata.create_all(engine)
with SessionLocal() as db:
    for role, name in [("admin", "顾芩"), ("analyst", "林荞"), ("viewer", "季苔")]:
        db.add(User(email=f"{role}@test.demo", name=name, role=role, password_hash=hash_password("pass")))
    spring = Survey(name="春季", survey_date=date(2026, 4, 14), filename="spring.csv", description="")
    autumn = Survey(name="秋季", survey_date=date(2026, 10, 14), filename="autumn.csv", description="")
    db.add_all([spring, autumn]); db.flush()
    # Spring has SJ-01..04; autumn has SJ-01..03 plus SJ-05 (missing spring).
    for i in range(1, 5):
        add_transect(db, spring, f"SJ-0{i}", 300)
    for i in range(1, 4):
        add_transect(db, autumn, f"SJ-0{i}", 500)
    add_transect(db, autumn, "SJ-05", 500)
    db.commit()
    spring_id, autumn_id = spring.id, autumn.id

client = TestClient(app)

def token_for(role):
    from src.utils.security import issue_token
    with SessionLocal() as db:
        return issue_token(db.query(User).filter(User.role == role).first())

def auth(role):
    return {"Authorization": "Bearer " + token_for(role)}

# 1. Submission and worker execution with late-record backfill.
r = client.post("/runs/paired", json={"name": "春秋配对", "spring_survey_id": spring_id, "autumn_survey_id": autumn_id,
                                      "m": 100, "bootstrap": 60, "seed": 20261114}, headers=auth("analyst"))
check("paired run accepted", r.status_code == 201, r.text)
run_id = r.json()["id"]
analyze_run.run(run_id)
detail = client.get(f"/runs/{run_id}", headers=auth("analyst")).json()
result = detail["result"]
check("worker succeeded", detail["status"] == "succeeded", detail.get("error"))
statuses = {p["reference"]: p["status"] for p in result["pairs"]}
check("pairing by reference", statuses == {"SJ-01": "eligible", "SJ-02": "eligible", "SJ-03": "eligible",
                                           "SJ-04": "missing_autumn", "SJ-05": "missing_spring"}, str(statuses))
check("eligible/missing counters", result["eligible"] == 3 and result["missing"] == 2 and result["total_references"] == 5)
check("every reference listed", len(result["pairs"]) == result["total_references"])
check("missing reasons populated", all(p["reason"] for p in result["pairs"] if p["status"].startswith("missing_")))

# 2. CSV export includes pair rows and assumptions.
csv_response = client.get(f"/runs/{run_id}/export", headers=auth("viewer"))
check("csv export allowed for viewer", csv_response.status_code == 200, csv_response.text[:120])
body = csv_response.text
check("csv has one line per reference + header", len([x for x in body.splitlines() if x.strip()]) == result["total_references"] + 1)
check("csv carries missing reasons", "春季缺期" in body and "秋季缺期" in body)
check("csv carries statistical assumptions", "conditional on each observed composition" in body)

# 3. Late records backfilled, then a new paired run must include the new pairs.
with SessionLocal() as db:
    spring = db.get(Survey, spring_id); autumn = db.get(Survey, autumn_id)
    add_transect(db, spring, "SJ-05", 300)      # completes SJ-05
    add_transect(db, autumn, "SJ-04", 400)      # completes SJ-04
    db.commit()
r2 = client.post("/runs/paired", json={"name": "春秋配对补录", "spring_survey_id": spring_id, "autumn_survey_id": autumn_id,
                                       "m": 100, "bootstrap": 60, "seed": 20261114}, headers=auth("analyst"))
check("backfill run accepted", r2.status_code == 201, r2.text)
run2 = r2.json()["id"]
analyze_run.run(run2)
backfill = client.get(f"/runs/{run2}/", headers=auth("analyst")).json()["result"]
check("backfill adds pairs", backfill["eligible"] == 5 and backfill["missing"] == 0, str(backfill["eligible"]))
check("backfill changes fingerprint", backfill["fingerprint"] != result["fingerprint"])
stable_before = next(p["delta"] for p in result["pairs"] if p["reference"] == "SJ-01")
stable_after = next(p["delta"] for p in backfill["pairs"] if p["reference"] == "SJ-01")
check("existing pair unchanged after backfill", abs(stable_before - stable_after) < 1e-12)

# 4. Validation paths and permissions.
r = client.post("/runs/paired", json={"name": "同期", "spring_survey_id": spring_id, "autumn_survey_id": spring_id,
                                      "m": 100, "bootstrap": 50, "seed": 1}, headers=auth("analyst"))
check("same survey rejected 422", r.status_code == 422, str(r.status_code))
r = client.post("/runs/paired", json={"name": "观察员", "spring_survey_id": spring_id, "autumn_survey_id": autumn_id,
                                      "m": 100, "bootstrap": 50, "seed": 1}, headers=auth("viewer"))
check("viewer cannot queue", r.status_code == 403, str(r.status_code))
r = client.get(f"/runs/{run_id}/", headers=auth("viewer"))
check("viewer can read pair detail", r.status_code == 200)

# 5. m above common_limit: study still succeeds, pairs listed as insufficient.
with SessionLocal() as db:
    spring = db.get(Survey, spring_id); autumn = db.get(Survey, autumn_id)
    add_transect(db, spring, "SJ-06", 40)
    add_transect(db, autumn, "SJ-06", 40)
    db.commit()
r = client.post("/runs/paired", json={"name": "超m", "spring_survey_id": spring_id, "autumn_survey_id": autumn_id,
                                      "m": 200, "bootstrap": 50, "seed": 1}, headers=auth("analyst"))
run3 = r.json()["id"]
analyze_run.run(run3)
res3 = client.get(f"/runs/{run3}/", headers=auth("analyst")).json()["result"]
check("oversized m flagged", res3["m_exceeds_common_limit"] is True and res3["common_limit"] == 40)
check("under-m pairs retained", any(p["reference"] == "SJ-06" and p["status"] == "insufficient" for p in res3["pairs"]))
check("eligible pairs unaffected", res3["eligible"] == 5, str(res3["eligible"]))
check("no pair silently dropped", res3["total_references"] == 6 and len(res3["pairs"]) == 6)

# 6. Paired export works; single-survey export is refused; notes on paired runs are refused.
check("paired export available", client.get(f"/runs/{run_id}/export", headers=auth("viewer")).status_code == 200)
note_body = {"run_id": run_id, "name": "配对建议", "transect_ids": [1], "observation": "x", "suggested_action": "y"}
check("pair run cannot spawn single-survey note",
      client.post("/notes", json=note_body, headers=auth("analyst")).status_code == 422)
r = client.post("/runs", json={"name": "单期", "survey_id": spring_id, "transect_ids": [1, 2],
                               "m": 100, "bootstrap": 60, "seed": 7}, headers=auth("analyst"))
single = r.json()["id"]
analyze_run.run(single)
check("single run still succeeds", client.get(f"/runs/{single}/", headers=auth("analyst")).json()["status"] == "succeeded")
check("single run paired export refused", client.get(f"/runs/{single}/export", headers=auth("viewer")).status_code == 422)

print("\nRESULT " + ("ALL PASS" if not failures else f"FAILURES: {failures}"))
sys.exit(1 if failures else 0)
