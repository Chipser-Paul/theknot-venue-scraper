"""Deduplication and CSV export utilities for extracted reception venues."""

import csv
import logging
from pathlib import Path
from typing import Iterable, List

from src.models import ReceptionVenue

logger = logging.getLogger(__name__)

CSV_COLUMNS = [
    "name",
    "location",
    "price",
    "capacity",
    "rating",
    "reviews_count",
    "short_description",
    "source_url",
]


def deduplicate_venues(venues: Iterable[ReceptionVenue]) -> List[ReceptionVenue]:
    """Deduplicate venues while preserving original discovery order.

    If a duplicate record appears on a subsequent page with additional non-null
    fields, missing fields on the first record are backfilled without overwriting
    existing verified values.
    """
    unique_by_key: dict[str, ReceptionVenue] = {}

    for venue in venues:
        key = venue.deduplication_key()
        if key not in unique_by_key:
            unique_by_key[key] = venue
        else:
            existing = unique_by_key[key]
            merged_data = existing.to_dict()
            for field_name, value in venue.to_dict().items():
                if merged_data.get(field_name) is None and value is not None:
                    merged_data[field_name] = value
            unique_by_key[key] = ReceptionVenue.validate_record(merged_data)

    return list(unique_by_key.values())


def export_venues_to_csv(venues: Iterable[ReceptionVenue], output_path: str | Path) -> int:
    """Write deduplicated venues to a UTF-8 CSV file.

    Missing values (`None`) are written as empty strings (`""`) so no synthetic
    placeholders appear in the final dataset.
    """
    deduped = deduplicate_venues(venues)
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open(mode="w", encoding="utf-8", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        for venue in deduped:
            row = {
                col: ("" if getattr(venue, col) is None else getattr(venue, col))
                for col in CSV_COLUMNS
            }
            writer.writerow(row)

    logger.info("Exported %d unique venues to %s", len(deduped), path)
    return len(deduped)
