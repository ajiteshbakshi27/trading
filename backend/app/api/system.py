"""Liveness, root and feed-status endpoints."""
from __future__ import annotations
from typing import Dict

from fastapi import APIRouter

from app import database as db
from app.core.runtime import _feed_status, settings, stream_client
from app.quantum_hft import risk_manager

router = APIRouter()


@router.get("/health")
def health():
    """Liveness + readiness. No secrets, ever."""
    return {
        "status": "ok",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
        "halted": risk_manager.is_halted(),
        "db": db.engine_info().get("backend"),
        "feeds": _feed_status(),
    }


@router.get("/")
def root():
    """API root — points to docs and health. The frontend is a separate app."""
    return {
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/docs",
        "health": "/health",
        "snapshot": "/api/snapshot",
        "note": "This is the API backend. The frontend is deployed separately (Vercel).",
    }


@router.get("/api/feeds/status")
def feeds_status():
    """Phase 1: report live vs mock source per feed without changing data shapes."""
    feeds = _feed_status()
    try:
        st = stream_client.status()
        feeds["stream"] = ("live" if st["connected"]
                           else "configured" if st["configured"] else "mock")
    except Exception:
        feeds["stream"] = "mock"
    return {"feeds": feeds}
