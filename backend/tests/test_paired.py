"""Offline verification for spring/autumn paired rarefaction."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.constants.species import SPECIES
from src.services.paired import analyze_paired, paired_csv

CODES = list(SPECIES)  # insertion order S01..S24

def transect(id, survey_id, reference, n_total, shape, name=None):
    """Distribute n_total individuals across 24 species using a simple shape."""
    counts = {}
    remaining = n_total
    for i, code in enumerate(CODES):
        if remaining <= 0:
            counts[code] = 0
            continue
        share = max(0, int(round(n_total * shape[i])))
        share = min(share, remaining)
        counts[code] = share
        remaining -= share
    if remaining:
        counts[CODES[0]] += remaining
    return {
        "id": id, "survey_id": survey_id, "reference": reference,
        "name": name or reference, "habitat": "林缘", "counts": counts,
    }

SHAPE = [0.08, 0.07, 0.06, 0.05, 0.05, 0.04, 0.04, 0.04, 0.03, 0.03,
         0.03, 0.03, 0.03, 0.02, 0.02, 0.02, 0.02, 0.02, 0.02, 0.01,
         0.01, 0.01, 0.01, 0.01]

def survey(id, name, date, filename):
    return {"id": id, "name": name, "survey_date": date, "filename": filename}

def run(spring_extra=None, autumn_extra=None, spring_n=300, autumn_n=500, m=100,
        bootstrap=80, seed=20261114, field_order=False):
    spring = survey(1, "春季返青调查", "2026-04-14", "sj-spring.csv")
    autumn = survey(3, "秋季样线调查", "2026-10-14", "sj-autumn.csv")
    springs = [transect(10 + i, 1, f"SJ-{i:02d}", spring_n, SHAPE) for i in range(1, 6)]
    autumns = [transect(20 + i, 3, f"SJ-{i:02d}", autumn_n, SHAPE) for i in range(1, 6)]
    if spring_extra:
        springs.extend(spring_extra)
    if autumn_extra:
        autumns.extend(autumn_extra)
    if field_order:
        springs = list(reversed(springs))
        autumns = list(reversed(autumns))
    config = {"mode": "paired", "spring_survey_id": 1, "autumn_survey_id": 3,
              "m": m, "bootstrap": bootstrap, "seed": seed}
    return analyze_paired(spring, autumn, springs, autumns, config)

def summary(result):
    return {
        "fingerprint": result["fingerprint"],
        "m": result["m"],
        "counts": {k: result[k] for k in ("eligible", "missing", "empty", "insufficient", "total_references")},
        "deltas": {p["reference"]: (None if p["delta"] is None else round(p["delta"], 6)
                                    ) for p in result["pairs"]},
        "delta_cis": {p["reference"]: ([round(x, 6) for x in p["delta_ci"]] if p["delta_ci"] else None)
                      for p in result["pairs"]},
        "overall": result["overall"] and {k: (round(v, 6) if isinstance(v, float) else
                                              ([round(x, 6) for x in v] if isinstance(v, list) else v))
                                          for k, v in result["overall"].items()},
    }

failures = []

def check(label, condition, detail=""):
    print(("PASS " if condition else "FAIL ") + label + (" — " + detail if detail and not condition else ""))
    if not condition:
        failures.append(label)

# 1. Row order / selection order must not change any numeric result.
a = summary(run())
b = summary(run(field_order=True))
check("row-order invariance", a == b, json.dumps({"forward": a, "reversed": b}, ensure_ascii=False)[:400])

# 2. Unequal sampling effort remains paired and m is fixed.
res = run(spring_n=300, autumn_n=500)
check("unequal N still paired", res["eligible"] == 5 and res["m"] == 100)
check("unequal N uses same m both sides",
      all(p["spring"]["rarefied"] is not None and p["autumn"]["rarefied"] is not None for p in res["pairs"]))

# 3. Missing pair (autumn lacks SJ-05, spring lacks SJ-06) is explained, not dropped.
spring = survey(1, "春季返青调查", "2026-04-14", "sj-spring.csv")
autumn = survey(3, "秋季样线调查", "2026-10-14", "sj-autumn.csv")
springs = [transect(10 + i, 1, f"SJ-{i:02d}", 300, SHAPE) for i in range(1, 7)]
autumns = [transect(20 + i, 3, f"SJ-{i:02d}", 500, SHAPE) for i in range(1, 5)] + [transect(27, 3, "SJ-08", 500, SHAPE)]
config = {"mode": "paired", "spring_survey_id": 1, "autumn_survey_id": 3, "m": 100, "bootstrap": 80, "seed": 20261114}
missing = analyze_paired(spring, autumn, springs, autumns, config)
statuses = {p["reference"]: p["status"] for p in missing["pairs"]}
check("missing autumn pair listed", statuses.get("SJ-05") == "missing_autumn", str(statuses))
check("missing spring pair listed", statuses.get("SJ-08") == "missing_spring", str(statuses))
check("missing reasons non-empty", all(p["reason"] for p in missing["pairs"] if p["status"].startswith("missing_")))
check("missing counts surfaced", missing["missing"] == 3 and missing["total_references"] == 7)

# 4. Empty transect is separate from insufficient and is not low diversity.
springs.append(transect(30, 1, "SJ-07", 0, SHAPE))
autumns.append(transect(31, 3, "SJ-07", 0, SHAPE))
empty = analyze_paired(spring, autumn, springs, autumns, config)
empty_pair = next(p for p in empty["pairs"] if p["reference"] == "SJ-07")
check("empty pair status", empty_pair["status"] == "empty" and empty["empty"] == 1, str(empty_pair["status"]))

# 5. Under-sampled pair kept, blocks that pair only, with a reason.
springs = [transect(10, 1, "SJ-01", 300, SHAPE), transect(11, 1, "SJ-02", 40, SHAPE)]
autumns = [transect(20, 3, "SJ-01", 500, SHAPE), transect(21, 3, "SJ-02", 500, SHAPE)]
short = analyze_paired(spring, autumn, springs, autumns, {"mode": "paired", "spring_survey_id": 1,
                                                       "autumn_survey_id": 3, "m": 100, "bootstrap": 80, "seed": 1})
short_pair = next(p for p in short["pairs"] if p["reference"] == "SJ-02")
check("insufficient pair retained", short_pair["status"] == "insufficient" and short["insufficient"] == 1)
check("insufficient reason names N and m", "N=40" in short_pair["reason"] and "m=100" in short_pair["reason"], short_pair["reason"])
check("insufficient did not enter comparison", short_pair["delta"] is None and short["eligible"] == 1)
check("common_limit uses both sides", short["common_limit"] == 40)

# 6. Late-record backfill changes fingerprint and adds the new pair; stable pairs keep their delta.
before = analyze_paired(spring, autumn, springs, autumns, {"mode": "paired", "spring_survey_id": 1,
                                                         "autumn_survey_id": 3, "m": 100, "bootstrap": 80, "seed": 1})
backs = [transect(12, 1, "SJ-03", 300, SHAPE)]
backs_a = [transect(22, 3, "SJ-03", 500, SHAPE)]
after = analyze_paired(spring, autumn, springs + backs, autumns + backs_a, {"mode": "paired", "spring_survey_id": 1,
                                                                          "autumn_survey_id": 3, "m": 100, "bootstrap": 80, "seed": 1})
check("backfill changes fingerprint", before["fingerprint"] != after["fingerprint"])
check("backfill adds eligible pair", after["eligible"] == 2 and after["total_references"] == 3)
deltas_after = {p["reference"]: round(p["delta"], 9) for p in after["pairs"] if p["reference"] == "SJ-01"}
check("existing pair delta unchanged after backfill",
      round(next(p for p in before["pairs"] if p["reference"] == "SJ-01")["delta"], 9) == deltas_after["SJ-01"],
      str(deltas_after))
check("existing pair CI unchanged after backfill",
      next(p for p in before["pairs"] if p["reference"] == "SJ-01")["delta_ci"] ==
      next(p for p in after["pairs"] if p["reference"] == "SJ-01")["delta_ci"])

# 7. Reproducibility with the same seed; a different seed moves the interval.
r1 = run(bootstrap=60, seed=777)
r2 = run(bootstrap=60, seed=777)
r3 = run(bootstrap=60, seed=778)
check("same seed reproducibility", summary(r1) == summary(r2))
check("different seed changes CI",
      summary(r1)["delta_cis"] != summary(r3)["delta_cis"])

# 8. CSV contains pair details, exclusions, assumptions and stats headers.
headers, rows = paired_csv({"id": 1, "name": "春秋配对", "config": {"mode": "paired"}, "result": r1})
check("csv has one row per pair", len(rows) == len(r1["pairs"]))
check("csv header exposes exclusions", any("排除原因" in h for h in headers) and any("统计假设" in h for h in headers))
check("csv rows carry assumption text", all(len(r[9]) > 50 for r in rows))
check("csv includes pair status labels", all(r[11] for r in rows))

# 9. m outside common limit is flagged, not silently clamped.
big = analyze_paired(spring, autumn, springs, autumns, {"mode": "paired", "spring_survey_id": 1,
                                                       "autumn_survey_id": 3, "m": 200, "bootstrap": 50, "seed": 1})
check("m above common limit flagged", big["m_exceeds_common_limit"] is True and big["common_limit"] == 40)
check("pairs failing m stay listed as insufficient", big["insufficient"] == 1 and big["eligible"] == 1
      and next(p for p in big["pairs"] if p["reference"] == "SJ-02")["status"] == "insufficient")

# 10. Same survey rejected.
try:
 analyze_paired(spring, spring, springs, springs, {"mode": "paired", "spring_survey_id": 1,
                                                 "autumn_survey_id": 1, "m": 10, "bootstrap": 50, "seed": 1})
 check("same survey rejected", False)
except ValueError as e:
 check("same survey rejected", "不同调查期" in str(e), str(e))

print("\nRESULT " + ("ALL PASS" if not failures else f"FAILURES: {failures}"))
sys.exit(1 if failures else 0)
