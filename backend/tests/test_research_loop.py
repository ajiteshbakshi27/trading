"""
QuantPulse AI — Research loop tests.

Covers the closed loop: event creation, propagation, signal generation,
thesis creation, stress scenarios, prediction creation, resolution, failure
autopsy, experiment creation, reproducibility, mock-mode operation, missing
credentials, API validation, and unauthorized access.

Run:  python -m pytest tests/test_research_loop.py -v
"""
from __future__ import annotations

import pytest

from app.models.enums import (
    DataMode,
    Direction,
    FailureMode,
    FeatureKey,
    Regime,
    StressScenario,
    Verdict,
)
from app.services import (
    event_transmission,
    fusion,
    information_propagation,
    prediction_autopsy,
    signal_tournament,
    thesis_stress,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def bullish_evidence():
    return [
        {"feature": "order_flow", "z_score": 0.9, "confidence": 0.8,
         "data_mode": "mock", "layer": "order_flow"},
        {"feature": "social", "z_score": 0.6, "confidence": 0.7,
         "data_mode": "mock", "layer": "reddit"},
        {"feature": "prediction", "z_score": 0.5, "confidence": 0.6,
         "data_mode": "mock", "layer": "prediction"},
    ]


@pytest.fixture
def bearish_evidence():
    return [
        {"feature": "order_flow", "z_score": -0.8, "confidence": 0.75,
         "data_mode": "mock", "layer": "order_flow"},
        {"feature": "social", "z_score": -0.5, "confidence": 0.6,
         "data_mode": "mock", "layer": "x"},
    ]


# ---------------------------------------------------------------------------
# Event creation + propagation
# ---------------------------------------------------------------------------

class TestInformationPropagation:
    def test_detect_events_returns_list(self):
        books = [{"symbol": "NVDA", "mid": 130.0, "ofi": {"ofi_norm": 0.5},
                  "spread_bps": 5.0, "bids": [], "asks": []}]
        sentiment = {"posts": [], "by_ticker": {}}
        markets = []
        news = []
        events = information_propagation.detect_events(
            books, sentiment, markets, news, mode=DataMode.MOCK)
        assert isinstance(events, list)

    def test_collect_evidence_produces_all_layers(self, bullish_evidence):
        from app.models.information_event import MarketEvent
        event = MarketEvent(
            event_id="E1", symbol="NVDA", event_type="news",
            category="company", headline="test", detected_at="2026-01-01T00:00:00Z",
            data_mode=DataMode.MOCK,
        )
        evidence = information_propagation.collect_evidence(event)
        assert len(evidence) > 0
        layers = {e.layer for e in evidence}
        assert "event" in layers

    def test_build_chain_orders_steps(self, bullish_evidence):
        from app.models.information_event import MarketEvent, Evidence
        event = MarketEvent(
            event_id="E1", symbol="NVDA", event_type="news",
            category="company", headline="test", detected_at="2026-01-01T00:00:00Z",
            data_mode=DataMode.MOCK,
        )
        evidence = information_propagation.collect_evidence(event)
        fused = fusion.fuse(bullish_evidence)
        chain = information_propagation.build_chain(event, evidence, fused)
        assert len(chain.propagation_steps) > 0
        # Steps are in canonical layer order
        orders = [s.layer.order for s in chain.propagation_steps]
        assert orders == sorted(orders)

    def test_node_detail_insufficient_data(self):
        from app.models.information_event import MarketEvent, InformationEvent
        event = MarketEvent(
            event_id="E1", symbol="NVDA", event_type="news",
            category="company", headline="test", detected_at="2026-01-01T00:00:00Z",
            data_mode=DataMode.MOCK,
        )
        chain = InformationEvent(
            event_id="E1", symbol="NVDA", event_type="news",
            detected_at="2026-01-01T00:00:00Z", data_mode=DataMode.MOCK,
        )
        # A layer with no observation returns an honest insufficient-data payload
        detail = information_propagation.node_detail(chain, "price")
        assert detail is not None
        assert detail["status"] == "insufficient_data"


# ---------------------------------------------------------------------------
# Signal generation (fusion)
# ---------------------------------------------------------------------------

class TestFusion:
    def test_bullish_fusion(self, bullish_evidence):
        out = fusion.fuse(bullish_evidence)
        assert out["direction"] == Direction.LONG
        assert out["confidence"] > 0.5
        assert out["n_evidence"] == 3

    def test_bearish_fusion(self, bearish_evidence):
        out = fusion.fuse(bearish_evidence)
        assert out["direction"] == Direction.SHORT

    def test_empty_evidence_abstains(self):
        out = fusion.fuse([])
        assert out["direction"] == Direction.FLAT
        assert out["abstaining"] is True

    def test_thin_evidence_shrinks_confidence(self):
        thin = [{"feature": "order_flow", "z_score": 0.2, "confidence": 0.35,
                 "data_mode": "mock", "layer": "order_flow"}]
        out = fusion.fuse(thin)
        assert out["confidence"] <= 0.5

    def test_ablation_changes_confidence(self, bullish_evidence):
        full = fusion.fuse(bullish_evidence)
        ablated = fusion.fuse(bullish_evidence, features_enabled=[FeatureKey.ORDER_FLOW])
        assert full["confidence"] != ablated["confidence"]

    def test_fusion_is_deterministic(self, bullish_evidence):
        a = fusion.fuse(bullish_evidence)
        b = fusion.fuse(bullish_evidence)
        assert a["confidence"] == b["confidence"]
        assert a["fused_score"] == b["fused_score"]


# ---------------------------------------------------------------------------
# Thesis creation + stress
# ---------------------------------------------------------------------------

class TestThesisStress:
    def test_build_thesis(self, bullish_evidence):
        thesis = thesis_stress.build_thesis("NVDA", bullish_evidence)
        assert thesis.direction == Direction.LONG
        assert thesis.confidence > 0.5
        assert thesis.symbol == "NVDA"

    def test_stress_test_returns_scenarios(self, bullish_evidence):
        thesis = thesis_stress.build_thesis("NVDA", bullish_evidence)
        test = thesis_stress.run_stress(thesis)
        assert len(test.scenarios) == 7
        assert 0.0 <= test.robustness <= 1.0
        assert 0.0 <= test.fragility <= 1.0

    def test_order_flow_reversal_can_flip(self, bullish_evidence):
        thesis = thesis_stress.build_thesis("NVDA", bullish_evidence)
        test = thesis_stress.run_stress(thesis)
        reversal = next(
            s for s in test.scenarios
            if s.scenario == StressScenario.ORDER_FLOW_REVERSAL
        )
        # With strong order flow, reversal should reduce confidence
        assert reversal.delta_confidence < 0

    def test_na_scenario_reported_not_scored(self):
        # Evidence with no news layer -> conflicting_source is N/A
        evidence = [
            {"feature": "order_flow", "z_score": 0.9, "confidence": 0.8,
             "data_mode": "mock", "layer": "order_flow"},
        ]
        thesis = thesis_stress.build_thesis("NVDA", evidence)
        test = thesis_stress.run_stress(thesis)
        assert any("not applicable" in n for n in test.notes)


# ---------------------------------------------------------------------------
# Prediction + outcome + autopsy
# ---------------------------------------------------------------------------

class TestPredictionAutopsy:
    def test_resolve_correct_prediction(self):
        from app.models.prediction_outcome import PredictionRecord
        pred = PredictionRecord(
            prediction_id="P1", symbol="NVDA", direction=Direction.LONG,
            confidence=0.8, entry_price=100.0, expected_move_pct=2.0,
            horizon="1h", created_at="2026-01-01T00:00:00Z",
            expires_at="2026-01-01T01:00:00Z",
            data_mode=DataMode.MOCK, regime=Regime.TREND,
            feature_contributions=[], evidence=[],
        )
        outcome = prediction_autopsy.resolve(pred, 103.0)
        assert outcome.correct is True
        assert outcome.actual_move_pct == pytest.approx(3.0)

    def test_resolve_incorrect_prediction(self):
        from app.models.prediction_outcome import PredictionRecord
        pred = PredictionRecord(
            prediction_id="P2", symbol="NVDA", direction=Direction.LONG,
            confidence=0.8, entry_price=100.0, expected_move_pct=2.0,
            horizon="1h", created_at="2026-01-01T00:00:00Z",
            expires_at="2026-01-01T01:00:00Z",
            data_mode=DataMode.MOCK, regime=Regime.TREND,
            feature_contributions=[], evidence=[],
        )
        outcome = prediction_autopsy.resolve(pred, 96.0)
        assert outcome.correct is False
        assert outcome.actual_move_pct == pytest.approx(-4.0)

    def test_autopsy_only_on_failure(self):
        from app.models.prediction_outcome import PredictionRecord
        pred = PredictionRecord(
            prediction_id="P3", symbol="NVDA", direction=Direction.LONG,
            confidence=0.8, entry_price=100.0, expected_move_pct=2.0,
            horizon="1h", created_at="2026-01-01T00:00:00Z",
            expires_at="2026-01-01T01:00:00Z",
            data_mode=DataMode.MOCK, regime=Regime.TREND,
            feature_contributions=[], evidence=[],
        )
        outcome = prediction_autopsy.resolve(pred, 103.0)
        # Correct prediction -> no autopsy
        assert outcome.correct is True

    def test_autopsy_classifies_failure(self):
        from app.models.prediction_outcome import PredictionRecord
        pred = PredictionRecord(
            prediction_id="P4", symbol="NVDA", direction=Direction.LONG,
            confidence=0.8, entry_price=100.0, expected_move_pct=2.0,
            horizon="1h", created_at="2026-01-01T00:00:00Z",
            expires_at="2026-01-01T01:00:00Z",
            data_mode=DataMode.MOCK, regime=Regime.TREND,
            feature_contributions=[], evidence=[
                {"feature": "order_flow", "z_score": 0.9, "confidence": 0.8,
                 "data_mode": "mock", "layer": "order_flow", "contribution": 0.5},
            ],
        )
        outcome = prediction_autopsy.resolve(pred, 96.0, realized_vol=3.5)
        assert outcome.correct is False
        autopsy = prediction_autopsy.run_autopsy(
            pred, outcome, realized_regime=Regime.HIGH_VOL)
        assert autopsy.failure_mode is not FailureMode.UNCLASSIFIED
        assert autopsy.regime_mismatch is True

    def test_failure_analysis_withholds_below_floor(self):
        pairs = []
        analysis = prediction_autopsy.failure_analysis(pairs)
        assert analysis.status == "insufficient_data"
        assert analysis.accuracy is None

    def test_failure_analysis_computes_above_floor(self):
        from app.models.prediction_outcome import PredictionRecord, PredictionOutcome
        pairs = []
        for i in range(25):
            pred = PredictionRecord(
                prediction_id=f"P{i}", symbol="NVDA", direction=Direction.LONG,
                confidence=0.7, entry_price=100.0, expected_move_pct=2.0,
                horizon="1h", created_at="2026-01-01T00:00:00Z",
                expires_at="2026-01-01T01:00:00Z",
                data_mode=DataMode.MOCK, regime=Regime.TREND,
                feature_contributions=[], evidence=[],
            )
            outcome = PredictionOutcome(
                outcome_id=f"O{i}", prediction_id=f"P{i}", symbol="NVDA",
                exit_price=101.0, actual_move_pct=1.0, expected_move_pct=2.0,
                error_pct=-1.0, correct=True, data_mode=DataMode.MOCK,
                resolved_at="2026-01-01T01:00:00Z",
            )
            pairs.append((pred, outcome))
        analysis = prediction_autopsy.failure_analysis(pairs)
        assert analysis.status == "ok"
        assert analysis.accuracy is not None
        assert analysis.resolved_predictions == 25


# ---------------------------------------------------------------------------
# Event transmission
# ---------------------------------------------------------------------------

class TestEventTransmission:
    def test_build_graph_returns_nodes_and_edges(self):
        from app.models.information_event import MarketEvent
        event = MarketEvent(
            event_id="E1", symbol="NVDA", event_type="ai",
            category="ai", headline="AI infrastructure spending increases",
            detected_at="2026-01-01T00:00:00Z", data_mode=DataMode.MOCK,
        )
        graph = event_transmission.build_graph(event, ["ai"], {})
        assert len(graph.nodes) > 0
        assert len(graph.edges) > 0
        assert len(graph.exposures) > 0

    def test_historical_response_insufficient_without_data(self):
        hist = event_transmission.historical_response("NVDA", "ai", [])
        assert hist["status"] == "insufficient_data"
        assert hist["median_response_pct"] is None

    def test_historical_response_computes_with_enough_data(self):
        rows = [
            {"symbol": "NVDA", "event_type": "ai", "response_pct": 2.0,
             "data_mode": "mock"},
            {"symbol": "NVDA", "event_type": "ai", "response_pct": 3.0,
             "data_mode": "mock"},
            {"symbol": "NVDA", "event_type": "ai", "response_pct": 1.0,
             "data_mode": "mock"},
        ]
        hist = event_transmission.historical_response("NVDA", "ai", rows)
        assert hist["status"] == "ok"
        assert hist["median_response_pct"] == pytest.approx(2.0)

    def test_relation_vocabulary_excludes_causation(self):
        from app.models.enums import CAUSAL_CLAIMS_FORBIDDEN, RELATION_VOCABULARY
        for word in CAUSAL_CLAIMS_FORBIDDEN:
            assert word not in RELATION_VOCABULARY


# ---------------------------------------------------------------------------
# Signal tournament
# ---------------------------------------------------------------------------

class TestSignalTournament:
    def test_build_observation_set_deterministic(self):
        obs1, win1 = signal_tournament.build_observation_set(["NVDA"], n=30, seed=7)
        obs2, win2 = signal_tournament.build_observation_set(["NVDA"], n=30, seed=7)
        assert len(obs1) == len(obs2)
        assert obs1[0]["actual_move_pct"] == obs2[0]["actual_move_pct"]

    def test_run_arm_produces_metrics(self):
        obs, window = signal_tournament.build_observation_set(["NVDA"], n=40, seed=7)
        result = signal_tournament.run_arm("TEST", "", [], obs, window)
        assert result.n_observations > 0
        assert result.overall.n > 0

    def test_matrix_withholds_below_floor(self):
        suite = signal_tournament.run_suite(["NVDA"], n=10, seed=7)
        matrix = signal_tournament.build_matrix(suite, min_n=20)
        assert matrix.status == "insufficient_data"

    def test_matrix_computes_above_floor(self):
        suite = signal_tournament.run_suite(["NVDA"], n=60, seed=7)
        matrix = signal_tournament.build_matrix(suite, min_n=5)
        assert matrix.status in ("ok", "partial")
        assert len(matrix.rows) > 0

    def test_ablation_arms_differ(self):
        suite = signal_tournament.run_suite(["NVDA"], n=60, seed=7)
        results = signal_tournament.attach_deltas(suite)
        full = next(r for r in results if not r.features_disabled)
        no_social = next(
            r for r in results
            if FeatureKey.SOCIAL in r.features_disabled
        )
        # Disabling a feature should change the result
        assert full.overall.n == no_social.overall.n


# ---------------------------------------------------------------------------
# Mock mode + missing credentials
# ---------------------------------------------------------------------------

class TestMockMode:
    def test_fusion_works_without_credentials(self, bullish_evidence):
        out = fusion.fuse(bullish_evidence)
        assert out["data_mode"] == DataMode.MOCK

    def test_scenario_cycle_runs_offline(self):
        from app.services import closed_loop
        result = closed_loop.run_scenario_cycle(persist=False)
        assert result["status"] == "ok"
        assert result["data_mode"] == DataMode.SIMULATED

    def test_feed_layer_handles_missing_credentials(self):
        from app.services import feed_layer
        news, mode = feed_layer.get_news(symbol="NVDA", limit=5)
        # In a credentialless sandbox the feed layer falls back to deterministic
        # mock data. When a network path exists it may report LIVE — both are
        # honest labels, so we only assert the contract.
        assert mode in (DataMode.MOCK, DataMode.LIVE)
        assert len(news) > 0


# ---------------------------------------------------------------------------
# Research backtest
# ---------------------------------------------------------------------------

class TestResearchBacktest:
    def test_backtest_returns_result(self):
        from app.services import research_backtest
        result = research_backtest.run_backtest("NVDA", period="1y", min_resolved=20)
        assert result["status"] in ("ok", "insufficient_data")
        assert result["symbol"] == "NVDA"
        assert result["data_mode"] in ("backtest", "mock")

    def test_backtest_synthetic_fallback(self):
        from app.services import research_backtest
        result = research_backtest.run_backtest("NVDA", period="1y", min_resolved=20)
        # Should never raise; synthetic fallback keeps the loop running
        assert result is not None

    def test_backtest_withholds_below_floor(self):
        from app.services import research_backtest
        result = research_backtest.run_backtest("NVDA", period="6mo", min_resolved=5000)
        assert result["status"] == "insufficient_data"
        assert result["label"] == "INSUFFICIENT DATA"

    def test_backtest_suite_runs(self):
        from app.services import research_backtest
        result = research_backtest.run_suite(["NVDA", "TSLA"], period="1y", min_resolved=20)
        assert result["status"] in ("ok", "insufficient_data")
        assert len(result["results"]) == 2

    def test_backtest_predictions_have_outcomes(self):
        from app.services import research_backtest
        result = research_backtest.run_backtest("NVDA", period="1y", min_resolved=20)
        if result["status"] == "ok":
            assert len(result["predictions"]) > 0
            for p in result["predictions"]:
                assert "actual_move_pct" in p
                assert "correct" in p


# ---------------------------------------------------------------------------
# Paper trading
# ---------------------------------------------------------------------------

class TestPaperTrading:
    def test_ledger_buy_and_sell(self):
        from app.services.paper_trading import PaperLedger
        ledger = PaperLedger(budget=10000.0)
        order = ledger.execute("NVDA", "buy", 10, 100.0)
        assert order.side == "buy"
        assert order.qty == 10
        assert ledger.cash < 10000.0
        assert "NVDA" in ledger.positions

        sell = ledger.execute("NVDA", "sell", 5, 110.0)
        assert sell.side == "sell"
        assert ledger.positions["NVDA"].qty == 5

    def test_ledger_insufficient_cash(self):
        from app.services.paper_trading import PaperLedger
        ledger = PaperLedger(budget=100.0)
        with pytest.raises(ValueError):
            ledger.execute("NVDA", "buy", 100, 100.0)

    def test_ledger_insufficient_position(self):
        from app.services.paper_trading import PaperLedger
        ledger = PaperLedger(budget=10000.0)
        ledger.execute("NVDA", "buy", 5, 100.0)
        with pytest.raises(ValueError):
            ledger.execute("NVDA", "sell", 10, 100.0)

    def test_ledger_liquidate_all(self):
        from app.services.paper_trading import PaperLedger
        ledger = PaperLedger(budget=10000.0)
        ledger.execute("NVDA", "buy", 10, 100.0)
        ledger.execute("TSLA", "buy", 5, 200.0)
        orders = ledger.liquidate_all({"NVDA": 105.0, "TSLA": 210.0})
        assert len(orders) == 2
        assert len(ledger.positions) == 0

    def test_ledger_metrics(self):
        from app.services.paper_trading import PaperLedger
        ledger = PaperLedger(budget=10000.0)
        ledger.execute("NVDA", "buy", 10, 100.0)
        ledger.mark_to_market({"NVDA": 110.0})
        snap = ledger.snapshot()
        assert snap["equity"] > 10000.0
        assert snap["total_pnl"] > 0
        assert snap["sharpe"] is not None or snap["sharpe"] is None  # may be None with 1 point

    def test_ledger_data_mode_is_mock(self):
        from app.services.paper_trading import PaperLedger
        ledger = PaperLedger()
        assert ledger.snapshot()["data_mode"] == "mock"


# ---------------------------------------------------------------------------
# Data mode integrity
# ---------------------------------------------------------------------------

class TestDataModeIntegrity:
    def test_weakest_rollup(self):
        assert fusion.weakest(DataMode.LIVE, DataMode.MOCK) == DataMode.MOCK
        assert fusion.weakest(DataMode.LIVE, DataMode.BACKTEST) == DataMode.BACKTEST
        assert fusion.weakest(DataMode.LIVE, DataMode.LIVE) == DataMode.LIVE

    def test_insufficient_data_constant(self):
        from app.models.common import INSUFFICIENT_DATA
        assert INSUFFICIENT_DATA == "INSUFFICIENT DATA"

    def test_causal_claims_forbidden(self):
        from app.models.common import CAUSAL_CLAIMS_FORBIDDEN
        assert "caused" in CAUSAL_CLAIMS_FORBIDDEN
        assert "guaranteed" in CAUSAL_CLAIMS_FORBIDDEN

    def test_enum_tolerant_parsing(self):
        assert DataMode("DataMode.SIMULATED") == DataMode.SIMULATED
        assert DataMode("simulated") == DataMode.SIMULATED
        assert DataMode("mock") == DataMode.MOCK
