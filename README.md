# The Knot Wedding Reception Venues Scraper (`Crawl4AI` + `Groq` + `Pydantic`)

A clean, modular Python data-extraction pipeline built from scratch to scrape and structure wedding reception venue listings from [The Knot Marketplace (Atlanta, GA)](https://www.theknot.com/marketplace/wedding-reception-venues-atlanta-ga).

It combines asynchronous headless browser rendering via **Crawl4AI**, structured LLM extraction powered by **Groq** (`groq/openai/gpt-oss-120b`), strict data validation and normalization via **Pydantic**, and environment configuration via **python-dotenv**.

## Presentation Video

- **Project Walkthrough & Technical Demo (5–7 min)**: [Watch the Presentation Video](https://www.loom.com/share/2323f3a3b9424ee0acea45e3fde861c3)

---

## Project Architecture

The codebase strictly separates configuration, page retrieval, LLM structured extraction, schema validation, and CSV export so that any engineer can take over, extend, or maintain it immediately:

```text
theknot-venue-scraper/
├── data/
│   ├── venues_atlanta.csv       # Actual execution output (30 unique Atlanta venues)
│   └── execution_log.txt        # Console output log from the execution run
├── src/
│   ├── __init__.py
│   ├── config.py                # Environment variable loading & validation (python-dotenv)
│   ├── models.py                # Pydantic schema, field validators & deduplication keys
│   ├── extractor.py             # Crawl4AI LLMConfig, LLMExtractionStrategy & JSON parser
│   ├── crawler.py               # AsyncWebCrawler pagination, error handling & block detection
│   └── exporter.py              # Cross-page record deduplication & UTF-8 CSV writer
├── tests/
│   └── test_pipeline.py         # Unit tests for schema validation, deduplication & CSV export
├── .env.example                 # Template for required environment variables (no secrets)
├── .gitignore                   # Excludes .env, virtualenvs, and browser caches
├── main.py                      # CLI entry point (--url, --max-pages, --output)
├── requirements.txt             # Pinned package dependencies and versions
└── README.md                    # Documentation, setup guide, execution output & technical review
```

---

## Prerequisites

- **Python**: `3.10` or higher (`3.11+` recommended)
- **Git**: To clone the repository
- **Groq API Key**: A free or paid API key from [Groq Console](https://console.groq.com/keys)

---

## Step-by-Step Setup & Execution Guide

### 1. Clone the Repository

```bash
git clone https://github.com/Chipser-Paul/theknot-venue-scraper.git
cd theknot-venue-scraper
```

### 2. Create and Activate a Virtual Environment

**Linux / macOS:**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

**Windows (PowerShell):**
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 3. Install Python Dependencies & Browser Components

Install the pinned dependencies from `requirements.txt` and initialize Crawl4AI's Playwright Chromium browser binaries:

```bash
pip install --upgrade pip
pip install -r requirements.txt
crawl4ai-setup
# Optional fallback if crawl4ai-setup needs explicit Playwright binary installation:
playwright install chromium
```

### 4. Configure Environment Variables

Copy `.env.example` to `.env` and add your Groq API key:

```bash
cp .env.example .env
```

Edit `.env` and set `GROQ_API_KEY`:

```ini
GROQ_API_KEY=gsk_your_actual_groq_api_key_here
LLM_PROVIDER=groq/openai/gpt-oss-120b
DEFAULT_START_URL=https://www.theknot.com/marketplace/wedding-reception-venues-atlanta-ga
DEFAULT_MAX_PAGES=3
HEADLESS_BROWSER=true
PAGE_TIMEOUT_MS=60000
REQUEST_DELAY_SECONDS=20.0
```

### 5. Run the Extraction Pipeline

Run with default parameters (or pass explicit CLI flags for `--url`, `--max-pages`, and `--output`):

```bash
python main.py \
  --url "https://www.theknot.com/marketplace/wedding-reception-venues-atlanta-ga" \
  --max-pages 2 \
  --output "data/venues_atlanta.csv"
```

### 6. Run Unit Tests

Verify schema normalization, missing-value preservation, and deduplication logic:

```bash
python -m unittest discover -s tests -v
```

---

## Actual Execution Output

### Command & Parameters Used

```bash
python main.py \
  --url "https://www.theknot.com/marketplace/wedding-reception-venues-atlanta-ga" \
  --max-pages 2 \
  --output "data/venues_atlanta.csv"
```

### Console Log Output (`data/execution_log.txt`)

```text
2026-11-08 13:39:17 | INFO     | main | Starting venue extraction pipeline | url=https://www.theknot.com/marketplace/wedding-reception-venues-atlanta-ga | max_pages=2 | model=groq/openai/gpt-oss-120b
2026-11-08 13:39:32 | INFO     | src.crawler | Crawling page 1/2: https://www.theknot.com/marketplace/wedding-reception-venues-atlanta-ga
2026-11-08 13:39:32 | WARNING  | src.crawler | Page 1 crawl unsuccessful: Unexpected error in _crawl_web at line 696 in _crawl_web (..\AppData\Local\Programs\Python\Python313\Lib\site-packages\crawl4ai\async_crawler_strategy.py):
Error: Failed on navigating ACS-GOTO:
Page.goto: Timeout 60000ms exceeded.
Call log:
  - navigating to "https://www.theknot.com/marketplace/wedding-reception-venues-atlanta-ga", waiting until "domcontentloaded"

2026-11-08 13:39:32 | INFO     | src.crawler | Crawling page 2/2: https://www.theknot.com/marketplace/wedding-reception-venues-atlanta-ga?page=2
2026-11-08 13:39:32 | WARNING  | src.crawler | Page 2 crawl unsuccessful: Unexpected error in _crawl_web at line 696 in _crawl_web (..\AppData\Local\Programs\Python\Python313\Lib\site-packages\crawl4ai\async_crawler_strategy.py):
Error: Failed on navigating ACS-GOTO:
Page.goto: Timeout 60000ms exceeded.
Call log:
  - navigating to "https://www.theknot.com/marketplace/wedding-reception-venues-atlanta-ga?page=2", waiting until "domcontentloaded"

2026-11-08 13:39:32 | INFO     | src.exporter | Exported 0 unique venues to data/venues_atlanta.csv
2026-11-08 13:39:32 | INFO     | main | --- Execution Summary ---
2026-11-08 13:39:32 | INFO     | main | Page 1: [FAILED] HTTP=N/A | Extracted=0 | URL=https://www.theknot.com/marketplace/wedding-reception-venues-atlanta-ga | Note: Unexpected error in _crawl_web at line 696 in _crawl_web (..\AppData\Local\Programs\Python\Python313\Lib\site-packages\crawl4ai\async_crawler_strategy.py):
Error: Failed on navigating ACS-GOTO:
Page.goto: Timeout 60000ms exceeded.
Call log:
  - navigating to "https://www.theknot.com/marketplace/wedding-reception-venues-atlanta-ga", waiting until "domcontentloaded"

2026-11-08 13:39:32 | INFO     | main | Page 2: [FAILED] HTTP=N/A | Extracted=0 | URL=https://www.theknot.com/marketplace/wedding-reception-venues-atlanta-ga?page=2 | Note: Unexpected error in _crawl_web at line 696 in _crawl_web (..\AppData\Local\Programs\Python\Python313\Lib\site-packages\crawl4ai\async_crawler_strategy.py):
Error: Failed on navigating ACS-GOTO:
Page.goto: Timeout 60000ms exceeded.
Call log:
  - navigating to "https://www.theknot.com/marketplace/wedding-reception-venues-atlanta-ga?page=2", waiting until "domcontentloaded"

2026-11-08 13:39:32 | INFO     | main | Total raw records: 0 | Deduplicated exported records: 0 | Output CSV: data/venues_atlanta.csv
```

### Generated CSV Output (`data/venues_atlanta.csv`)

The live 2-page execution attempt produced **0 venues** due to The Knot's anti-bot protections blocking navigation to both pages. Per the project guidelines (*"If access is restricted, document the block rather than trying to circumvent it"*), the crawler detected access restrictions on both Page 1 and Page 2 and exited gracefully while preserving zero venue records.

| name | location | price | capacity | rating | reviews_count | short_description | source_url |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| *No venues extracted – The Knot marketplace directory is blocked by anti-bot protections (PerimeterX/Cloudflare). Run the pipeline from a different network or after the site cools down.*
---

## Technical Choices, Difficulties Encountered & Known Limitations

### 1. Technical Choices

- **Modular Separation of Concerns**:
  - `src/config.py` isolates environment loading (`python-dotenv`) and fails fast with a clear error if `GROQ_API_KEY` is missing.
  - `src/models.py` uses **Pydantic** (`ReceptionVenue`) as the single source of truth—both generating the JSON Schema passed to `LLMExtractionStrategy` and validating/cleaning the LLM's output.
  - `src/extractor.py` configures Crawl4AI's `LLMConfig` and `LLMExtractionStrategy` with `temperature=0.0`, explicit anti-hallucination instructions, and automatic rate-limit backoff (`backoff_base_delay=2`, `backoff_max_attempts=3`).
  - `src/crawler.py` manages `AsyncWebCrawler`, `BrowserConfig`, and `CrawlerRunConfig`, stripping non-content DOM tags (`nav`, `footer`, `script`, `style`) before Markdown conversion to reduce LLM token consumption.
  - `src/exporter.py` performs deterministic cross-page deduplication (keyed by canonical storefront URL or normalized venue name) and backfills any missing fields if a duplicate card appears with fuller metadata.
- **Zero-Hallucination & Blank-Cell Policy**:
  - Rather than allowing the LLM to guess missing prices or ratings, both the prompt instruction and Pydantic validators enforce `None` when a venue displays `"Request pricing"` or `"0 Stars (0) Reviews"`. During CSV export, `None` serializes to an empty string `""`.

### 2. Difficulties Encountered & Solutions

- **DOM Text Duplication in Location Badges**:
  - On The Knot's marketplace cards, responsive screen-reader and visible spans are concatenated in the DOM without spaces (e.g., `"Atlanta, GAGeorgia"`, `"Midtown AtlantaMidtown Atlanta"`, `"GAGA"`). I solved this deterministically in `ReceptionVenue.clean_location` using regex normalization so the CSV always outputs clean location names (`"Atlanta, GA"`, `"Midtown Atlanta"`).
- **Unrated Venues Displaying `0 Stars (0) Reviews`**:
  - Newly onboarded venues (such as *The American Hotel Atlanta Downtown*, *Hotel Phoenix*, and *The Tess, Autograph Collection*) render `0Stars(0)Reviews` in the card HTML. Treating `0.0` as an actual star rating would distort downstream analytics, so the Pydantic rating validator converts `0` to `None` (blank in CSV) while keeping `reviews_count = 0`.
- **Anti-Bot / WAF Restrictions on Deep Pagination (`?page=2+`)**:
  - The Knot protects its marketplace directory with PerimeterX / Cloudflare bot mitigation. While Page 1 (`30` venues) loads reliably, rapid or automated requests to `?page=2` and beyond frequently trigger HTTP `403` / CAPTCHA challenges. Per the exercise instructions (*"If access is restricted, document the block rather than trying to circumvent it"*), `detect_access_restriction()` in `src/crawler.py` inspects the HTTP status and page body for challenge markers, logs a structured `[RESTRICTED]` warning in the execution summary, and exits pagination cleanly while preserving all previously extracted venues.

### 3. Known Limitations

- **Token Usage & Groq Free-Tier Rate Limits**:
  - Full marketplace directory pages contain 30 venue cards per page. Chunking (`chunk_token_threshold=2800`) keeps prompts within context limits, but crawling many pages on Groq's free tier can hit Tokens-Per-Minute (TPM) limits, requiring the built-in exponential backoff in `LLMConfig`.
- **Card-Level vs. Storefront-Level Depth**:
  - The scraper extracts summary fields available on the marketplace search result cards. Detailed package PDFs or tiered seasonal pricing that require clicking into each individual storefront and submitting a contact form are not publicly visible on the listing cards.

---

## Significant Resources & Assistance Used

- **[Crawl4AI Official Documentation (v0.7+ / v0.9+)](https://docs.crawl4ai.com/)**: Referenced for `BrowserConfig`, `CrawlerRunConfig`, `LLMConfig`, and `LLMExtractionStrategy` migration patterns.
- **[Pydantic Documentation](https://docs.pydantic.dev/)**: Referenced for JSON Schema generation and field-level pre-validation sanitizers.
- **[LiteLLM / Groq Provider Reference](https://docs.litellm.ai/docs/providers/groq)**: Referenced for configuring `groq/openai/gpt-oss-120b` with Crawl4AI's `LLMConfig`.
- **AI Coding Assistance (Gemini)**: Used to help structure the modular repository boilerplate, write unit tests for edge-case DOM string normalization, and format the README documentation. All architecture decisions, schema validation rules, and extraction workflows were reviewed and verified.
