"""Page retrieval and pagination orchestration using Crawl4AI."""

import asyncio
import logging
from dataclasses import dataclass
from typing import List, Optional
from urllib.parse import urlencode, urlparse, parse_qs, urlunparse

from crawl4ai import (
    AsyncWebCrawler,
    BrowserConfig,
    CrawlerRunConfig,
    CacheMode,
    DefaultMarkdownGenerator,
    PruningContentFilter,
)

from src.config import Settings
from src.extractor import (
    TokenRateLimiter,
    build_llm_extraction_strategy,
    parse_extracted_venues,
)
from src.models import ReceptionVenue

logger = logging.getLogger(__name__)

ANTI_BOT_MARKERS = (
    "access denied",
    "px-captcha",
    "perimeterx",
    "cloudflare",
    "verify you are human",
    "please enable cookies",
)


@dataclass
class PageCrawlSummary:
    """Diagnostic summary for a single crawled page."""

    page_number: int
    url: str
    success: bool
    status_code: Optional[int]
    venues_extracted: int
    blocked_or_restricted: bool = False
    error_message: Optional[str] = None


def build_paginated_url(base_url: str, page_number: int) -> str:
    """Construct a paginated URL for The Knot marketplace (`?page=N`)."""
    if page_number <= 1:
        return base_url
    parsed = urlparse(base_url)
    query_params = parse_qs(parsed.query)
    query_params["page"] = [str(page_number)]
    new_query = urlencode(query_params, doseq=True)
    return urlunparse(parsed._replace(query=new_query))


def detect_access_restriction(
    status_code: Optional[int], html_or_markdown: str, error_msg: Optional[str]
) -> Optional[str]:
    """Check whether the target site returned an anti-bot challenge or HTTP block.

    Per project guidelines, access restrictions are documented cleanly rather than
    aggressively circumvented.
    """
    if status_code in (401, 403, 429, 503):
        return f"HTTP {status_code} access restriction returned by server."

    combined = f"{html_or_markdown or ''} {error_msg or ''}".lower()
    for marker in ANTI_BOT_MARKERS:
        if marker in combined and len(html_or_markdown or "") < 8000:
            return f"Anti-bot protection detected (marker: '{marker}')."

    return None


async def crawl_venues(
    start_url: str, max_pages: int, settings: Settings
) -> tuple[List[ReceptionVenue], List[PageCrawlSummary]]:
    """Crawl up to `max_pages` starting from `start_url` and extract unique venues."""
    # NOTE: `enable_stealth=True` is intentionally NOT used. In crawl4ai==0.7.4 it
    # crashes with `ImportError: cannot import name 'Stealth' from 'playwright_stealth'`.
    browser_config = BrowserConfig(
        browser_type="chromium",
        headless=settings.headless,
        viewport_width=1280,
        viewport_height=800,
        text_mode=True,
        verbose=False,
    )

    # Strip image URLs (10 carousel images per venue card) and boilerplate before
    # Markdown generation so the LLM receives the pruned `fit_markdown` payload.
    markdown_generator = DefaultMarkdownGenerator(
        content_filter=PruningContentFilter(threshold=0.45, threshold_type="fixed"),
        options={"ignore_images": True},
    )

    rate_limiter = TokenRateLimiter(settings.groq_tpm_limit)
    llm_strategy = build_llm_extraction_strategy(settings, rate_limiter)

    run_config = CrawlerRunConfig(
        cache_mode=CacheMode.BYPASS,
        extraction_strategy=llm_strategy,
        markdown_generator=markdown_generator,
        word_count_threshold=15,
        page_timeout=settings.page_timeout_ms,
        wait_until="domcontentloaded",
        delay_before_return_html=2.0,
        remove_overlay_elements=True,
        exclude_external_links=True,
        exclude_social_media_links=True,
        excluded_tags=[
            "nav",
            "header",
            "footer",
            "aside",
            "form",
            "script",
            "style",
            "noscript",
            "svg",
        ],
        verbose=False,
    )

    all_venues: List[ReceptionVenue] = []
    summaries: List[PageCrawlSummary] = []

    async with AsyncWebCrawler(config=browser_config) as crawler:
        for page_num in range(1, max_pages + 1):
            target_url = build_paginated_url(start_url, page_num)
            logger.info("Crawling page %d/%d: %s", page_num, max_pages, target_url)

            try:
                result = await crawler.arun(url=target_url, config=run_config)
            except Exception as exc:
                err_text = f"Unhandled crawler exception: {exc}"
                logger.error("Page %d failed: %s", page_num, err_text)
                summaries.append(
                    PageCrawlSummary(
                        page_number=page_num,
                        url=target_url,
                        success=False,
                        status_code=None,
                        venues_extracted=0,
                        error_message=err_text,
                    )
                )
                continue

            status_code = getattr(result, "status_code", None)
            raw_md = ""
            if getattr(result, "markdown", None):
                raw_md = (
                    result.markdown.raw_markdown
                    if hasattr(result.markdown, "raw_markdown")
                    else str(result.markdown)
                )

            restriction_reason = detect_access_restriction(
                status_code, raw_md, getattr(result, "error_message", None)
            )
            if restriction_reason:
                logger.warning(
                    "Access restricted on page %d (%s): %s. "
                    "Documenting block and stopping pagination gracefully.",
                    page_num,
                    target_url,
                    restriction_reason,
                )
                summaries.append(
                    PageCrawlSummary(
                        page_number=page_num,
                        url=target_url,
                        success=False,
                        status_code=status_code,
                        venues_extracted=0,
                        blocked_or_restricted=True,
                        error_message=restriction_reason,
                    )
                )
                break

            if not result.success:
                err_msg = getattr(result, "error_message", "Unknown crawl failure")
                logger.warning("Page %d crawl unsuccessful: %s", page_num, err_msg)
                summaries.append(
                    PageCrawlSummary(
                        page_number=page_num,
                        url=target_url,
                        success=False,
                        status_code=status_code,
                        venues_extracted=0,
                        error_message=err_msg,
                    )
                )
                continue

            page_venues = parse_extracted_venues(
                result.extracted_content, fallback_page_url=target_url
            )
            logger.info(
                "Page %d complete (HTTP %s): extracted %d valid venue records.",
                page_num,
                status_code or 200,
                len(page_venues),
            )
            all_venues.extend(page_venues)
            summaries.append(
                PageCrawlSummary(
                    page_number=page_num,
                    url=target_url,
                    success=True,
                    status_code=status_code or 200,
                    venues_extracted=len(page_venues),
                )
            )

            # Groq's on_demand tier meters 8,000 tokens/minute, so pause between
            # pages to let the rolling 60-second TPM bucket refill.
            if page_num < max_pages and settings.request_delay_seconds > 0:
                logger.info(
                    "Waiting %.1fs for the Groq TPM bucket to refill before page %d.",
                    settings.request_delay_seconds,
                    page_num + 1,
                )
                await asyncio.sleep(settings.request_delay_seconds)

    return all_venues, summaries
