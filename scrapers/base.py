from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional, List
import csv
import json


@dataclass
class TalkRecord:
    """Standardized record for a conference talk."""
    title: str
    conference_name: str
    conference_date: Optional[str] = None  # ISO date or date range
    talk_date: Optional[str] = None  # specific day of the talk
    description: Optional[str] = None
    source_url: Optional[str] = None
    presenters: List[str] = field(default_factory=list)
    presenter_schools: List[str] = field(default_factory=list)
    session_type: Optional[str] = None  # e.g., Workshop, Keynote, Poster
    topics: List[str] = field(default_factory=list)
    grade_levels: List[str] = field(default_factory=list)
    location: Optional[str] = None  # venue/room
    city: Optional[str] = None
    scraped_at: Optional[str] = None
    confidence: str = "high"  # high | medium | low
    
    def to_dict(self):
        return asdict(self)
    
    @staticmethod
    def csv_headers():
        return [
            "title", "conference_name", "conference_date", "talk_date",
            "description", "source_url", "presenters", "presenter_schools",
            "session_type", "topics", "grade_levels", "location", "city",
            "scraped_at", "confidence"
        ]
    
    def to_csv_row(self):
        d = self.to_dict()
        # Serialize lists as pipe-delimited strings
        for key in ["presenters", "presenter_schools", "topics", "grade_levels"]:
            if isinstance(d[key], list):
                d[key] = " | ".join(d[key])
        return d


class BaseScraper:
    """Base class for conference scrapers."""
    
    name: str = "base"
    
    def __init__(self, delay: float = 1.0):
        self.delay = delay
        self.records: List[TalkRecord] = []
    
    def scrape(self) -> List[TalkRecord]:
        raise NotImplementedError
    
    def save(self, path: str):
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=TalkRecord.csv_headers())
            writer.writeheader()
            for r in self.records:
                writer.writerow(r.to_csv_row())
