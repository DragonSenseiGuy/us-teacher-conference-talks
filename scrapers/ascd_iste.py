"""
Scraper for ASCD and ISTE conference session pages.

ASCD session detail URL pattern:
  https://event.ascd.org/{year}/program/search/detail_session.php?id={session_id}

ISTE session detail URL pattern:
  https://conference.iste.org/{year}/program/search/detail_session.php?id={session_id}
  (Note: ISTE and ASCD co-located from 2025, may share platform)
"""

import re
import time
from datetime import datetime
from typing import List, Optional
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from .base import BaseScraper, TalkRecord


class AscdIsteScraper(BaseScraper):
    """Scraper for ASCD/ISTE session detail pages."""
    
    name = "ascd_iste"
    
    # Known conference configurations
    CONFERENCES = {
        "ascd_2024": {
            "base_url": "https://event.ascd.org/2024/program/search",
            "conference_name": "ASCD Annual Conference 2024",
            "conference_date": "2024-03-22/2024-03-25",
            "city": "Washington, DC",
        },
        "ascd_2025": {
            "base_url": "https://event.ascd.org/2025/program/search",
            "conference_name": "ASCD Annual Conference 2025",
            "conference_date": "2025-06-29/2025-07-02",
            "city": "San Antonio, TX",
        },
        "iste_2024": {
            "base_url": "https://conference.iste.org/2024/program/search",
            "conference_name": "ISTELive 24",
            "conference_date": "2024-06-23/2024-06-26",
            "city": "Denver, CO",
        },
        "iste_2025": {
            "base_url": "https://conference.iste.org/2025/program/search",
            "conference_name": "ISTELive 25",
            "conference_date": "2025-06-29/2025-07-02",
            "city": "San Antonio, TX",
        },
    }
    
    def __init__(self, delay: float = 1.5):
        super().__init__(delay)
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        })
    
    def _fetch(self, url: str) -> Optional[BeautifulSoup]:
        try:
            resp = self.session.get(url, timeout=30)
            resp.raise_for_status()
            return BeautifulSoup(resp.text, "lxml")
        except Exception as e:
            print(f"[ERROR] Failed to fetch {url}: {e}")
            return None
    
    def parse_session_page(self, soup: BeautifulSoup, conf_key: str, session_url: str) -> Optional[TalkRecord]:
        """Parse a single ASCD/ISTE session detail page."""
        meta = self.CONFERENCES[conf_key]
        
        # Title is usually the first h1 or h2
        title_tag = soup.find("h1") or soup.find("h2")
        if not title_tag:
            return None
        title = title_tag.get_text(strip=True)
        if not title or title.lower() in ["program search", "ascd annual conference"]:
            return None
        
        # Description: look for paragraphs after title, before presenters
        description = ""
        desc_parts = []
        for elem in title_tag.find_all_next():
            if elem.name in ["h2", "h3", "strong"] and "presented by" in elem.get_text(strip=True).lower():
                break
            if elem.name == "p":
                txt = elem.get_text(strip=True)
                if txt and not txt.startswith("Outcomes:") and not txt.startswith("After this session"):
                    desc_parts.append(txt)
            if len(desc_parts) > 5:
                break
        description = " ".join(desc_parts)
        
        # Find When/Where block
        when_where = ""
        when_where_parent = None
        for strong in soup.find_all("strong"):
            if "When/Where" in strong.get_text():
                when_where_parent = strong.find_parent("p")
                if when_where_parent:
                    when_where = when_where_parent.get_text(separator="\n", strip=True)
                break
        
        talk_date = None
        location = None
        if when_where:
            # Extract date like "Sunday, March 24, 3:00pm – 4:30pm"
            m = re.search(r"([A-Za-z]+,\s+[A-Za-z]+\s+\d{1,2}),?\s+\d{1,2}:\d{2}[ap]m", when_where, re.IGNORECASE)
            if m:
                talk_date = m.group(1)
            # Extract room/location from lines after the date/time line
            lines = [l.strip() for l in when_where.split("\n") if l.strip() and "When/Where" not in l]
            if len(lines) >= 2:
                location = lines[-1]
            elif len(lines) == 1 and "," in lines[0]:
                # Sometimes location is on same line after the time
                parts = lines[0].split(",")
                if len(parts) >= 2:
                    location = ",".join(parts[1:]).strip()
        
        # Extract presenters
        presenters = []
        schools = []
        in_presenter = False
        for elem in soup.find_all(["h2", "h3", "strong", "p"]):
            text = elem.get_text(strip=True)
            if "presented by" in text.lower():
                in_presenter = True
                continue
            if in_presenter and elem.name == "p":
                # Presenter block often has name in bold, then role/school on next lines
                bold = elem.find("strong")
                if bold:
                    name = bold.get_text(strip=True)
                    if name and len(name) < 100:
                        presenters.append(name)
                # Try to extract school from the text after the name
                full = elem.get_text(separator="\n", strip=True)
                lines = [l.strip() for l in full.split("\n") if l.strip()]
                for line in lines[1:]:
                    if any(k in line.lower() for k in ["school", "district", "university", "college", "department", "center"]):
                        schools.append(line)
                        break
            if in_presenter and elem.name in ["h2", "h3"] and "digital tote" in text.lower():
                break
        
        # Topics/Format
        topics = []
        session_type = None
        for strong in soup.find_all("strong"):
            txt = strong.get_text(strip=True)
            if txt == "Topic:":
                topic_p = strong.find_parent("p")
                if topic_p:
                    topics = [t.strip() for t in topic_p.get_text().replace("Topic:", "").split(",") if t.strip()]
            if txt == "Format:":
                fmt_p = strong.find_parent("p")
                if fmt_p:
                    session_type = fmt_p.get_text().replace("Format:", "").strip()
        
        return TalkRecord(
            title=title,
            conference_name=meta["conference_name"],
            conference_date=meta["conference_date"],
            talk_date=talk_date,
            description=description[:2000] if description else None,
            source_url=session_url,
            presenters=presenters,
            presenter_schools=list(set(schools)),
            session_type=session_type,
            topics=topics,
            location=location,
            city=meta.get("city"),
            scraped_at=datetime.utcnow().isoformat(),
            confidence="high",
        )
    
    def scrape_session_ids_from_search(self, conf_key: str, max_pages: int = 5) -> List[str]:
        """Attempt to discover session IDs from search index pages."""
        meta = self.CONFERENCES[conf_key]
        base = meta["base_url"]
        ids = []
        
        for page in range(1, max_pages + 1):
            url = f"{base}/index.php?page={page}"
            soup = self._fetch(url)
            if not soup:
                continue
            # Look for links to detail_session.php
            for a in soup.find_all("a", href=re.compile(r"detail_session\.php\?id=(\d+)")):
                m = re.search(r"id=(\d+)", a["href"])
                if m:
                    ids.append(m.group(1))
            time.sleep(self.delay)
        
        return list(set(ids))
    
    def scrape_by_session_ids(self, conf_key: str, session_ids: List[str]) -> List[TalkRecord]:
        meta = self.CONFERENCES[conf_key]
        records = []
        for sid in session_ids:
            url = f"{meta['base_url']}/detail_session.php?id={sid}"
            soup = self._fetch(url)
            if soup:
                rec = self.parse_session_page(soup, conf_key, url)
                if rec:
                    records.append(rec)
            time.sleep(self.delay)
        return records
    
    def scrape(self) -> List[TalkRecord]:
        # By default, scrape ASCD 2024 using a few known session IDs as demo
        # In production, discover IDs via search index or enumerate ranges
        demo_ids = [
            "117189261", "117315132", "117193452", "117191759", "117195120",
            "117197290", "117190006", "117189261", "117188001", "117188002",
        ]
        records = self.scrape_by_session_ids("ascd_2024", demo_ids)
        self.records = records
        return records
