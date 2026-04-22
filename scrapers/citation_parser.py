"""
Robust parser for academic citation-style conference presentation listings.
"""

import re
from datetime import datetime
from typing import List

from .base import TalkRecord


CITATION_RE = re.compile(
    r"^([A-Z][^()]+?)\s*\((\d{4})(?:,\s*([A-Za-z]+))?\)\.?\s*"
    r"[_\*\"“”']?(.+?)[_\*\"“”']?(?=\s*(?:Presented|Poster|Paper|Workshop|Session|Symposium|Keynote|Invited talk|Presentation))\s*"
    r"(?:Presented|Poster|Paper|Workshop|Session|Symposium|Keynote|Invited talk|Presentation)\s+"
    r"(?:at|to|for)\s+(?:the\s+)?(.+?)[,\.]\s+"
    r"(.+?)(?:[,\.]\s+((?:January|February|March|April|May|June|July|August|September|October|November|December)[^\.]*\d{4}))?\.?$",
    re.IGNORECASE | re.MULTILINE,
)

SIMPLE_RE = re.compile(
    r"[_\*\"“”']?(.+?)[_\*\"“”']?(?=\s*(?:Presented|Poster|Paper|Workshop|Session|Symposium|Keynote|Invited talk|Presentation))\s*"
    r"(?:Presented|Poster|Paper|Workshop|Session|Symposium|Keynote|Invited talk|Presentation)\s+"
    r"(?:at|to|for)\s+(?:the\s+)?(.+?)[,\.]\s+"
    r"(.+?)(?:[,\.]\s+((?:January|February|March|April|May|June|July|August|September|October|November|December)[^\.]*\d{4}))?\.?$",
    re.IGNORECASE | re.MULTILINE,
)

CONFERENCE_ALIASES = {
    "nctm": "NCTM Annual Meeting & Exposition",
    "national council of teachers of mathematics": "NCTM Annual Meeting & Exposition",
    "nsta": "NSTA National Conference on Science Education",
    "national science teachers association": "NSTA National Conference on Science Education",
    "national science teachers' association": "NSTA National Conference on Science Education",
    "ascd": "ASCD Annual Conference",
    "iste": "ISTELive",
    "ncte": "NCTE Annual Convention",
    "ncss": "NCSS Annual Conference",
    "aera": "AERA Annual Meeting",
    "amte": "AMTE Annual Conference",
}


def normalize_conference(name: str) -> str:
    name_lower = name.lower()
    for alias, full_name in CONFERENCE_ALIASES.items():
        if alias in name_lower:
            return full_name
    return name.strip()


def clean_title(title: str) -> str:
    """Remove markdown formatting and trailing artifacts from captured title."""
    title = title.strip()
    # Remove trailing presentation type words that got captured
    for suffix in ["._ Workshop", "_ Workshop", ". Workshop", " Workshop",
                   "._ Session", "_ Session", ". Session", " Session",
                   "._ Poster", "_ Poster", ". Poster", " Poster",
                   "._ Paper", "_ Paper", ". Paper", " Paper",
                   "._ Presentation", "_ Presentation", ". Presentation", " Presentation"]:
        if title.endswith(suffix):
            title = title[:-len(suffix)]
            break
    return title.strip("._*\"“”' ")


def parse_authors(authors_text: str) -> List[str]:
    """Parse author list like 'Cullen, C. J., Klanderman, D., & Barrett, J.'"""
    authors = []
    parts = re.split(r"\s+&\s+", authors_text)
    for part in parts:
        part = part.strip().rstrip(",")
        if not part:
            continue
        subparts = [p.strip() for p in part.split(",") if p.strip()]
        if len(subparts) >= 2 and len(subparts[-1]) <= 4:
            authors.append(f"{subparts[-2]}, {subparts[-1]}")
            subparts = subparts[:-2]
        for sp in subparts:
            sp = sp.strip()
            if sp and len(sp) > 2:
                authors.append(sp)
    return list(dict.fromkeys(a for a in authors if a))


def parse_citation_text(text: str, source_url: str = "") -> List[TalkRecord]:
    records = []
    for line in text.split("\n"):
        line = line.strip()
        if len(line) < 40:
            continue
        
        m = CITATION_RE.search(line)
        if m:
            authors_text, year, month, title, conf, location, date = m.groups()
            presenters = parse_authors(authors_text) if authors_text else []
            title = clean_title(title) if title else ""
            # Build date from year/month if no trailing date
            talk_date = date.strip() if date else None
            if not talk_date and month:
                talk_date = f"{month} {year}"
            if title:
                records.append(TalkRecord(
                    title=title,
                    conference_name=normalize_conference(conf) if conf else "",
                    conference_date=f"{year}-01-01/{year}-12-31" if year else None,
                    talk_date=talk_date,
                    source_url=source_url,
                    presenters=presenters,
                    scraped_at=datetime.utcnow().isoformat(),
                    confidence="medium",
                ))
            continue
        
        m2 = SIMPLE_RE.search(line)
        if m2:
            title, conf, location, date = m2.groups()
            title = clean_title(title) if title else ""
            if title and len(title) >= 10:
                records.append(TalkRecord(
                    title=title,
                    conference_name=normalize_conference(conf) if conf else "",
                    talk_date=date.strip() if date else None,
                    source_url=source_url,
                    scraped_at=datetime.utcnow().isoformat(),
                    confidence="medium",
                ))
    return records
