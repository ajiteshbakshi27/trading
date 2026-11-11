"""
Parakh — Feature 7: Indian event impact maps.

EVENT → THEME → ASSETS with a typed, *non-causal* relationship and the
direction in which the theme has typically been sensitive. Where an event
has fixed historical dates (Union Budget), we measure each asset's actual
move around those dates from price data and report the sample size.
"""
from __future__ import annotations

from typing import Any, Dict, List

from app.parakh import market, universe

EVENTS: Dict[str, Dict[str, Any]] = {
    "RBI_POLICY": {
        "name": "RBI monetary policy (repo rate)",
        "when": "Six MPC meetings a year; decision announced ~10:00 IST on the last day.",
        "themes": [
            {"theme": "Rate-sensitive lenders", "sectors": ["bank_private", "bank_psu", "nbfc"],
             "sensitivity": "A rate cut usually helps loan growth but can squeeze bank margins; NBFC funding costs fall."},
            {"theme": "Rate-sensitive demand", "sectors": ["auto", "realty"],
             "sensitivity": "Cheaper EMIs are typically read as positive for autos and real estate."},
        ],
    },
    "UNION_BUDGET": {
        "name": "Union Budget",
        "when": "1 February each year (2024 also had a full budget on 23 July).",
        "dates": ["2021-02-01", "2022-02-01", "2023-02-01", "2024-02-01", "2024-07-23", "2025-02-01", "2026-02-01"],
        "themes": [
            {"theme": "Government capex", "sectors": ["infra", "cement", "defence", "power"],
             "sensitivity": "Higher capex allocations are associated with gains in infra, cement and defence."},
            {"theme": "PSU banks & divestment", "sectors": ["bank_psu"],
             "sensitivity": "Recapitalisation / divestment plans move PSU banks."},
            {"theme": "Consumption & tax", "sectors": ["fmcg", "auto", "consumer"],
             "sensitivity": "Income-tax relief is associated with consumption names."},
            {"theme": "Capital-markets taxes (STT/LTCG)", "sectors": ["capital_markets"],
             "sensitivity": "STT or capital-gains tax changes hit brokers and exchanges directly."},
        ],
    },
    "QUARTERLY_RESULTS": {
        "name": "Quarterly results season",
        "when": "Roughly mid-Jan, mid-Apr, mid-Jul, mid-Oct; IT majors report first.",
        "themes": [{"theme": "Company-specific gap risk", "sectors": ["*"],
                    "sensitivity": "Single stocks can gap 5–10% on results; check the date before holding through it."}],
    },
    "MONSOON": {
        "name": "IMD monsoon forecast & progress",
        "when": "April (first forecast), June–September (progress).",
        "themes": [{"theme": "Rural demand", "sectors": ["fmcg", "agri", "auto"],
                    "sensitivity": "A good monsoon is associated with stronger rural demand (FMCG, tractors, two-wheelers)."}],
    },
    "CRUDE_OIL": {
        "name": "Crude oil price spike",
        "when": "Any time — driven by OPEC+, geopolitics.",
        "themes": [
            {"theme": "Oil marketing margins", "sectors": ["oil_marketing"],
             "sensitivity": "Higher crude typically squeezes OMC margins (BPCL, IOC)."},
            {"theme": "Crude as a cost", "sectors": ["paints", "aviation"],
             "sensitivity": "Paints and airlines use crude derivatives / jet fuel — usually negative."},
            {"theme": "Upstream producers", "sectors": ["oil_upstream"],
             "sensitivity": "Producers like ONGC typically benefit from higher realisations."},
        ],
    },
    "RUPEE_WEAKNESS": {
        "name": "Rupee weakens vs US dollar",
        "when": "Any time.",
        "themes": [
            {"theme": "Exporters", "sectors": ["it", "pharma"],
             "sensitivity": "Dollar earners (IT services, pharma exporters) typically benefit."},
            {"theme": "Importers", "sectors": ["oil_marketing", "aviation"],
             "sensitivity": "Dollar-cost importers are typically hurt."},
        ],
    },
    "US_FED": {
        "name": "US Federal Reserve decision",
        "when": "Eight FOMC meetings a year; result lands after Indian market hours.",
        "themes": [{"theme": "Foreign flows (FPI)", "sectors": ["bank_private", "it"],
                    "sensitivity": "Fed cuts tend to support FPI inflows into large Indian banks and IT; hikes the reverse."}],
    },
    "SEBI_FNO_RULES": {
        "name": "SEBI F&O / market-structure rules",
        "when": "As announced.",
        "themes": [{"theme": "Retail derivatives volumes", "sectors": ["capital_markets"],
                    "sensitivity": "Curbs on retail F&O hit discount brokers and exchanges' volume-linked revenue."}],
    },
}


def list_events() -> List[Dict[str, str]]:
    return [{"id": k, "name": v["name"], "when": v["when"]} for k, v in EVENTS.items()]


def _assets_for(sectors: List[str]) -> List[str]:
    if "*" in sectors:
        return []
    return [s for s, (_, sec, _) in universe.STOCKS.items() if sec in sectors]


def _window_move(symbol: str, date: str, bars: List[market.Bar], before: int = 1, after: int = 3) -> Any:
    dates = [b["date"] for b in bars]
    idx = next((i for i, d in enumerate(dates) if d >= date), None)
    if idx is None or idx - before < 0 or idx + after >= len(bars):
        return None
    return bars[idx + after]["close"] / bars[idx - before]["close"] - 1


def impact_map(event_id: str, measure: bool = True) -> Dict[str, Any]:
    ev = EVENTS.get(event_id)
    if not ev:
        raise KeyError(event_id)
    themes = []
    data_mode = "n/a"
    for th in ev["themes"]:
        assets = []
        for sym in _assets_for(th["sectors"]):
            entry: Dict[str, Any] = {"symbol": sym, "name": universe.display_name(sym),
                                     "relation": "associated"}
            if measure and ev.get("dates"):
                bars, mode = market.history(sym, 1250)
                data_mode = mode
                moves = [m for m in (_window_move(sym, d, bars) for d in ev["dates"]) if m is not None]
                if len(moves) >= 3:
                    entry.update({"relation": "historical",
                                  "avg_move_pct": round(sum(moves) / len(moves) * 100, 2),
                                  "up_share": round(sum(m > 0 for m in moves) / len(moves), 2),
                                  "n": len(moves)})
                else:
                    entry.update({"n": len(moves), "note": "Fewer than 3 past events in the data — no statistics."})
            assets.append(entry)
        themes.append({**th, "assets": assets})
    return {"event": event_id, "name": ev["name"], "when": ev["when"], "themes": themes,
            "data_mode": data_mode,
            "method": ("Relationships are 'associated' (domain knowledge) unless measured. "
                       "'historical' = average close-to-close move from the day before to 3 sessions after "
                       "each past event date. Association is not causation; small samples."),}


def events_for_symbol(symbol: str) -> List[Dict[str, str]]:
    sec = universe.sector_of(symbol)
    out = []
    for k, ev in EVENTS.items():
        for th in ev["themes"]:
            if sec and (sec in th["sectors"] or "*" in th["sectors"]):
                out.append({"event": k, "name": ev["name"], "theme": th["theme"], "sensitivity": th["sensitivity"]})
                break
    return out
