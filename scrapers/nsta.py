"""
Scraper for NSTA conference session browsers.

URL patterns observed:
  https://my.nsta.org/conferences/sessions.aspx?id={CONF_ID}&day={MM/DD/YYYY}&...

Known conference IDs (from web research):
  2025MIN, 2024NEW, 2024DEN, 2023KC, 2023ATL, 2022CHI, 2022HOU,
  2021POR, 2021LOS, 2021NH, 2020BOS (cancelled?), etc.
"""

import re
import time
from datetime import datetime
from typing import List, Optional

import requests
from bs4 import BeautifulSoup

from .base import BaseScraper, TalkRecord


class NstaScraper(BaseScraper):
    """Scraper for NSTA session browsers."""
    
    name = "nsta"
    
    CONFERENCES = {
        "2025MIN": {"name": "NSTA National Conference 2025 Minneapolis", "dates": "2025-11-12/2025-11-15", "city": "Minneapolis, MN"},
        "2024NEW": {"name": "NSTA National Conference 2024 New Orleans", "dates": "2024-11-20/2024-11-23", "city": "New Orleans, LA"},
        "2024DEN": {"name": "NSTA National Conference 2024 Denver", "dates": "2024-03-20/2024-03-23", "city": "Denver, CO"},
        "2023KC":  {"name": "NSTA National Conference 2023 Kansas City", "dates": "2023-10-25/2023-10-28", "city": "Kansas City, MO"},
        "2023ATL": {"name": "NSTA National Conference 2023 Atlanta", "dates": "2023-10-12/2023-10-14", "city": "Atlanta, GA"},
        "2022CHI": {"name": "NSTA National Conference 2022 Chicago", "dates": "2022-07-21/2022-07-24", "city": "Chicago, IL"},
        "2022HOU": {"name": "NSTA National Conference 2022 Houston", "dates": "2022-03-31/2022-04-03", "city": "Houston, TX"},
        "2021POR": {"name": "NSTA Area Conference 2021 Portland", "dates": "2021-10-28/2021-10-30", "city": "Portland, OR"},
        "2021LOS": {"name": "NSTA Area Conference 2021 Los Angeles", "dates": "2021-12-09/2021-12-11", "city": "Los Angeles, CA"},
        "2021NH":  {"name": "NSTA Area Conference 2021 National Harbor", "dates": "2021-11-11/2021-11-13", "city": "National Harbor, MD"},
        "2019STL": {"name": "NSTA National Conference 2019 St. Louis", "dates": "2019-04-11/2019-04-14", "city": "St. Louis, MO"},
        "2018ATL": {"name": "NSTA National Conference 2018 Atlanta", "dates": "2018-03-15/2018-03-18", "city": "Atlanta, GA"},
    }
    
    def __init__(self, delay: float = 2.0):
        super().__init__(delay)
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://www.nsta.org/",
        })
    
    def _fetch(self, url: str) -> Optional[BeautifulSoup]:
        try:
            resp = self.session.get(url, timeout=30)
            if resp.status_code == 403:
                # NSTA blocks non-browser-like requests; return None
                print(f"[WARN] 403 for {url} — may require authenticated session")
                return None
            resp.raise_for_status()
            return BeautifulSoup(resp.text, "lxml")
        except Exception as e:
            print(f"[ERROR] Failed to fetch {url}: {e}")
            return None
    
    def parse_sessions_list(self, soup: BeautifulSoup, conf_id: str, source_url: str) -> List[TalkRecord]:
        """Parse an NSTA session list page."""
        meta = self.CONFERENCES.get(conf_id, {})
        records = []
        
        # NSTA session items are typically in table rows or div blocks with session info
        # The page structure varies; look for session title links
        for link in soup.find_all("a", href=re.compile(r"session_detail|session\.aspx|sessions\.aspx")):
            title = link.get_text(strip=True)
            if not title or len(title) < 5:
                continue
            
            # Try to find parent container with speakers/date
            container = link.find_parent(["tr", "div", "li"])
            if not container:
                continue
            
            presenters = []
            schools = []
            talk_date = None
            session_type = None
            
            text = container.get_text(separator="\n", strip=True)
            lines = [l.strip() for l in text.split("\n") if l.strip()]
            
            # Look for speaker lines
            for line in lines:
                if line.startswith("Speaker") or line.startswith("Presenter"):
                    # e.g., "Speakers: John Doe (School Name)"
                    m = re.search(r"[:\-]\s*(.+)", line)
                    if m:
                        presenters.append(m.group(1))
                # Date patterns
                if re.search(r"(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),?\s+(January|February|March|April|May|June|July|August|September|October|November|December)", line):
                    talk_date = line
                # Session type
                if any(t in line for t in ["Workshop", "Presentation", "Poster", "Short Course", "Share-a-Thon"]):
                    session_type = line
            
            records.append(TalkRecord(
                title=title,
                conference_name=meta.get("name", f"NSTA Conference {conf_id}"),
                conference_date=meta.get("dates"),
                talk_date=talk_date,
                source_url=source_url,
                presenters=presenters,
                presenter_schools=schools,
                session_type=session_type,
                city=meta.get("city"),
                scraped_at=datetime.utcnow().isoformat(),
                confidence="medium",
            ))
        
        return records
    
    def scrape_conference(self, conf_id: str) -> List[TalkRecord]:
        """Scrape a single NSTA conference browser."""
        url = f"https://my.nsta.org/conferences/sessions.aspx?id={conf_id}"
        soup = self._fetch(url)
        if not soup:
            return []
        records = self.parse_sessions_list(soup, conf_id, url)
        time.sleep(self.delay)
        return records
    
    def scrape(self) -> List[TalkRecord]:
        # Attempt a few conferences as demo
        all_records = []
        for conf_id in ["2024DEN", "2023ATL"]:
            print(f"[NSTA] Scraping {conf_id}...")
            recs = self.scrape_conference(conf_id)
            all_records.extend(recs)
            print(f"[NSTA] Got {len(recs)} records from {conf_id}")
        self.records = all_records
        return all_records
