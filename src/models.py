"""Pydantic data schemas and validation rules for wedding reception venues."""

import re
from typing import Any, Dict, Optional
from urllib.parse import urljoin
from pydantic import BaseModel, Field

try:
    from pydantic import field_validator

    PYDANTIC_V2 = True
except ImportError:
    from pydantic import validator

    PYDANTIC_V2 = False

THEKNOT_BASE_URL = "https://www.theknot.com"


def _clean_name_val(v: object) -> str:
    if not v or not str(v).strip():
        raise ValueError("Venue name cannot be empty.")
    return " ".join(str(v).strip().split())


def _clean_location_val(v: object) -> Optional[str]:
    if v is None:
        return None
    text = " ".join(str(v).strip().split())
    if not text or text.lower() in ("none", "null", "n/a", "unknown"):
        return None
    text = re.sub(r",\s*GA\s*Georgia$", ", GA", text)
    if text == "GeorgiaGeorgia":
        text = "Georgia"
    elif text == "GAGA":
        text = "GA"
    elif text == "Atlanta AreaAtlanta Area":
        text = "Atlanta Area"
    elif text == "Midtown AtlantaMidtown Atlanta":
        text = "Midtown Atlanta"
    elif text == "AtlantaAtlanta":
        text = "Atlanta, GA"
    return text


def _clean_optional_text_val(v: object) -> Optional[str]:
    if v is None:
        return None
    text = " ".join(str(v).strip().split())
    if not text or text.lower() in (
        "none",
        "null",
        "n/a",
        "not available",
        "request pricing",
        "unknown",
    ):
        return None
    return text


def _clean_rating_val(v: object) -> Optional[float]:
    if v is None or v == "":
        return None
    if isinstance(v, (int, float)):
        val = float(v)
        return val if 0.0 < val <= 5.0 else None
    match = re.search(r"(\d+(?:\.\d+)?)", str(v))
    if not match:
        return None
    val = float(match.group(1))
    return val if 0.0 < val <= 5.0 else None


def _clean_reviews_count_val(v: object) -> Optional[int]:
    if v is None or v == "":
        return None
    if isinstance(v, int):
        return v if v >= 0 else None
    match = re.search(r"(\d+)", str(v).replace(",", ""))
    if not match:
        return None
    return int(match.group(1))


def _clean_source_url_val(v: object) -> Optional[str]:
    if v is None:
        return None
    url = str(v).strip()
    if not url or url.lower() in ("none", "null", "n/a"):
        return None
    if url.startswith("/"):
        return urljoin(THEKNOT_BASE_URL, url)
    return url


class ReceptionVenue(BaseModel):
    """Validated data model for a single reception venue listing on The Knot.

    Missing information is preserved as None (exported as blank in CSV) rather
    than invented or filled with synthetic defaults.
    """

    name: str = Field(
        ...,
        description="Official name of the reception venue.",
    )
    location: Optional[str] = Field(
        default=None,
        description="City and state or neighborhood location (e.g., 'Atlanta, GA'). Leave null if missing.",
    )
    price: Optional[str] = Field(
        default=None,
        description="Starting price or price text exactly as shown (e.g., 'Starting at $5,000'). Leave null if not listed.",
    )
    capacity: Optional[str] = Field(
        default=None,
        description="Guest capacity range as listed (e.g., '151-200 guests' or '300+ guests'). Leave null if missing.",
    )
    rating: Optional[float] = Field(
        default=None,
        description="Numerical star rating between 0.0 and 5.0. Leave null if the venue has 0 reviews or no rating.",
    )
    reviews_count: Optional[int] = Field(
        default=None,
        description="Total number of user reviews as an integer. Leave null if missing.",
    )
    short_description: Optional[str] = Field(
        default=None,
        description="Short descriptive summary snippet of the venue from the listing card. Leave null if missing.",
    )
    source_url: Optional[str] = Field(
        default=None,
        description="Direct URL to the venue storefront on The Knot (or listing page URL if storefront URL is absent).",
    )

    if PYDANTIC_V2:
        _val_name = field_validator("name", mode="before")(_clean_name_val)
        _val_loc = field_validator("location", mode="before")(_clean_location_val)
        _val_text = field_validator("price", "capacity", "short_description", mode="before")(_clean_optional_text_val)
        _val_rating = field_validator("rating", mode="before")(_clean_rating_val)
        _val_reviews = field_validator("reviews_count", mode="before")(_clean_reviews_count_val)
        _val_url = field_validator("source_url", mode="before")(_clean_source_url_val)
    else:
        _val_name = validator("name", pre=True, allow_reuse=True)(_clean_name_val)
        _val_loc = validator("location", pre=True, allow_reuse=True)(_clean_location_val)
        _val_text = validator("price", "capacity", "short_description", pre=True, allow_reuse=True)(_clean_optional_text_val)
        _val_rating = validator("rating", pre=True, allow_reuse=True)(_clean_rating_val)
        _val_reviews = validator("reviews_count", pre=True, allow_reuse=True)(_clean_reviews_count_val)
        _val_url = validator("source_url", pre=True, allow_reuse=True)(_clean_source_url_val)

    @classmethod
    def get_json_schema(cls) -> Dict[str, Any]:
        """Return JSON schema compatible across Pydantic v1 and v2."""
        if hasattr(cls, "model_json_schema"):
            return cls.model_json_schema()
        return cls.schema()

    @classmethod
    def validate_record(cls, data: Dict[str, Any]) -> "ReceptionVenue":
        """Validate a dictionary record across Pydantic v1 and v2."""
        if hasattr(cls, "model_validate"):
            return cls.model_validate(data)
        return cls.parse_obj(data)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize model to dictionary across Pydantic v1 and v2."""
        if hasattr(self, "model_dump"):
            return self.model_dump()
        return self.dict()

    def deduplication_key(self) -> str:
        """Generate a normalized key for deduplicating venues across pages."""
        if self.source_url and "/marketplace/" in self.source_url:
            base_url = self.source_url.split("?")[0].rstrip("/").lower()
            if not base_url.endswith("wedding-reception-venues-atlanta-ga"):
                return f"url:{base_url}"
        norm_name = re.sub(r"[^a-z0-9]+", "", self.name.lower())
        return f"name:{norm_name}"
