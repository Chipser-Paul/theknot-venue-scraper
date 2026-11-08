"""CLI entry point for The Knot Wedding Reception Venues Scraper."""

import argparse
import asyncio
import logging
import sys
import warnings
from pathlib import Path

# Python 3.13 + requests emits a noisy RequestsDependencyWarning at import time.
warnings.filterwarnings("ignore", message=".*urllib3.*or chardet.*")

# litellm==1.63.11 prints internal debug info (and, on Python 3.13, an
# AttributeError: __annotations__ traceback from its logging helpers) even when
# every API call succeeds. Keep the console output clean.
import litellm  # noqa: E402

litellm.suppress_debug_info = True
litellm.set_verbose = False

from src.config import Settings  # noqa: E402
from src.crawler import crawl_venues  # noqa: E402
from src.exporter import export_venues_to_csv  # noqa: E402


NOISY_LOGGERS = ("LiteLLM", "litellm", "httpx", "httpcore")


def configure_logging(verbose: bool = False) -> None:
    """Configure structured console logging."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    for noisy_logger in NOISY_LOGGERS:
        logging.getLogger(noisy_logger).setLevel(logging.CRITICAL)


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Extract wedding reception venues from The Knot using Crawl4AI and Groq LLM."
    )
    parser.add_argument(
        "--url",
        type=str,
        default=None,
        help="Starting URL on The Knot marketplace (defaults to DEFAULT_START_URL in .env).",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=None,
        help="Maximum number of paginated listing pages to crawl (default: 2).",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="data/venues_atlanta.csv",
        help="Output CSV file path (default: data/venues_atlanta.csv).",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable debug logging.",
    )
    return parser.parse_args()


async def run_pipeline() -> int:
    """Run the end-to-end crawl, LLM extraction, deduplication, and CSV export."""
    args = parse_args()
    configure_logging(args.verbose)
    logger = logging.getLogger("main")

    try:
        settings = Settings.from_env()
    except ValueError as err:
        logger.error("Configuration error: %s", err)
        return 1

    start_url = args.url or settings.default_start_url
    max_pages = args.max_pages if args.max_pages is not None else settings.default_max_pages
    if max_pages < 1:
        logger.error("--max-pages must be at least 1.")
        return 1

    logger.info(
        "Starting venue extraction pipeline | url=%s | max_pages=%d | model=%s",
        start_url,
        max_pages,
        settings.llm_provider,
    )

    raw_venues, summaries = await crawl_venues(
        start_url=start_url,
        max_pages=max_pages,
        settings=settings,
    )

    total_raw = len(raw_venues)
    unique_count = export_venues_to_csv(raw_venues, Path(args.output))

    logger.info("--- Execution Summary ---")
    for s in summaries:
        status_label = "OK" if s.success else ("RESTRICTED" if s.blocked_or_restricted else "FAILED")
        logger.info(
            "Page %d: [%s] HTTP=%s | Extracted=%d | URL=%s %s",
            s.page_number,
            status_label,
            s.status_code or "N/A",
            s.venues_extracted,
            s.url,
            f"| Note: {s.error_message}" if s.error_message else "",
        )
    logger.info(
        "Total raw records: %d | Deduplicated exported records: %d | Output CSV: %s",
        total_raw,
        unique_count,
        args.output,
    )

    return 0 if unique_count > 0 else 2


if __name__ == "__main__":
    sys.exit(asyncio.run(run_pipeline()))
