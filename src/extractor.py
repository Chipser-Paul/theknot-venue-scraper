"""LLM extraction strategy configuration and JSON parsing utilities."""

import json
import logging
import time
from collections import deque
from typing import Deque, List, Tuple

from pydantic import ValidationError
from crawl4ai import LLMConfig, LLMExtractionStrategy
from crawl4ai.utils import sanitize_input_encode

from src.config import Settings
from src.models import ReceptionVenue

logger = logging.getLogger(__name__)

EXTRACTION_INSTRUCTION = """
Extract all wedding reception venue listings from the provided page content.
For each venue card, extract:
- name: Exact name of the venue.
- location: City and state (e.g., 'Atlanta, GA' or 'Decatur, GA').
- price: Starting price string if shown (e.g., 'Starting at $5,000'). If no dollar price is displayed, return null.
- capacity: Guest capacity range if shown (e.g., '151-200 guests' or '300+ guests'). If missing, return null.
- rating: Numerical star rating (e.g., 4.8). If rating is 0 or not shown, return null.
- reviews_count: Integer number of reviews (e.g., 39).
- short_description: Short summary description of the venue from the card.
- source_url: The direct URL to the venue's storefront on The Knot (https://www.theknot.com/marketplace/...).

CRITICAL RULES:
1. NEVER invent, guess, or fabricate missing fields. If a field (like price or rating) is not present on a venue card, set it to null.
2. Ignore navigation menus, category footers, FAQs, and filter sidebars—only extract actual reception venue listings.
3. Respond with a raw JSON array only. Do not wrap the JSON in markdown code fences and do not add commentary before or after it.
""".strip()


class TokenRateLimiter:
    """Sliding-window limiter for Groq's per-minute token quota.

    Groq rejects a request when `prompt_tokens + max_tokens` would push the
    rolling 60-second usage past the tier limit, so every chunk request has to
    be admitted against the budget instead of being fired immediately.
    """

    def __init__(self, tokens_per_minute: int, headroom_tokens: int = 250):
        self.window_seconds = 60.0
        self.budget = max(1, tokens_per_minute - headroom_tokens)
        self._events: Deque[Tuple[float, int]] = deque()

    def _prune(self, now: float) -> None:
        while self._events and now - self._events[0][0] >= self.window_seconds:
            self._events.popleft()

    def used_tokens(self) -> int:
        """Tokens charged inside the current sliding window."""
        self._prune(time.monotonic())
        return sum(tokens for _, tokens in self._events)

    def delay_before(self, estimated_tokens: int) -> float:
        """Seconds to wait so that `estimated_tokens` still fits in the window."""
        now = time.monotonic()
        self._prune(now)
        used = sum(tokens for _, tokens in self._events)
        overflow = used + estimated_tokens - self.budget
        if overflow <= 0:
            return 0.0

        freed = 0
        for timestamp, tokens in self._events:
            freed += tokens
            if freed >= overflow:
                return max(0.0, self.window_seconds - (now - timestamp)) + 0.5
        return self.window_seconds

    def record(self, tokens: int) -> None:
        """Record the tokens actually charged by the provider for one request."""
        self._events.append((time.monotonic(), max(0, tokens)))


class ThrottledLLMExtractionStrategy(LLMExtractionStrategy):
    """`LLMExtractionStrategy` that paces chunk requests to a token budget.

    crawl4ai 0.7.4 fires every chunk as soon as the previous one returns, which
    on Groq's free `on_demand` tier exhausts the 8,000 TPM quota mid-page and
    drops the remaining chunks. This subclass admits each chunk against a
    shared `TokenRateLimiter` and sleeps until the quota has room for it.
    """

    def __init__(
        self,
        *args,
        rate_limiter: TokenRateLimiter,
        prompt_overhead_tokens: int = 800,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.rate_limiter = rate_limiter
        self.prompt_overhead_tokens = prompt_overhead_tokens

    def __setattr__(self, name: str, value: object) -> None:
        """Bypass crawl4ai's deprecated-argument guard.

        `LLMExtractionStrategy.__setattr__` introspects `self.__init__`'s
        signature, which no longer exposes the parent parameters on a subclass
        and raises `KeyError: 'provider'` during construction.
        """
        object.__setattr__(self, name, value)

    def _estimated_request_tokens(self, payload: str) -> int:
        """Approximate Groq's admission estimate: prompt + reserved completion."""
        prompt_tokens = len(payload) // 4 + self.prompt_overhead_tokens
        return prompt_tokens + int(self.extra_args.get("max_tokens", 0))

    def run(self, url: str, sections: List[str]) -> List[dict]:
        merged_sections = self._merge(
            sections,
            self.chunk_token_threshold,
            overlap=int(self.chunk_token_threshold * self.overlap_rate),
        )
        inserted_content: List[dict] = []

        for index, section in enumerate(merged_sections):
            payload = sanitize_input_encode(section)
            delay = self.rate_limiter.delay_before(
                self._estimated_request_tokens(payload)
            )
            if delay > 0:
                logger.info(
                    "Groq TPM budget reached; waiting %.1fs before chunk %d/%d of %s.",
                    delay,
                    index + 1,
                    len(merged_sections),
                    url,
                )
                time.sleep(delay)

            usages_before = len(self.usages)
            inserted_content.extend(self.extract(url, index, payload))
            if len(self.usages) > usages_before:
                self.rate_limiter.record(self.usages[-1].total_tokens)
            else:
                self.rate_limiter.record(self._estimated_request_tokens(payload))

        return inserted_content


def build_llm_extraction_strategy(
    settings: Settings, rate_limiter: TokenRateLimiter
) -> LLMExtractionStrategy:
    """Create a Crawl4AI LLMExtractionStrategy backed by Groq and Pydantic."""
    llm_config = LLMConfig(
        provider=settings.llm_provider,
        api_token=settings.groq_api_key,
    )

    return ThrottledLLMExtractionStrategy(
        llm_config=llm_config,
        rate_limiter=rate_limiter,
        schema=ReceptionVenue.get_json_schema(),
        extraction_type="schema",
        instruction=EXTRACTION_INSTRUCTION,
        chunk_token_threshold=settings.chunk_token_threshold,
        overlap_rate=0.0,
        apply_chunking=True,
        # Send the pruned `fit_markdown` (PruningContentFilter output) rather than
        # raw Markdown, which keeps every request far below Groq's 8,000 TPM limit.
        input_format="fit_markdown",
        extra_args={
            "temperature": settings.llm_temperature,
            # `openai/gpt-oss-120b` is a reasoning model: its reasoning tokens are
            # billed inside max_tokens. With the default effort it spends the whole
            # 2,048-token budget thinking and returns truncated JSON, so ask for low
            # effort and a slightly larger budget (3,072 + prompt still < 8,000 TPM).
            "max_tokens": 3072,
            "extra_body": {"reasoning_effort": "low"},
        },
        verbose=False,
    )


def parse_extracted_venues(
    raw_extracted_content: str, fallback_page_url: str
) -> List[ReceptionVenue]:
    """Parse and validate the JSON string returned by Crawl4AI's LLMExtractionStrategy."""
    if not raw_extracted_content or not raw_extracted_content.strip():
        logger.warning("Empty extracted_content returned for %s", fallback_page_url)
        return []

    try:
        payload = json.loads(raw_extracted_content)
    except json.JSONDecodeError as exc:
        logger.error("Failed to decode LLM JSON output on %s: %s", fallback_page_url, exc)
        return []

    if isinstance(payload, dict):
        # Handle cases where the LLM wraps the list inside a key like {"venues": [...]}
        items = (
            payload.get("venues")
            or payload.get("items")
            or payload.get("results")
            or [payload]
        )
    elif isinstance(payload, list):
        items = payload
    else:
        logger.warning("Unexpected JSON structure from LLM: %s", type(payload))
        return []

    validated_venues: List[ReceptionVenue] = []
    for raw_item in items:
        if not isinstance(raw_item, dict):
            continue
        if raw_item.get("error") is True:
            logger.warning("Skipping chunk with LLM error flag: %s", raw_item)
            continue
        if not raw_item.get("source_url"):
            raw_item["source_url"] = fallback_page_url
        try:
            venue = ReceptionVenue.validate_record(raw_item)
            validated_venues.append(venue)
        except ValidationError as val_err:
            logger.debug("Skipping invalid venue record %s: %s", raw_item, val_err)

    return validated_venues
