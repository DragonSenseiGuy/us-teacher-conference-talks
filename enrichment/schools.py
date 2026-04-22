"""
Cheap enrichment pipeline for school affiliations and topic classification.

This module provides:
1. Regex/heuristic extraction of school/district names from presenter bios
2. Lightweight keyword-based topic tagging
3. Optional LLM enrichment via OpenAI API (only if OPENAI_API_KEY is set)

Design goal: keep cost < $0.001 per talk for the heuristic path;
LLM path is demonstrated on a sample.
"""

import csv
import os
import re
from typing import List, Optional

SCHOOL_KEYWORDS = [
    "School District", "Public Schools", "High School", "Middle School",
    "Elementary School", "Charter School", "Academy", "Prep School",
    "University of", "College", "Institute of Technology",
    "Department of Education", "Education Center",
]

TOPIC_KEYWORDS = {
    "STEM": ["STEM", "STEAM", "science technology engineering math"],
    "Mathematics": ["mathematics", "math education", "algebra", "geometry", "calculus"],
    "Science": ["science education", "biology", "chemistry", "physics", "earth science"],
    "Literacy": ["literacy", "reading", "writing", "English language arts", "ELA"],
    "Social Studies": ["social studies", "history", "civics", "geography"],
    "Technology": ["technology integration", "edtech", "coding", "computer science", "AI"],
    "Equity": ["equity", "inclusion", "diversity", "social justice", "culturally responsive"],
    "Assessment": ["assessment", "grading", " formative assessment", "standardized testing"],
    "Leadership": ["leadership", "administration", "principal", "instructional coach"],
    "SEL": ["social emotional", "SEL", "mental health", "wellness", "trauma"],
    "PBL": ["project-based", "problem-based", "inquiry-based", "hands-on"],
    "Differentiation": ["differentiation", "personalized learning", "gifted", "special education"],
    "Early Childhood": ["early childhood", "pre-k", "kindergarten", "preschool"],
}


def extract_schools_from_text(text: str) -> List[str]:
    """Extract school names from free text."""
    schools = []
    text = text or ""
    
    # Pattern: Name (School Name) or Name, School Name
    for match in re.finditer(r"\(([A-Z][^)]{5,200}?(?:School|District|University|College))\)", text):
        candidate = match.group(1).strip()
        if len(candidate) > 5:
            schools.append(candidate)
    
    # Pattern: lines ending with school keywords
    for line in text.split("\n"):
        line = line.strip()
        for kw in SCHOOL_KEYWORDS:
            if kw in line and len(line) < 200:
                # Clean up
                clean = re.sub(r"^[\-\•\*]\s*", "", line)
                if clean not in schools:
                    schools.append(clean)
                break
    
    return list(dict.fromkeys(schools))  # preserve order, dedupe


def classify_topics(text: str) -> List[str]:
    """Keyword-based topic classification."""
    text_lower = (text or "").lower()
    topics = []
    for topic, keywords in TOPIC_KEYWORDS.items():
        for kw in keywords:
            if kw.lower() in text_lower:
                topics.append(topic)
                break
    return topics


def enrich_record(row: dict) -> dict:
    """Enrich a single CSV row with extracted schools and topics."""
    combined_text = " ".join(filter(None, [
        row.get("description", ""),
        row.get("presenters", ""),
        row.get("title", ""),
    ]))
    
    # Extract schools if not already present
    existing_schools = row.get("presenter_schools", "")
    if not existing_schools or existing_schools.strip() == "":
        schools = extract_schools_from_text(combined_text)
        row["presenter_schools"] = " | ".join(schools)
    
    # Add topic tags
    topics = classify_topics(combined_text)
    if topics:
        existing = [t.strip() for t in row.get("topics", "").split("|") if t.strip()]
        merged = list(dict.fromkeys(existing + topics))
        row["topics"] = " | ".join(merged)
    
    return row


def enrich_csv(input_path: str, output_path: str, sample_llm: int = 0):
    """Enrich a CSV file. Optionally run LLM on first N rows."""
    with open(input_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    
    enriched = [enrich_record(r) for r in rows]
    
    if sample_llm > 0 and os.environ.get("OPENAI_API_KEY"):
        enriched = enrich_with_llm(enriched, sample_llm)
    
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=enriched[0].keys() if enriched else [])
        writer.writeheader()
        writer.writerows(enriched)
    
    print(f"[Enrichment] Enriched {len(enriched)} records -> {output_path}")


def enrich_with_llm(rows: List[dict], n: int) -> List[dict]:
    """Demonstration: use OpenAI to extract structured info from first N rows."""
    try:
        import openai
    except ImportError:
        print("[Enrichment] openai package not installed, skipping LLM enrichment")
        return rows
    
    client = openai.OpenAI()
    for row in rows[:n]:
        prompt = f"""Extract school affiliations and 3-5 topic tags for this conference talk.
Title: {row.get('title', '')}
Description: {row.get('description', '')[:500]}
Presenters: {row.get('presenters', '')}

Return JSON: {{"schools": ["..."], "topics": ["..."]}}"""
        try:
            resp = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                max_tokens=200,
            )
            import json
            data = json.loads(resp.choices[0].message.content)
            if data.get("schools"):
                row["presenter_schools"] = " | ".join(data["schools"])
            if data.get("topics"):
                row["topics"] = " | ".join(data["topics"])
            row["confidence"] = "high"
        except Exception as e:
            print(f"[Enrichment] LLM failed for row: {e}")
    return rows
