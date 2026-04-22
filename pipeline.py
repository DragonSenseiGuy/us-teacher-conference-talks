#!/usr/bin/env python3
"""
Teacher Conference Dataset Pipeline

Orchestrates scrapers for multiple conference sources and produces
a unified CSV dataset.

Usage:
    python pipeline.py --output data/talks.csv
    python pipeline.py --scraper ascd_iste --output data/ascd.csv
    python pipeline.py --enrich data/talks.csv --output data/talks_enriched.csv
"""

import argparse
import csv
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import List

from scrapers.base import TalkRecord
from scrapers.ascd_iste import AscdIsteScraper
from scrapers.nsta import NstaScraper
from scrapers.generic import GenericTalkScraper


def run_ascd_iste(output_path: str):
    scraper = AscdIsteScraper(delay=1.5)
    print("[Pipeline] Running ASCD/ISTE scraper...")
    records = scraper.scrape()
    print(f"[Pipeline] Collected {len(records)} ASCD/ISTE records")
    scraper.save(output_path)
    print(f"[Pipeline] Saved to {output_path}")
    return records


def run_nsta(output_path: str):
    scraper = NstaScraper(delay=2.0)
    print("[Pipeline] Running NSTA scraper...")
    records = scraper.scrape()
    print(f"[Pipeline] Collected {len(records)} NSTA records")
    scraper.save(output_path)
    print(f"[Pipeline] Saved to {output_path}")
    return records


def run_generic(urls: List[str], output_path: str):
    scraper = GenericTalkScraper(delay=1.0)
    print(f"[Pipeline] Running generic scraper on {len(urls)} URLs...")
    records = scraper.scrape_urls(urls)
    print(f"[Pipeline] Collected {len(records)} generic records")
    scraper.save(output_path)
    print(f"[Pipeline] Saved to {output_path}")
    return records


def merge_csvs(paths: List[str], output_path: str):
    all_records = []
    for p in paths:
        if not os.path.exists(p):
            continue
        with open(p, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                all_records.append(row)
    
    if not all_records:
        print("[Pipeline] No records to merge")
        return
    
    # Deduplicate by title + conference_name + talk_date
    seen = set()
    deduped = []
    for row in all_records:
        key = (row.get("title", "").lower(), row.get("conference_name", "").lower(), row.get("talk_date", ""))
        if key not in seen:
            seen.add(key)
            deduped.append(row)
    
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=TalkRecord.csv_headers())
        writer.writeheader()
        writer.writerows(deduped)
    
    print(f"[Pipeline] Merged {len(deduped)} unique records to {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Teacher Conference Dataset Pipeline")
    parser.add_argument("--scraper", choices=["all", "ascd_iste", "nsta", "generic"], default="all")
    parser.add_argument("--output", default="data/talks.csv")
    parser.add_argument("--urls", help="Comma-separated URLs for generic scraper")
    parser.add_argument("--merge", nargs="+", help="Merge multiple CSVs")
    parser.add_argument("--enrich", help="Path to CSV to enrich")
    args = parser.parse_args()
    
    os.makedirs("data", exist_ok=True)
    
    if args.merge:
        merge_csvs(args.merge, args.output)
        return
    
    if args.enrich:
        from enrichment.schools import enrich_csv
        enrich_csv(args.enrich, args.output)
        return
    
    outputs = []
    if args.scraper in ("all", "ascd_iste"):
        out = "data/raw_ascd_iste.csv"
        run_ascd_iste(out)
        outputs.append(out)
    
    if args.scraper in ("all", "nsta"):
        out = "data/raw_nsta.csv"
        run_nsta(out)
        outputs.append(out)
    
    if args.scraper in ("all", "generic"):
        if not args.urls:
            print("[Pipeline] --urls required for generic scraper")
            sys.exit(1)
        urls = [u.strip() for u in args.urls.split(",")]
        out = "data/raw_generic.csv"
        run_generic(urls, out)
        outputs.append(out)
    
    if len(outputs) > 1:
        merge_csvs(outputs, args.output)
    elif len(outputs) == 1:
        import shutil
        shutil.copy(outputs[0], args.output)
        print(f"[Pipeline] Copied to {args.output}")


if __name__ == "__main__":
    main()
