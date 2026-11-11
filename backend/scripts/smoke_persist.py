"""Phase 2 check: migration + persistence round-trip."""
import json
from app import database as db
from app.models.enums import DataMode

# 1. migration report
info = db.init_db()
print("INIT:", json.dumps(info))

# 2. run the demo once, then read everything back
from app.services import closed_loop
result = closed_loop.run_scenario_cycle(persist=True)
print("SCENARIO:", result["scenario_id"], "mode=", result["data_mode"].value)

# 3. read back
events = db.list_market_events(limit=5)
theses = db.list_predictions(limit=5)  # placeholder to confirm table exists
print("EVENTS READ:", len(events), "first mode=", events[0].get("data_mode") if events else None)
print("  event keys:", sorted(events[0].keys())[:8] if events else None)

preds = db.list_predictions(limit=5)
print("PREDICTIONS READ:", len(preds), "first status=", preds[0].get("status") if preds else None)

outcomes = db.list_outcomes(limit=5)
print("OUTCOMES READ:", len(outcomes), "first correct=", outcomes[0].get("correct") if outcomes else None)

autopsies = db.list_autopsies(limit=5)
print("AUTOPSIES READ:", len(autopsies), "first mode=", autopsies[0].get("failure_mode") if autopsies else None)

experiments = db.list_experiments(limit=5)
print("EXPERIMENTS READ:", len(experiments))

results = db.get_experiment_result("exp_full_model")
print("EXP RESULT READ:", results is not None, "n=", results.get("n") if results else None)

# 4. model version registry
from sqlmodel import Session, select
with Session(db.get_engine()) as s:
    rows = list(s.exec(select(db.ModelVersionRow)))
print("MODEL VERSIONS:", [(r.model_version, r.active) for r in rows])

# 5. research evidence (usable tournament samples)
ev = db.get_research_evidence(limit=100)
print("RESEARCH EVIDENCE:", len(ev), "with actual_move=", sum(1 for e in ev if e.get("actual_move_pct") is not None))

# 6. resolved pairs for failure analysis
pairs = db.resolved_pairs(limit=100)
print("RESOLVED PAIRS:", len(pairs))
