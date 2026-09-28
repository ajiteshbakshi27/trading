"""Smoke: do the five services produce coherent, honest output offline?"""
from app.services import fusion, thesis_stress, information_propagation as ip, event_transmission as et
from app.models.enums import FeatureKey, DataMode, Regime

ev = [
    {"feature":"order_flow","z_score":0.9,"confidence":0.8,"data_mode":"mock","layer":"order_flow"},
    {"feature":"social","z_score":0.6,"confidence":0.7,"data_mode":"mock","layer":"reddit"},
    {"feature":"prediction","z_score":0.5,"confidence":0.6,"data_mode":"mock","layer":"prediction"},
    {"feature":"momentum","z_score":0.4,"confidence":0.6,"data_mode":"mock","layer":"price"},
]
out = fusion.fuse(ev)
print("FUSE  dir=%s conf=%.3f score=%.3f n=%d" % (out["direction"].value, out["confidence"], out["fused_score"], out["n_evidence"]))

th = thesis_stress.build_thesis("NVDA", ev, regime=Regime.HIGH_VOL, market_state={"realized_vol":2.6,"spread_bps":9.0})
print("THESIS %s %s conf=%.3f contradictions=%d" % (th.thesis_id[:12], th.direction.value, th.confidence, len(th.contradictions)))
st = thesis_stress.run_stress(th)
print("STRESS robust=%.2f fragile=%.2f label=%s" % (st.robustness, st.fragility, st.robustness_label))
for s in st.scenarios:
    print("   %-34s %.3f (%+.3f) flip=%s survive=%s" % (s.label, s.perturbed_confidence, s.delta_confidence, s.flipped, s.survives))
for n in st.notes: print("   NOTE:", n)

abl = fusion.fuse(ev, features_enabled=[FeatureKey.ORDER_FLOW])
print("ABLATE no-social conf=%.3f dir=%s" % (abl["confidence"], abl["direction"].value))

thin = fusion.fuse([{"feature":"order_flow","z_score":0.2,"confidence":0.35,"data_mode":"mock","layer":"order_flow"}])
print("THIN   conf=%.3f dir=%s abstaining=%s" % (thin["confidence"], thin["direction"].value, thin["abstaining"]))

class E:
    symbol="NVDA"; headline="Hyperscaler capex guidance lifted as AI infrastructure demand accelerates"
    event_type=ip.EventType.NEWS; category=ip.EventCategory.AI; event_id="E1"
    probability=0.72; detected_at="2026-09-26T10:00:00+00:00"
g = et.build_graph(E(), ["ai"], {}, DataMode.MOCK)
print("GRAPH  nodes=%d edges=%d themes=%s exposures=%d hist=%s" % (len(g.nodes), len(g.edges), [t.name for t in g.themes], len(g.exposures), g.historical_label))
for e in g.exposures[:4]:
    print("   %-6s strength=%.2f rel=%-22s median=%s n=%d" % (e.symbol, e.strength, e.relation.value, e.median_response_pct, e.n_observations))
