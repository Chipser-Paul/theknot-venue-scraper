"""Configuration management module.

Loads and validates environment variables from a .env file using python-dotenv,
and defines runtime settings for Crawl4AI and the LLM extraction provider.
"""

import os
from dataclasses import dataclass
from dotenv import load_dotenv

# Load environment variables from .env file if present
load_dotenv()


@dataclass(frozen=True)
class Settings:
    """Application configuration parameters."""

    groq_api_key: str
    llm_provider: str
    default_start_url: str
    default_max_pages: int
    headless: bool
    page_timeout_ms: int
    request_delay_seconds: float
    chunk_token_threshold: int = 1200
    llm_temperature: float = 0.0
    groq_tpm_limit: int = 8000

    @classmethod
    def from_env(cls) -> "Settings":
        """Instantiate and validate Settings from environment variables."""
        api_key = os.getenv("GROQ_API_KEY", "").strip()
        if not api_key or api_key == "your_groq_api_key_here":
            raise ValueError(
                "Missing or placeholder GROQ_API_KEY. "
                "Please copy .env.example to .env and set a valid GROQ_API_KEY."
            )

        return cls(
            groq_api_key=api_key,
            llm_provider=os.getenv(
                "LLM_PROVIDER", "groq/openai/gpt-oss-120b"
            ).strip(),
            default_start_url=os.getenv(
                "DEFAULT_START_URL",
                "https://www.theknot.com/marketplace/wedding-reception-venues-atlanta-ga",
            ).strip(),
            default_max_pages=int(os.getenv("DEFAULT_MAX_PAGES", "3")),
            headless=os.getenv("HEADLESS_BROWSER", "true").lower() in ("true", "1", "yes"),
            page_timeout_ms=int(os.getenv("PAGE_TIMEOUT_MS", "60000")),
            request_delay_seconds=float(os.getenv("REQUEST_DELAY_SECONDS", "20.0")),
            groq_tpm_limit=int(os.getenv("GROQ_TPM_LIMIT", "8000")),
        )
