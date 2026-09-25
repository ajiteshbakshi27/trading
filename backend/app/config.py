"""
QuantPulse AI - Configuration Management
Centralized configuration with environment variable support and secure defaults.
"""
import os
from functools import lru_cache
from typing import Optional, List, Dict, Annotated
from pydantic_settings import BaseSettings, NoDecode
from pydantic import Field, field_validator


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # App Settings
    APP_NAME: str = "QuantPulse AI"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = Field(default=False, description="Enable debug mode")
    ENVIRONMENT: str = Field(default="development", description="Environment: development, staging, production")

    # API Keys - Financial Data
    ALPACA_API_KEY: Optional[str] = Field(default=None, description="Alpaca API key for paper/live trading")
    ALPACA_SECRET_KEY: Optional[str] = Field(default=None, description="Alpaca secret key")
    # Deprecated aliases (Gemini spec typo ALPACAS_*): honored as fallback only.
    ALPACAS_API_KEY: Optional[str] = Field(default=None, description="Deprecated alias of ALPACA_API_KEY")
    ALPACAS_SECRET_KEY: Optional[str] = Field(default=None, description="Deprecated alias of ALPACA_SECRET_KEY")
    ALPACA_BASE_URL: str = Field(default="https://paper-api.alpaca.markets", description="Alpaca base URL (paper vs live)")
    # Real-time data websocket (free IEX feed; "sip" needs a paid plan)
    ALPACA_DATA_FEED: str = Field(default="iex", description="Alpaca data feed: iex or sip")
    STREAM_MAX_AGE_S: float = Field(default=5.0, description="Tick freshness threshold seconds")
    # Generic market-data provider (Alpha Vantage / FMP / Polygon.io)
    FINANCIAL_DATA_API_KEY: Optional[str] = Field(default=None, description="Alpha Vantage / FMP / Polygon.io key")
    FINANCIAL_DATA_PROVIDER: str = Field(default="alphavantage", description="Market data provider name")

    # API Keys - Social Sentiment
    REDDIT_CLIENT_ID: Optional[str] = Field(default=None, description="Reddit API client ID")
    REDDIT_CLIENT_SECRET: Optional[str] = Field(default=None, description="Reddit API client secret")
    REDDIT_USER_AGENT: str = Field(default="QuantPulse AI Sentiment Bot v1.0", description="Reddit user agent")
    TWITTER_BEARER_TOKEN: Optional[str] = Field(default=None, description="Twitter API v2 Bearer Token")
    TWITTER_API_KEY: Optional[str] = Field(default=None, description="Twitter API key")
    TWITTER_API_SECRET: Optional[str] = Field(default=None, description="Twitter API secret")
    TWITTER_ACCESS_TOKEN: Optional[str] = Field(default=None, description="Twitter access token")
    TWITTER_ACCESS_SECRET: Optional[str] = Field(default=None, description="Twitter access secret")

    # Prediction Markets
    POLYMARKET_API_KEY: Optional[str] = Field(default=None, description="Polymarket API key")
    KALSHI_API_KEY: Optional[str] = Field(default=None, description="Kalshi API key")
    KALSHI_PRIVATE_KEY: Optional[str] = Field(default=None, description="Kalshi private key")

    # Alerts (Telegram / Discord)
    TELEGRAM_BOT_TOKEN: Optional[str] = Field(default=None, description="Telegram bot token")
    TELEGRAM_CHAT_ID: Optional[str] = Field(default=None, description="Telegram chat ID for alerts")
    DISCORD_WEBHOOK_URL: Optional[str] = Field(default=None, description="Discord webhook URL")

    # AI Copilot (optional external LLM; rule-based engine is built in)
    COPILOT_LLM_URL: Optional[str] = Field(default=None, description="Optional LLM chat endpoint")
    COPILOT_LLM_KEY: Optional[str] = Field(default=None, description="Optional LLM API key")

    # Risk kill-switch
    KILL_SWITCH_DRAWNDOWN_PCT: float = Field(default=5.0, description="Auto-halt drawdown threshold %")

    # Cost model (pre-trade estimates; flat, currency-agnostic)
    FEE_RATE: float = Field(default=0.0005, description="Brokerage rate on notional")
    FEE_MIN: float = Field(default=1.0, description="Minimum fee per order")
    TAX_RATE_GAINS: float = Field(default=0.15, description="Capital-gains tax proxy on profits")

    # Alpha Vantage guards (free tier: 5 calls/min, 25 calls/day)
    AV_CACHE_TTL_S: int = Field(default=60, description="Quote/candle cache TTL seconds")
    AV_MAX_DAILY_CALLS: int = Field(default=20, description="Daily Alpha Vantage call budget")

    # Database & Cache
    REDIS_URL: str = Field(default="redis://localhost:6379/0", description="Redis connection URL")
    DATABASE_URL: Optional[str] = Field(default=None, description="PostgreSQL connection URL (Supabase)")
    SUPABASE_URL: Optional[str] = Field(default=None, description="Supabase project URL")
    SUPABASE_ANON_KEY: Optional[str] = Field(default=None, description="Supabase anon public key")
    SUPABASE_SERVICE_KEY: Optional[str] = Field(default=None, description="Supabase service role key (server only)")
    DB_PATH: str = Field(default="quantpulse.db", description="SQLite file when DATABASE_URL is unset")

    # Quantum Computing
    PENNYLANE_DEVICE: str = Field(default="default.qubit", description="PennyLane device (default.qubit, lightning.qubit)")
    QISKIT_BACKEND: str = Field(default="aer_simulator", description="Qiskit backend")

    # HFT Engine Settings
    HFT_TICK_INTERVAL_MS: int = Field(default=100, description="HFT simulation tick interval in milliseconds")
    HFT_MAX_ORDER_BOOK_DEPTH: int = Field(default=20, description="Max order book depth levels")
    HFT_OFI_WINDOW_SIZE: int = Field(default=100, description="Order Flow Imbalance calculation window")

    # WebSocket Settings
    WS_HEARTBEAT_INTERVAL: int = Field(default=30, description="WebSocket heartbeat interval in seconds")
    WS_MAX_CONNECTIONS: int = Field(default=1000, description="Max concurrent WebSocket connections")

    # Backtesting
    BACKTEST_INITIAL_CAPITAL: float = Field(default=100000.0, description="Initial capital for backtesting")
    BACKTEST_COMMISSION: float = Field(default=0.001, description="Commission rate (0.1%)")
    BACKTEST_SLIPPAGE: float = Field(default=0.0005, description="Slippage rate (0.05%)")

    # Risk Management
    MAX_POSITION_SIZE: float = Field(default=0.1, description="Max position size as fraction of portfolio")
    MAX_DAILY_LOSS: float = Field(default=0.02, description="Max daily loss limit (2%)")
    VAR_CONFIDENCE_LEVEL: float = Field(default=0.95, description="VaR confidence level")

    # Logging
    LOG_LEVEL: str = Field(default="INFO", description="Logging level")
    LOG_FORMAT: str = Field(default="json", description="Log format: json or console")

    # CORS
    CORS_ORIGINS: Annotated[List[str], NoDecode] = Field(
        default=["http://localhost:3000", "http://127.0.0.1:3000"],
        description="Allowed CORS origins (JSON list or comma-separated)"
    )

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def _split_cors(cls, v):
        # Render/Vercel: allow CORS_ORIGINS=https://app.vercel.app,https://x
        if isinstance(v, str):
            s = v.strip()
            if s.startswith("["):
                import json
                try:
                    return json.loads(s)
                except Exception:
                    pass
            return [o.strip() for o in s.split(",") if o.strip()]
        return v

    class Config:
        env_file = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", ".env")
        env_file_encoding = "utf-8"
        case_sensitive = True

    @field_validator(
        "ALPACA_API_KEY", "ALPACA_SECRET_KEY", "ALPACAS_API_KEY", "ALPACAS_SECRET_KEY",
        "FINANCIAL_DATA_API_KEY", "REDDIT_CLIENT_ID", "REDDIT_CLIENT_SECRET",
        "TWITTER_BEARER_TOKEN", "TWITTER_API_KEY", "TWITTER_API_SECRET",
        "TWITTER_ACCESS_TOKEN", "TWITTER_ACCESS_SECRET", "POLYMARKET_API_KEY",
        "KALSHI_API_KEY", "KALSHI_PRIVATE_KEY", "DATABASE_URL", "SUPABASE_URL",
        "SUPABASE_ANON_KEY", "SUPABASE_SERVICE_KEY", "TELEGRAM_BOT_TOKEN",
        "TELEGRAM_CHAT_ID", "DISCORD_WEBHOOK_URL", "COPILOT_LLM_URL", "COPILOT_LLM_KEY",
        mode="before",
    )
    @classmethod
    def _empty_to_none(cls, v):
        # Treat "" / whitespace in .env as missing so mock fallback triggers.
        if isinstance(v, str) and not v.strip():
            return None
        return v

    # ---- Resolved credentials (canonical + deprecated alias fallback) ----
    @property
    def alpaca_key(self) -> Optional[str]:
        return self.ALPACA_API_KEY or self.ALPACAS_API_KEY or None

    @property
    def alpaca_secret(self) -> Optional[str]:
        return self.ALPACA_SECRET_KEY or self.ALPACAS_SECRET_KEY or None

    # ---- Presence flags: falsy (None/"") means mock fallback ----
    @property
    def has_alpaca(self) -> bool:
        return bool(self.alpaca_key and self.alpaca_secret)

    @property
    def has_financial_data(self) -> bool:
        return bool(self.FINANCIAL_DATA_API_KEY)

    @property
    def has_reddit(self) -> bool:
        return bool(self.REDDIT_CLIENT_ID and self.REDDIT_CLIENT_SECRET)

    @property
    def has_twitter(self) -> bool:
        return bool(self.TWITTER_BEARER_TOKEN)

    @property
    def has_supabase(self) -> bool:
        return bool(self.SUPABASE_URL and (self.SUPABASE_ANON_KEY or self.SUPABASE_SERVICE_KEY))

    @property
    def has_alerts(self) -> bool:
        return bool((self.TELEGRAM_BOT_TOKEN and self.TELEGRAM_CHAT_ID)
                    or self.DISCORD_WEBHOOK_URL)

    def feed_status(self) -> Dict[str, str]:
        """Live vs mock source per feed. HFT book stays a simulator in Phase 1."""
        return {
            "hft_orderbook": "mock_simulator",
            "alpaca_trading": "live" if self.has_alpaca else "mock",
            "market_data": "live" if (self.has_alpaca or self.has_financial_data) else "mock",
            "reddit": "live" if self.has_reddit else "mock",
            "twitter": "live" if self.has_twitter else "mock",
            "prediction": "live" if (self.KALSHI_API_KEY or self.POLYMARKET_API_KEY) else "mock",
            "supabase": "live" if self.has_supabase else "mock",
            "alerts": "live" if self.has_alerts else "mock",
        }


@lru_cache()
def get_settings() -> Settings:
    """Cached settings instance for dependency injection."""
    return Settings()


# Mock Data Configuration (for development without API keys)
MOCK_DATA_CONFIG = {
    "enable_mock_hft": True,
    "enable_mock_social": True,
    "enable_mock_prediction": True,
    "mock_tickers": ["AAPL", "MSFT", "NVDA", "TSLA", "GOOGL", "META", "AMD", "INTC"],
    "mock_update_interval_ms": 500,
    "mock_order_book_levels": 10,
    "mock_spread_bps": 5,
}