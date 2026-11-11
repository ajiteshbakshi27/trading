"""Shared test setup: isolated SQLite DB, memory state store, offline data."""
import os
import tempfile

_tmp = tempfile.mkdtemp(prefix="parakh-test-")
os.environ.setdefault("DB_PATH", os.path.join(_tmp, "test.db"))
os.environ["REDIS_URL"] = ""
os.environ.setdefault("ENVIRONMENT", "test")
for k in ("SUPABASE_URL", "SUPABASE_JWT_SECRET", "ANTHROPIC_API_KEY", "DATABASE_URL"):
    os.environ.pop(k, None)
