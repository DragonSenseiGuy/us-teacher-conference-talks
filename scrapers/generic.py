"""
Generic scraper for parsing conference talk listings from arbitrary HTML pages.

Targets pages like:
- School district staff pages listing presentations
- University faculty pages
- Personal educator blogs
- Vendor/partner pages listing their conference sessions
"""

import re
from datetime import datetime
from typing import List, Optional
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

from .base import BaseScraper, TalkRecord


# Conference name patterns for detection
CONFERENCE_PATTERNS = [
    (r"NCTM\s+(?:Annual|Regional|Spring|Fall)?\s*(?:Meeting|Conference|Exposition)?", "NCTM"),
    (r"NSTA\s+(?:National|Area)?\s*(?:Conference|Meeting)?\s*(?:on\s+Science\s+Education)?", "NSTA"),
    (r"NCTE\s+(?:Annual)?\s*(?:Convention|Conference)?", "NCTE"),
    (r"NCSS\s+(?:Annual)?\s*(?:Conference|Convention)?", "NCSS"),
    (r"ISTE(?:Live)?\s+\d{2,4}", "ISTE"),
    (r"ASCD\s+(?:Annual)?\s*(?:Conference|Meeting)?", "ASCD"),
    (r"SXSW\s+EDU", "SXSW EDU"),
    (r"CUE\s+(?:National|Annual)?\s*Conference", "CUE"),
    (r"National\s+(?:Science|Math|English|Social\s+Studies)\s+Teachers?\s+(?:Association|Conference)", "National Subject Conference"),
]

# Date patterns
DATE_PATTERNS = [
    r"(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4}",
    r"\d{1,2}/\d{1,2}/\d{2,4}",
    r"\d{4}-\d{2}-\d{2}",
    r"(Spring|Fall|Summer|Winter)\s+\d{4}",
]


class GenericTalkScraper(BaseScraper):
    """Parse talk information from generic HTML pages."""
    
    name = "generic"
    
    def __init__(self, delay: float = 1.0):
        super().__init__(delay)
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
        })
    
    def _fetch(self, url: str) -> Optional[BeautifulSoup]:
        try:
            resp = self.session.get(url, timeout=30)
            resp.raise_for_status()
            return BeautifulSoup(resp.text, "lxml")
        except Exception as e:
            print(f"[ERROR] Failed to fetch {url}: {e}")
            return None
    
    def detect_conference(self, text: str) -> Optional[str]:
        """Detect conference name from text."""
        for pattern, conf_name in CONFERENCE_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                return conf_name
        return None
    
    def extract_presenters(self, text: str, context: str = "") -> List[str]:
        """Heuristic presenter extraction."""
        presenters = []
        # Look for "Presenter(s): Name" or "Speaker: Name"
        for match in re.finditer(r"(?:Presenter|Speaker|Facilitator)\(?s?\)?:\s*([^\n]+)", text, re.IGNORECASE):
            name = match.group(1).strip()
            if name:
                presenters.append(name)
        return presenters
    
    def extract_schools(self, text: str) -> List[str]:
        """Heuristic school/institution extraction."""
        schools = []
        # Look for affiliations in parentheses after names
        for match in re.finditer(r"\(([A-Z][^)]+(?:School|District|University|College|Academy|Institute|Center)[^)]*)\)", text):
            schools.append(match.group(1).strip())
        # Look for lines containing school keywords
        for line in text.split("\n"):
            line = line.strip()
            if any(k in line for k in ["School District", "Public Schools", "High School", "Middle School", "Elementary School"]):
                if len(line) < 200:
                    schools.append(line)
        return list(set(schools))
    
    def parse_page(self, url: str) -> List[TalkRecord]:
        """Parse a generic page for talk listings."""
        soup = self._fetch(url)
        if not soup:
            return []
        
        records = []
        page_text = soup.get_text(separator="\n", strip=True)
        detected_conf = self.detect_conference(page_text)
        
        # Strategy 1: Look for list items or divs that contain both a title and conference reference
        for elem in soup.find_all(["li", "div", "p", "article"]):
            text = elem.get_text(separator="\n", strip=True)
            if not text or len(text) < 30:
                continue
            
            conf = self.detect_conference(text) or detected_conf
            if not conf:
                continue
            
            # Try to find a title: look for bold text or links at the start
            title = None
            bold = elem.find(["strong", "b", "h3", "h4"])
            if bold:
                title = bold.get_text(strip=True)
            else:
                link = elem.find("a")
                if link:
                    title = link.get_text(strip=True)
            
            if not title or len(title) < 10 or len(title) > 300:
                continue
            
            # Extract date
            talk_date = None
            for pat in DATE_PATTERNS:
                m = re.search(pat, text)
                if m:
                    talk_date = m.group(0)
                    break
            
            presenters = self.extract_presenters(text)
            schools = self.extract_schools(text)
            
            records.append(TalkRecord(
                title=title,
                conference_name=conf,
                talk_date=talk_date,
                description=text[:1000],
                source_url=url,
                presenters=presenters,
                presenter_schools=schools,
                scraped_at=datetime.utcnow().isoformat(),
                confidence="low" if not presenters else "medium",
            ))
        
        # Strategy 2: If no records found, treat the whole page as a single talk if it mentions a conference
        if not records and detected_conf:
            title_tag = soup.find("h1") or soup.find("title")
            title = title_tag.get_text(strip=True) if title_tag else detected_conf
            presenters = self.extract_presenters(page_text)
            schools = self.extract_schools(page_text)
            
            talk_date = None
            for pat in DATE_PATTERNS:
                m = re.search(pat, page_text)
                if m:
                    talk_date = m.group(0)
                    break
            
            records.append(TalkRecord(
                title=title,
                conference_name=detected_conf,
                talk_date=talk_date,
                description=page_text[:2000],
                source_url=url,
                presenters=presenters,
                presenter_schools=schools,
                scraped_at=datetime.utcnow().isoformat(),
                confidence="low",
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
        # No default URLs; this scraper is meant to be fed specific pages
        return []
