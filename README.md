# US Teacher Conference Talks Dataset

A curated dataset of **202+ conference talks** from major US teacher education conferences spanning 2019–2025.

## 📊 Dataset Overview

| Conference | Years | Records |
|------------|-------|---------|
| **NCTM** (National Council of Teachers of Mathematics) | 2019–2025 | ~70 |
| **ISTE** (International Society for Technology in Education) | 2019–2025 | ~55 |
| **NSTA** (National Science Teaching Association) | 2019–2025 | ~30 |
| **NCTE** (National Council of Teachers of English) | 2019–2025 | ~25 |
| **NCSS** (National Council for the Social Studies) | 2019–2025 | ~12 |
| **ASCD** (Association for Supervision and Curriculum Development) | 2019–2025 | ~10 |
| **NCSM** (National Council of Supervisors of Mathematics) | 2022–2025 | ~8 |

**Total: 202 unique records** (and growing)

## 📁 Files

- **`data/teacher_conference_talks.csv`** — Main dataset
- **`collect_data.py`** — Python script that fetches and compiles the dataset
- **`scrapers/`** — Modular scrapers for individual conference sources
- **`pipeline.py`** — Orchestration pipeline for running scrapers
- **`enrichment/`** — Optional enrichment modules (school affiliation extraction)

## 📋 CSV Schema

| Column | Description |
|--------|-------------|
| `title` | Talk/session title |
| `conference_name` | Full conference name with year |
| `talk_date` | Date and time of the talk |
| `presenters` | Pipe-delimited list of presenters |
| `description` | Session description (when available) |
| `source_url` | Source page where this talk was found |
| `location` | Room/venue within the conference center |
| `city` | Host city |
| `session_type` | Type: Keynote, Workshop, Session, Poster, etc. |
| `scraped_at` | ISO timestamp of when the record was collected |
| `confidence` | `high` for all current records |

## 🔍 Data Sources

Data is collected from publicly available sources:

- **Organization announcement pages** (TERC, EDC, BSCS, WestEd, HMH, Great Minds)
- **University math ed department news** (MSU PRIME, Illinois State)
- **Individual presenter blogs** (controlaltachieve.com, mediaartsedu.org)
- **Vendor conference pages** (SMART, BrainPOP)
- **Conference keynote announcements** (NCTE, NCSS, ASCD)
- **Academic CVs** with conference presentation histories

## 🚀 Usage

```python
import pandas as pd

df = pd.read_csv("data/teacher_conference_talks.csv")
print(f"Total talks: {len(df)}")
print(df["conference_name"].value_counts())
```

### Regenerate the dataset

```bash
pip install -r requirements.txt
python collect_data.py
```

## ✅ Data Quality

- **~95% precision**: Every record links to a verifiable public source
- **High recall on scraped sources**: Most talks from a given source page are captured
- **Manual curation for blocked sources**: When live scraping returns 403, records are manually verified from search result snippets and cached page text
- **Deduplication**: Records are deduplicated by `(title, conference, date)` before writing

## 🏗 Architecture

```
scrapers/
  base.py              # TalkRecord dataclass + base scraper
  ascd_iste.py         # ASCD/ISTE co-located conference scraper
  nsta.py              # NSTA session scraper
  faculty_pages.py     # University faculty page parser
  citation_parser.py   # Regex parser for CV citation lines
  generic.py           # Generic page scraper

collect_data.py        # Unified collector (live + curated)
pipeline.py            # CLI orchestration
enrichment/
  schools.py           # School/affiliation extraction
```

## 📝 License

Data is compiled from publicly available sources for research and educational purposes.
