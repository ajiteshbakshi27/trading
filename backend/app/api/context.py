"""
QuantPulse AI — Research API context.

Routers read the app-level singletons (HFT manager, sentiment engine,
prediction agent, stream client) from `app.state.research`, which main.py
populates at startup. This keeps the routers free of circular imports and
lets tests inject fakes.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class ResearchContext:
    """Everything the research routers need, resolved once at startup."""

    hft: Any = None
    sent_engine: Any = None
    pred_agent: Any = None
    bet_engine: Any = None
    stream_client: Any = None
    base_prices: Dict[str, float] = field(default_factory=dict)
    extra: Dict[str, Any] = field(default_factory=dict)


def get_ctx(request) -> ResearchContext:
    ctx = getattr(request.app.state, "research", None)
    if ctx is None:
        # Degraded mode: routers still answer, with mock data and honest labels.
        return ResearchContext()
    return ctx
