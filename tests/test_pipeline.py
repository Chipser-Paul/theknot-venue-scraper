"""Unit tests for Pydantic schema normalization, deduplication, and URL pagination."""

import tempfile
import unittest
from pathlib import Path
from urllib.parse import urlencode, urlparse, parse_qs, urlunparse

from src.models import ReceptionVenue
from src.exporter import deduplicate_venues, export_venues_to_csv


class TestVenuePipeline(unittest.TestCase):
    def test_reception_venue_normalization_and_missing_fields(self):
        """Verify duplicated state strings are cleaned and missing fields stay None."""
        venue = ReceptionVenue.validate_record({
            "name": "  Renaissance Atlanta Midtown Hotel  ",
            "location": "Atlanta, GAGeorgia",
            "price": "Request pricing",
            "capacity": "300+ guests",
            "rating": "0 Stars",
            "reviews_count": "0 Reviews",
            "short_description": "Renaissance Atlanta Midtown Hotel is a wedding venue in Atlanta, Georgia.",
            "source_url": "/marketplace/renaissance-atlanta-midtown-hotel-atlanta-ga-959882",
        })
        self.assertEqual(venue.name, "Renaissance Atlanta Midtown Hotel")
        self.assertEqual(venue.location, "Atlanta, GA")
        self.assertIsNone(venue.price)
        self.assertEqual(venue.capacity, "300+ guests")
        self.assertIsNone(venue.rating)
        self.assertEqual(venue.reviews_count, 0)
        self.assertEqual(
            venue.source_url,
            "https://www.theknot.com/marketplace/renaissance-atlanta-midtown-hotel-atlanta-ga-959882",
        )

    def test_deduplication_merges_missing_fields(self):
        """Verify duplicate venues across pages are merged without losing data."""
        v1 = ReceptionVenue.validate_record({
            "name": "Ventanas",
            "location": "Atlanta, GA",
            "price": None,
            "capacity": "151-200 guests",
            "rating": 4.6,
            "reviews_count": 39,
            "short_description": None,
            "source_url": "https://www.theknot.com/marketplace/ventanas-atlanta-ga-356342",
        })
        v2 = ReceptionVenue.validate_record({
            "name": "Ventanas",
            "location": "Atlanta, GA",
            "price": "Starting at $10,000",
            "capacity": "151-200 guests",
            "rating": 4.6,
            "reviews_count": 39,
            "short_description": "Spectacular cityscape vistas.",
            "source_url": "https://www.theknot.com/marketplace/ventanas-atlanta-ga-356342?page=2",
        })
        deduped = deduplicate_venues([v1, v2])
        self.assertEqual(len(deduped), 1)
        self.assertEqual(deduped[0].price, "Starting at $10,000")
        self.assertEqual(deduped[0].short_description, "Spectacular cityscape vistas.")

    def test_csv_export_writes_blank_for_none(self):
        """Verify None values are written as empty strings in the CSV output."""
        venue = ReceptionVenue.validate_record({
            "name": "Epicurean Hotel Atlanta",
            "location": "Atlanta, GA",
            "price": None,
            "capacity": "101-150 guests",
            "rating": 5.0,
            "reviews_count": 5,
            "short_description": "Sleek modern hotel venue.",
            "source_url": "https://www.theknot.com/marketplace/epicurean-hotel-atlanta-atlanta-ga-2045329",
        })
        with tempfile.TemporaryDirectory() as tmpdir:
            out_csv = Path(tmpdir) / "venues.csv"
            count = export_venues_to_csv([venue], out_csv)
            self.assertEqual(count, 1)
            lines = out_csv.read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(lines), 2)
            self.assertNotIn("None", lines[1])


if __name__ == "__main__":
    unittest.main()
