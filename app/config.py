"""
Environment/config for the Flock Energy API wrapper.

All values can be overridden via a `.env` file (see `.env.example`) or real
environment variables. Nothing here should ever be committed with real
credentials filled in.
"""
import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    # Base URL of the legacy Urja Meter Ops portal
    PORTAL_BASE_URL: str = os.getenv("PORTAL_BASE_URL", "https://urja-ops.flockenergy.tech")

    # Credentials for the portal (NOT this API's own auth - see README)
    PORTAL_EMAIL: str = os.getenv("PORTAL_EMAIL", "operator@urja.local")
    PORTAL_PASSWORD: str = os.getenv("PORTAL_PASSWORD", "urja-ops-2026")

    # How long we assume the portal session cookie stays valid before we
    # proactively refresh it. The observed cookie carries Max-Age=3600 (1hr).
    # We refresh a bit earlier than that as a safety margin.
    SESSION_TTL_SECONDS: int = int(os.getenv("SESSION_TTL_SECONDS", "3300"))  # 55 min

    # Default page size when paginating the portal's own list endpoint.
    DEFAULT_PAGE_SIZE: int = int(os.getenv("DEFAULT_PAGE_SIZE", "20"))

    REQUEST_TIMEOUT_SECONDS: float = float(os.getenv("REQUEST_TIMEOUT_SECONDS", "10.0"))


settings = Settings()
