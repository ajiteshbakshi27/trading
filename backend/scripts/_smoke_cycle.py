"""Phase 3 check: scenario cycle persists usable tournament samples."""
from app import database as db
from app.services import closed_loop

result = closed_loop.run_scenario_cycle(persist=True)
print("STATUS:", result["status"], "| mode:", result["data_mode"].value)
print("EVENT:", result["event"].event_id, "| headline:", result["event"].headline[:60])
print("CHAIN steps:", len(result["chain"].propagation_steps),
      "| span_s:", result["chain"].span_s)
print("THESIS:", result["thesis"].direction.value, result["thesis"].confidence,
      "| contradictions:", len(result["thesis"].contradictions))
print("STRESS robustness:", result["stress"].robustness,
      "| worst:", result["stress"].worst_case_confidence)
print("PREDICTION:", result["prediction"].direction.value,
      "conf:", result["prediction"].confidence,
      "expected:", result["prediction"].expected_move_pct)
print("OUTCOME correct:", result["outcome"].correct,
      "| actual:", result["outcome"].actual_move_pct,
      "| error:", result["outcome"].error_pct)
print("AUTOPSY:", result["autopsy"].failure_mode.value,
      "| likelihood:", result["autopsy"].mode_likelihood,
      "| regime_mismatch:", result["autopsy"].regime_mismatch)
print("TOURNAMENT arms:", len(result["tournament"]["results"]),
      "| matrix status:", result["tournament"]["matrix"].status)

ev = db.get_research_evidence(limit=200)
usable = [e for e in ev if e.get("actual_move_pct") is not None]
print("USABLE SAMPLES:", len(usable), "/", len(ev))
