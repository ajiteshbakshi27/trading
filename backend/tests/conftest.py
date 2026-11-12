"""Shared test setup: isolated SQLite DB, memory state store, offline data."""
import os
import tempfile

_tmp = tempfile.mkdtemp(prefix="parakh-test-")
os.environ.setdefault("DB_PATH", os.path.join(_tmp, "test.db"))
os.environ["REDIS_URL"] = ""
os.environ.setdefault("ENVIRONMENT", "test")
# Blank (not just unset): an empty env var overrides backend/.env, so tests never
# use the developer's real keys, database or AI quota.
for k in ("SUPABASE_URL", "SUPABASE_ANON_KEY", "SUPABASE_SERVICE_KEY", "SUPABASE_JWT_SECRET",
          "ANTHROPIC_API_KEY", "GEMINI_API_KEY", "DATABASE_URL", "KITE_API_KEY",
          "KITE_API_SECRET", "TELEGRAM_BOT_TOKEN", "REDDIT_CLIENT_ID", "REDDIT_CLIENT_SECRET"):
    os.environ[k] = ""
