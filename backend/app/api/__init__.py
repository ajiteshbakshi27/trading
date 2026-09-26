"""
QuantPulse AI — Research API routers.

Each router is included by app.main; none of them replaces an existing route.
All responses carry a data_mode block so the UI never has to guess whether it
is looking at live data, a synthetic scenario, a mock, or a backtest.
"""
from app.api import demo, event_transmission, experiments, information, \
    prediction_autopsy, research, thesis

__all__ = ["information", "thesis", "event_transmission", "prediction_autopsy",
           "experiments", "demo", "research"]
