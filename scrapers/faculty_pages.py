"""
Specialized scrapers for faculty presentation pages and news articles.

These pages often have highly structured citation formats that are easier
to parse than generic conference schedulers.
"""

import re
from datetime import datetime
from typing import List, Optional
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup, NavigableString

from .base import BaseScraper, TalkRecord


# Regex to parse common faculty CV citation formats
CITATION_PATTERNS = [
    # Author, A. (2023). "Title". Presented at the Conference Name, City, State, Month Day – Day, Year.
    r"([A-Z][^()]+)\s+\((\d{4})\)\s*[.\s]*[\"“”']?(.+?)[\"“”']?\s*[.]\s*(?:Presented|Poster|Paper|Workshop|Session)\s+(?:at|to)\s+(?:the\s+)?(.+?)[,\.]\s+(.+?)[,\.]\s+((?:January|February|March|April|May|June|July|August|September|October|November|December)[^\.]*\d{4})",
    
    # Simpler: Title. Presented at Conference, Location, Date.
    r"[\"“”']?(.+?)[\"“”']?\s*[.]\s*(?:Presented|Poster|Paper|Workshop)\s+(?:at|to)\s+(?:the\s+)?(.+?)[,\.]\s+(.+?)[,\.]\s+((?:January|February|March|April|May|June|July|August|September|October|November|December)[^\.]*\d{4})",
    
    # Author (Year). Title. Conference. Location. Date.
    r"([A-Z][a-z]+(?:,\s+[A-Z]\.)+)\s+\((\d{4})\)\s*[.]\s*(.+?)\s*[.]\s*(?:Presented|Poster|Paper|Workshop|Session)?\s*(?:at\s+)?(?:the\s+)?(NCTM|NSTA|ASCD|ISTE|NCTE|NCSS|AERA|PME-NA|AMTE)[^\.]*\s*[.]\s*(.+?)\s*[.]\s*((?:January|February|March|April|May|June|July|August|September|October|November|December)[^\.]*\d{4})",
]


def extract_presenters_from_citation(text: str) -> List[str]:
    """Extract author names from the beginning of a citation."""
    presenters = []
    # Pattern: Author, A. B., Author2, C. D., & Author3, E. F.
    # Try to grab everything before the year
    m = re.match(r"^([A-Z][^()]+?)\s+\(\d{4}", text)
    if m:
        authors_text = m.group(1)
        # Split by commas and &
        parts = re.split(r",\s*|\s+&\s+", authors_text)
        for part in parts:
            part = part.strip()
            if part and len(part) > 2:
                presenters.append(part)
    return presenters


def detect_conference_in_text(text: str) -> Optional[str]:
    text_lower = text.lower()
    conferences = [
        ("nctm", "NCTM Annual Meeting & Exposition"),
        ("nsta", "NSTA National Conference on Science Education"),
        ("ascd", "ASCD Annual Conference"),
        ("iste", "ISTELive"),
        ("ncte", "NCTE Annual Convention"),
        ("ncss", "NCSS Annual Conference"),
        ("aera", "AERA Annual Meeting"),
        ("amte", "AMTE Annual Conference"),
        ("pme-na", "PME-NA Annual Meeting"),
    ]
    for keyword, name in conferences:
        if keyword in text_lower:
            return name
    return None


class FacultyPageScraper(BaseScraper):
    """Parse faculty CV/presentation pages."""
    
    name = "faculty_pages"
    
    def __init__(self, delay: float = 1.0):
        super().__init__(delay)
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        })
    
    def _fetch(self, url: str) -> Optional[BeautifulSoup]:
        try:
            resp = self.session.get(url, timeout=30)
            resp.raise_for_status()
            return BeautifulSoup(resp.text, "lxml")
        except Exception as e:
            print(f"[ERROR] Failed to fetch {url}: {e}")
            return None
    
    def parse_page(self, url: str) -> List[TalkRecord]:
        soup = self._fetch(url)
        if not soup:
            return []
        
        records = []
        # Get all text elements
        text = soup.get_text(separator="\n", strip=True)
        lines = [l.strip() for l in text.split("\n") if l.strip()]
        
        for line in lines:
            line = line.strip()
            if len(line) < 40:
                continue
            
            conf = detect_conference_in_text(line)
            if not conf:
                continue
            
            # Try to extract year
            year_match = re.search(r"\((\d{4})\)", line)
            year = year_match.group(1) if year_match else None
            
            # Try to extract title from italics or quotes
            title = None
            # Look for text between underscores (markdown-style) or quotes
            title_match = re.search(r"[_\"“”'](.+?)[_\"“”']", line)
            if title_match:
                title = title_match.group(1).strip()
            
            # If no title found, try to get it from between year and "Presented"
            if not title and year:
                title_match = re.search(r"\(\d{4}\)\s*[.\s]*(.+?)\s*(?:Presented|Poster|Paper|Workshop)", line)
                if title_match:
                    title = title_match.group(1).strip()
            
            if not title or len(title) < 10:
                continue
            
            presenters = extract_presenters_from_citation(line)
            
            # Extract date
            talk_date = None
            date_match = re.search(r"((?:January|February|March|April|May|June|July|August|September|October|November|December)[^,\.]*\d{4})", line)
            if date_match:
                talk_date = date_match.group(1)
            
            # Extract location (often after conference name)
            location = None
            # Simple heuristic: text between conference name and date
            
            records.append(TalkRecord(
                title=title,
                conference_name=conf,
                conference_date=f"{year}-01-01/{year}-12-31" if year else None,
                talk_date=talk_date,
                source_url=url,
                presenters=presenters,
                scraped_at=datetime.utcnow().isoformat(),
                confidence="medium",
            ))
        
        return records
    
    def scrape_urls(self, urls: List[str]) -> List[TalkRecord]:
        all_records = []
        for url in urls:
            recs = self.parse_page(url)
            all_records.extend(recs)
        self.records = all_records
        return all_records
    
    def scrape(self) -> List[TalkRecord]:
        return []
