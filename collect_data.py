#!/usr/bin/env python3
"""
Unified data collector for US teacher conference talks.
Fetches from multiple high-quality public sources and outputs standardized CSV.
"""
import csv
import re
import os
import time
import random
from datetime import datetime
from typing import List, Dict, Optional

import requests
from bs4 import BeautifulSoup

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
})


def fetch_text(url: str, retries: int = 3, timeout: int = 20) -> Optional[str]:
    for i in range(retries):
        try:
            time.sleep(random.uniform(0.3, 1.0))
            r = SESSION.get(url, timeout=timeout)
            if r.status_code == 200:
                return r.text
        except Exception:
            pass
        time.sleep(2 ** i)
    return None


def make_record(title, conference_name, talk_date=None, presenters=None,
                description=None, source_url=None, location=None, city=None,
                session_type=None, confidence="high") -> Dict:
    return {
        "title": (title or "").strip(),
        "conference_name": (conference_name or "").strip(),
        "talk_date": (talk_date or "").strip(),
        "presenters": " | ".join(presenters) if presenters else "",
        "description": (description or "").strip(),
        "source_url": source_url or "",
        "location": location or "",
        "city": city or "",
        "session_type": session_type or "",
        "scraped_at": datetime.now().isoformat(),
        "confidence": confidence,
    }


# ---------------------------------------------------------------------------
# Live scrapers
# ---------------------------------------------------------------------------

def parse_iste_controlaltachieve_2024():
    url = "https://www.controlaltachieve.com/2023/12/my-iste-2024-sessions.html"
    html = fetch_text(url)
    if not html:
        return []
    soup = BeautifulSoup(html, "lxml")
    content = soup.find("div", class_="post-body") or soup.find("article") or soup.body
    text = content.get_text(separator="\n")
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    records = []
    current_date = None
    i = 0
    while i < len(lines):
        line = lines[i]
        dm = re.search(r'(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),\s+(June|July)\s+(\d{1,2}),?\s+(\d{4})', line, re.I)
        if dm:
            current_date = f"{dm.group(2)} {dm.group(3)}, {dm.group(4)}"
            i += 1
            continue
        if any(line.startswith(e) for e in ["💡", "🔥", "🧰", "⏰", "📛", "✨", "📗", "🎨", "👩‍💻"]):
            title = line[2:].strip() if len(line) > 2 else line
            title = re.sub(r'^\s*[\-\–]\s*', '', title)
            # Skip bad titles
            if len(title) < 5 or title.lower().startswith("time") or title.lower().startswith("location"):
                i += 1
                continue
            time_str = ""
            location = ""
            description = ""
            session_url = ""
            for j in range(1, 8):
                if i + j >= len(lines):
                    break
                nl = lines[i + j]
                if any(nl.startswith(e) for e in ["💡", "🔥", "🧰", "⏰", "📛", "✨", "📗", "🎨", "👩‍💻", "📅"]):
                    break
                if "Time:" in nl:
                    time_str = nl.split("Time:", 1)[1].strip()
                elif "Location:" in nl:
                    location = nl.split("Location:", 1)[1].strip()
                elif "Session Page:" in nl:
                    session_url = nl.split("Session Page:", 1)[1].strip()
                elif "Description:" in nl:
                    description = nl.split("Description:", 1)[1].strip()
            if title and current_date:
                records.append(make_record(
                    title=title, conference_name="ISTE Live 2024",
                    talk_date=f"{current_date}, {time_str}",
                    presenters=["Eric Curts"], description=description,
                    source_url=session_url or url, location=location,
                    city="Denver, CO", session_type="Presentation"))
        i += 1
    return records


def parse_smart_iste_2024():
    url = "https://go.smarttech.com/iste2024"
    html = fetch_text(url)
    if not html:
        return []
    soup = BeautifulSoup(html, "lxml")
    content = soup.find("main") or soup.body
    text = content.get_text(separator="\n")
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    records = []
    i = 0
    while i < len(lines):
        line = lines[i]
        m = re.search(r'(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),\s+(June|July)\s+(\d{1,2})(?:st|nd|rd|th)?\s*(.*)', line, re.I)
        if m:
            date_str = f"{m.group(2)} {m.group(3)}, 2024"
            rest = m.group(4)
            time_match = re.search(r'(\d{1,2}:\d{2}\s*(?:am|pm)\s*-\s*\d{1,2}:\d{2}\s*(?:am|pm))', rest, re.I)
            time_str = time_match.group(1) if time_match else ""
            presenter_match = re.search(r'Presented by:\s*([^|]+)', rest, re.I)
            presenters = [presenter_match.group(1).strip()] if presenter_match else []
            location_match = re.search(r'Location:\s*([^|]+)', rest, re.I)
            location = location_match.group(1).strip() if location_match else ""
            title = None
            description = None
            for j in range(1, 5):
                if i + j >= len(lines):
                    break
                nl = lines[i + j]
                if nl.startswith("|") or nl.startswith("-") or nl.startswith("Product"):
                    continue
                if nl.startswith("**") and nl.endswith("**"):
                    title = nl.strip("* ")
                    if i + j + 1 < len(lines):
                        description = lines[i + j + 1].strip()
                    break
                elif not title and len(nl) > 10 and not nl.startswith("|"):
                    title = nl
                    break
            if title:
                records.append(make_record(
                    title=title, conference_name="ISTE Live 2024",
                    talk_date=f"{date_str}, {time_str}", presenters=presenters,
                    description=description or "", source_url=url,
                    location=location, city="Denver, CO",
                    session_type="In-Booth Session" if "Booth" in location else "Session"))
        i += 1
    return records


def parse_ncte_keynotes_2024():
    url = "https://ncte.org/press-updates/speakers-for-2024-ncte-annual-convention/"
    return [
        make_record(title="Opening Keynote: Ketanji Brown Jackson", conference_name="NCTE Annual Convention 2024", talk_date="November 21, 2024", presenters=["Ketanji Brown Jackson"], source_url=url, city="Boston, MA", session_type="Keynote"),
        make_record(title="Keynote: Kate McKinnon", conference_name="NCTE Annual Convention 2024", talk_date="November 22, 2024", presenters=["Kate McKinnon"], source_url=url, city="Boston, MA", session_type="Keynote"),
        make_record(title="Keynote: Bryan Stevenson", conference_name="NCTE Annual Convention 2024", talk_date="November 23, 2024", presenters=["Bryan Stevenson"], source_url=url, city="Boston, MA", session_type="Keynote"),
        make_record(title="Keynote: Ada Limón", conference_name="NCTE Annual Convention 2024", talk_date="November 24, 2024", presenters=["Ada Limón"], source_url=url, city="Boston, MA", session_type="Keynote"),
    ]


def parse_ncss_keynotes_2024():
    url = "https://penguinrandomhousesecondaryeducation.com/2024/11/04/2024-national-council-for-the-social-studies-ncss-annual-conference/"
    return [
        make_record(title="Keynote: Ta-Nehisi Coates, author of The Message", conference_name="NCSS Annual Conference 2024", talk_date="November 22, 2024, 11:55am-12:45pm", presenters=["Ta-Nehisi Coates"], source_url=url, city="Boston, MA", session_type="Keynote"),
        make_record(title="Keynote: Heather Cox Richardson, author of Democracy Awakening", conference_name="NCSS Annual Conference 2024", talk_date="November 22, 2024, 5:15-6:15pm", presenters=["Heather Cox Richardson"], source_url=url, city="Boston, MA", session_type="Keynote"),
        make_record(title="Keynote: Ken Burns, author of Our America", conference_name="NCSS Annual Conference 2024", talk_date="November 24, 2024, 10:30-11:30am", presenters=["Ken Burns"], source_url=url, city="Boston, MA", session_type="Keynote"),
    ]


def parse_ascd_2025_sessions():
    base = "https://event.ascd.org/2025/program/search/detail_session.php?id="
    known_ids = ["118099699", "118083585", "118110489"]
    records = []
    for sid in known_ids:
        url = base + sid
        html = fetch_text(url)
        if not html:
            continue
        soup = BeautifulSoup(html, "lxml")
        title_elem = soup.find("h1") or soup.find("h2")
        title = title_elem.get_text(strip=True) if title_elem else None
        if not title or "ASCD Annual Conference" in title or len(title) < 5:
            continue
        desc = ""
        for h in soup.find_all(["h3", "h4"]):
            if "session description" in h.get_text(strip=True).lower():
                p = h.find_next("p")
                if p:
                    desc = p.get_text(strip=True)
                break
        when = None
        for b in soup.find_all(["b", "strong"]):
            txt = b.get_text(strip=True)
            if re.search(r'(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)', txt):
                when = txt
                break
        records.append(make_record(
            title=title, conference_name="ASCD Annual Conference 2025",
            talk_date=when, description=desc, source_url=url,
            city="San Antonio, TX", session_type="Session"))
    return records


# ---------------------------------------------------------------------------
# Curated records
# ---------------------------------------------------------------------------

def get_curated_records():
    records = []
    
    # ========== NCTM 2024 Chicago ==========
    terc_sessions = [
        ("Visualizing Verbosity: The Utility Of Visualizations to Facilitate More Robust Math Argumentation Within Middle School Math Classrooms", "September 25, 2024", "11:30 AM – 12:30 PM", "McCormick Place Room 504a", "Round Table Discussions #2", ["Zachary Alstad", "Teresa Lara-Meloy", "Ken Rafanan"]),
        ("Coach-Teacher Teams Transforming Classroom Practice Using Video and Reflections", "September 26, 2024", "11:00 AM – 12:00 PM", "McCormick Place Room 502b", "Session", ["Ken Rafanan", "Jennifer Knudsen", "Teresa Lara-Meloy", "Harriette S Stevens"]),
        ("A Student Reflection Tool For Building and Sustaining Equitable Math Learning Communities", "September 26, 2024", "1:00 PM – 2:15 PM", "McCormick Place Room N230b", "Workshop", ["Annie Sussman", "Marta Garcia"]),
        ("Noticing Middle Schoolers Mathematical Arguments During Class Through Video Enhanced Coaching", "September 26, 2024", "1:00 PM – 2:00 PM", "McCormick Place Room S404 A", "Session", ["Teresa Lara-Meloy", "Jennifer Knudsen", "Ken Rafanan", "Harriette S Stevens"]),
        ("Questioning, Revising, Backtracking: Essentials of Brilliance in Mathematical Argument", "September 27, 2024", "8:00 AM – 9:00 AM", "McCormick Place Room N288", "Session", ["Susan Jo Russell", "Deborah Schifter"]),
        ("From Pockets of Excellence to Collective Efficacy for Ambitious Instruction", "September 27, 2024", "9:30 AM – 10:30 AM", "McCormick Place Room S406A", "Session", ["Dr. DeAnn Huinker", "Dr. Melissa Hedges", "Beth Schefelker", "Rhode Marquez", "Sara Cruz"]),
        ("Building Community in the Elementary Math Classroom: Parents, Co-Educators, and Teachers", "September 27, 2024", "11:00 AM – 12:00 PM", "McCormick Place Room N229", "Session", ["Judy Storeygard", "Lillian Pinet", "Charleen Heard", "Chenetha Lockett"]),
        ("Highlighting Children As Doers of Math: Centering Classroom Discussions on Student Brilliance", "September 27, 2024", "1:00 PM – 2:00 PM", "Hyatt Regency A", "Session", ["Beth Schefelker", "DeAnn Huinker"]),
    ]
    for title, date, time, loc, stype, speakers in terc_sessions:
        records.append(make_record(title=title, conference_name="NCTM Annual Meeting & Exposition 2024", talk_date=f"{date}, {time}", presenters=speakers, source_url="https://www.terc.edu/news/terc-staff-presenting-at-nctm-2024/", location=loc, city="Chicago, IL", session_type=stype))
    
    # HMH NCTM 2024
    records.append(make_record(title="Humanizing Feedback in Mathematics Teacher Education: A Tuning Protocol Approach", conference_name="NCTM Annual Meeting & Exposition 2024", talk_date="September 25, 2024, 8:30 AM", presenters=["Dr. Jennifer Wolfe"], source_url="https://www.hmhco.com/event/nctm-2024", location="McCormick Place, Room S501", city="Chicago, IL", session_type="Author Session"))
    records.append(make_record(title="Smart Students Have 'It'. Correction. All Students Have 'It'!: Empowering Student Success in Math", conference_name="NCTM Annual Meeting & Exposition 2024", talk_date="September 26, 2024, 11:00 AM", presenters=["Dr. Thomasenia Lott Adams"], source_url="https://www.hmhco.com/event/nctm-2024", location="Lakeside Center, Room E354B", city="Chicago, IL", session_type="Author Session"))
    records.append(make_record(title="The Six Secrets To Highly Effective Mathematics Instruction", conference_name="NCTM Annual Meeting & Exposition 2024", talk_date="September 26, 2024, 1:00 PM", presenters=["Dr. Timothy Kanold"], source_url="https://www.hmhco.com/event/nctm-2024", location="Lakeside Center, Room E354B", city="Chicago, IL", session_type="Author Session"))
    records.append(make_record(title="Multiplication Fact Fluency: A School-Wide Solution", conference_name="NCTM Annual Meeting & Exposition 2024", talk_date="September 26, 2024, 4:00 PM", presenters=["Dr. Juli Dixon"], source_url="https://www.hmhco.com/event/nctm-2024", location="McCormick Place, Room N228", city="Chicago, IL", session_type="Author Session"))
    records.append(make_record(title="Four Steps to Fix Math Education", conference_name="NCTM Annual Meeting & Exposition 2024", talk_date="September 27, 2024, 11:00 AM", presenters=["Robert Kaplinsky"], source_url="https://www.hmhco.com/event/nctm-2024", location="Lakeside Center, Room E354A", city="Chicago, IL", session_type="Author Session"))
    records.append(make_record(title="Effective Mathematics Instruction: Cutting Through the Noise", conference_name="NCTM Annual Meeting & Exposition 2024", talk_date="September 28, 2024, 8:00 AM", presenters=["Dr. Matthew Larson"], source_url="https://www.hmhco.com/event/nctm-2024", location="McCormick Place, Room N228", city="Chicago, IL", session_type="Author Session"))
    
    # EDC NCTM 2024
    records.append(make_record(title="Building Local Capacity for Facilitating Professional Learning to Support Math Instruction", conference_name="NCTM Annual Meeting & Exposition 2024", talk_date="September 26, 2024, 12:00 p.m.", presenters=["Babette Moeller", "Matthew McLeod"], description="The Role of Local Facilitators in Scaling Up a Well-Specified Teacher Professional Learning Program.", source_url="https://edc.org/insights/connect-with-edc-at-nctm-2024/", city="Chicago, IL", session_type="Session"))
    records.append(make_record(title="Introducing Data Science to Preschoolers with Hands-on, Physical, and Digital Activities", conference_name="NCTM Annual Meeting & Exposition 2024", talk_date="September 26, 2024, 4:30 p.m.", presenters=["Jessica Young", "Ashley Lewis Presser", "Emily Braham", "Regan Vidiksis"], description="Preschool Data Toolbox - Using digital tools to create child-centered investigations.", source_url="https://edc.org/insights/connect-with-edc-at-nctm-2024/", city="Chicago, IL", session_type="Session"))
    records.append(make_record(title="Questioning, Revising, Backtracking: Essentials of Brilliance in Mathematical Argument", conference_name="NCTM Annual Meeting & Exposition 2024", talk_date="September 27, 2024, 8:00 a.m.", presenters=["Deborah Schifter", "Susan Jo Russell"], description="Mathematical argument in the elementary classroom.", source_url="https://edc.org/insights/connect-with-edc-at-nctm-2024/", city="Chicago, IL", session_type="Session"))
    records.append(make_record(title="Using Digital Activities and Resources to Engage Preschoolers and Preschool Teachers", conference_name="NCTM Annual Meeting & Exposition 2024", talk_date="September 27, 2024, 8:00 a.m.", presenters=["Kristen Reed", "Ashley Lewis Presser", "Jessica Young"], description="Data Collection and Analysis for Preschoolers using digital tools.", source_url="https://edc.org/insights/connect-with-edc-at-nctm-2024/", city="Chicago, IL", session_type="Session"))
    records.append(make_record(title="Making Math Part of Children's Everyday Play", conference_name="NCTM Annual Meeting & Exposition 2024", talk_date="September 27, 2024, 11:30 a.m.", presenters=["Shakesha Thompson", "Kristen Reed", "Jessica Young"], description="Young Mathematicians - Connecting home and school through family math.", source_url="https://edc.org/insights/connect-with-edc-at-nctm-2024/", city="Chicago, IL", session_type="Session"))
    
    # Great Minds NCTM 2024
    greatminds = [
        ("High-Quality Instructional Materials: Coherent, Equitable, and Knowledge-Building Curricula", "September 26, 2024", "8:00 a.m.–9:00 a.m.", "McCormick Place, Room N139"),
        ("Mathematical Coherence: A Long-Term Investment in Students and Teachers", "September 26, 2024", "9:30 a.m.–10:30 a.m.", "McCormick Place, Room N139"),
        ("The Dynamic Middle: Balancing Procedural Fluency, Conceptual Understanding, and Application", "September 26, 2024", "11:00 a.m.–12:00 p.m.", "McCormick Place, Room N139"),
        ("Make It Sticky: Knowledge Building in the Mathematics Classroom", "September 26, 2024", "1:00 p.m.–2:00 p.m.", "McCormick Place, Room N139"),
        ("Show Me Your Way: Connecting Student Thinking During Problem Solving", "September 26, 2024", "2:30 p.m.–3:30 p.m.", "McCormick Place, Room N139"),
        ("Being Multilingual is a Superpower! Multilingual Learners and Eureka Math2", "September 26, 2024", "4:00 p.m.–5:00 p.m.", "McCormick Place, Room N139"),
    ]
    for title, date, time, loc in greatminds:
        records.append(make_record(title=title, conference_name="NCTM Annual Meeting & Exposition 2024", talk_date=f"{date}, {time}", source_url="https://greatminds.org/math/eurekamathsquared/conference/nctm2024", location=loc, city="Chicago, IL", session_type="Breakout Session"))
    
    # MSU NCSM/NCTM 2024
    records.append(make_record(title="Are We Testing What We Value? A Thought-Provoking Exploration of Our Assessment Practices", conference_name="NCSM Annual Conference 2024", talk_date="September 23, 2024, 1:30 PM – 2:30 PM", presenters=["Elizabeth 'Betty' Phillips", "Alden 'AJ' Edson", "Yvonne Slanger-Grant"], description="Ross Taylor/Glenn Gilbert Awardee Lecture", source_url="https://prime.natsci.msu.edu/news/2024-NCSM-NCTM-conferences.aspx", location="Williford A, Floor 3", city="Chicago, IL", session_type="Awardee Lecture"))
    records.append(make_record(title="What Mathematics Is Important in the Third Year of High School Mathematics?", conference_name="NCSM Annual Conference 2024", talk_date="September 23, 2024, 2:45 PM – 3:45 PM", presenters=["Gail Burrill"], source_url="https://prime.natsci.msu.edu/news/2024-NCSM-NCTM-conferences.aspx", location="Blvd C, Floor 2", city="Chicago, IL", session_type="Session"))
    records.append(make_record(title="Algebra Across the K-12 Curriculum – Why Is Understanding the Progression Important for Teachers?", conference_name="NCSM Annual Conference 2024", talk_date="September 24, 2024, 10:30 AM – 11:30 AM", presenters=["Gail Burrill"], source_url="https://prime.natsci.msu.edu/news/2024-NCSM-NCTM-conferences.aspx", location="Williford C, Floor 3", city="Chicago, IL", session_type="Session"))
    records.append(make_record(title="A Co-Inquiry to Advance Justification in Algebra II Classrooms", conference_name="NCTM Annual Meeting & Exposition 2024", talk_date="September 25, 2024, 11:30 AM – 12:30 PM", presenters=["Kristen Bieda"], source_url="https://prime.natsci.msu.edu/news/2024-NCSM-NCTM-conferences.aspx", location="McCormick Place, Room 504a", city="Chicago, IL", session_type="Research Discussion"))
    records.append(make_record(title="Action Research for Productive and Powerful Discourse", conference_name="NCTM Annual Meeting & Exposition 2024", talk_date="September 25, 2024, 2:45 PM – 3:45 PM", presenters=["Beth Herbel-Eisenmann"], source_url="https://prime.natsci.msu.edu/news/2024-NCSM-NCTM-conferences.aspx", location="McCormick Place, Room 505a", city="Chicago, IL", session_type="Session"))
    records.append(make_record(title="Using Interactive Dynamic Technology to Develop Understanding in Algebra II and Precalculus", conference_name="NCTM Annual Meeting & Exposition 2024", talk_date="September 26, 2024, 8:00 AM – 9:00 AM", presenters=["Gail Burrill"], source_url="https://prime.natsci.msu.edu/news/2024-NCSM-NCTM-conferences.aspx", location="McCormick Place, Room 502b", city="Chicago, IL", session_type="Session"))
    records.append(make_record(title="Artificial Intelligence in Mathematics Education: Using Machine Learning to Support Learning", conference_name="NCTM Annual Meeting & Exposition 2024", talk_date="September 26, 2024, 1:00 PM – 2:00 PM", presenters=["AJ Edson", "Ashley Fabry", "Taren Going", "Sunyoung Park"], source_url="https://prime.natsci.msu.edu/news/2024-NCSM-NCTM-conferences.aspx", location="McCormick Place, Room N229", city="Chicago, IL", session_type="Session"))
    records.append(make_record(title="Assessing the 'What' and 'How' of Algebra for the Future", conference_name="NCTM Annual Meeting & Exposition 2024", talk_date="September 27, 2024, 4:00 PM – 5:00 PM", presenters=["Elizabeth Phillips", "AJ Edson", "Yvonne Slanger-Grant"], source_url="https://prime.natsci.msu.edu/news/2024-NCSM-NCTM-conferences.aspx", location="McCormick Place, Room N135", city="Chicago, IL", session_type="Session"))
    records.append(make_record(title="Celebrating Students' Mathematical Thinking: Experiencing STEM Problems on Proportional Reasoning", conference_name="NCTM Annual Meeting & Exposition 2024", talk_date="September 28, 2024, 9:45 AM – 11:00 AM", presenters=["Yvonne Slanger-Grant", "AJ Edson"], source_url="https://prime.natsci.msu.edu/news/2024-NCSM-NCTM-conferences.aspx", location="McCormick Place, Room N426b", city="Chicago, IL", session_type="Workshop"))
    records.append(make_record(title="Developing a Machine Learning Rubric for Proportional Reasoning in Digital Curricula", conference_name="NCTM Annual Meeting & Exposition 2024", talk_date="September 28, 2024, 11:00 AM – 12:00 PM", presenters=["Gail Burrill"], source_url="https://prime.natsci.msu.edu/news/2024-NCSM-NCTM-conferences.aspx", location="McCormick Place, Room N427d", city="Chicago, IL", session_type="Session"))
    records.append(make_record(title="Lighting the Way to Learning: Lessons Developing Algebraic Thinking From Presidential Awardees", conference_name="NCTM Annual Meeting & Exposition 2024", talk_date="September 28, 2024, 11:00 AM – 12:00 PM", presenters=["Gail Burrill"], source_url="https://prime.natsci.msu.edu/news/2024-NCSM-NCTM-conferences.aspx", location="McCormick Place, Room S404d", city="Chicago, IL", session_type="President Series Session"))
    
    # mathimprovement.org
    records.append(make_record(title="Access to Algebra", conference_name="NCTM Annual Meeting & Exposition 2024", talk_date="September 26, 2024", presenters=["CPS & M-DCPS District Leaders"], description="NMIP district leaders presented on efforts to improve math instruction and support access to algebra.", source_url="https://mathimprovement.org/", city="Chicago, IL", session_type="Session"))
    records.append(make_record(title="Coaching Models", conference_name="NCTM Annual Meeting & Exposition 2024", talk_date="September 26, 2024", presenters=["HISD & NYCPS District Leaders"], description="NMIP district leaders presented on coaching models for math instruction improvement.", source_url="https://mathimprovement.org/", city="Chicago, IL", session_type="Session"))
    records.append(make_record(title="Scaling HQIM Implementation", conference_name="NCTM Annual Meeting & Exposition 2024", talk_date="September 26, 2024", presenters=["LAUSD & SDP District Leaders"], description="NMIP district leaders presented on scaling high-quality instructional materials in math.", source_url="https://mathimprovement.org/", city="Chicago, IL", session_type="Session"))
    
    # NCTM Regional Seattle 2024
    records.append(make_record(title="NCTM 2024 Regional Conference & Exposition", conference_name="NCTM Regional Conference & Exposition 2024", talk_date="February 7-9, 2024", source_url="https://www.nctm.org/Seattle2024/", city="Seattle, WA", session_type="Conference"))
    
    # ========== NCTM 2023 DC ==========
    records.append(make_record(title="From the Personal to the Political and Back: Using Positioning Theory as an Analytic Lens and Potential Tool for Disruption", conference_name="NCTM Research Conference 2023", talk_date="October 25, 2023, 9:30 AM – 10:45 AM", presenters=["Dr. Beth Herbel-Eisenmann", "Dr. Beatriz Quintos"], source_url="https://prime.natsci.msu.edu/news/msu-math-ed-at-2023-nctm-and-ncsm.aspx", location="Walter E. Washington Convention Center Room 202A", city="Washington, DC", session_type="Research Report"))
    records.append(make_record(title="Stats and Tech Literacy: Supporting Student Agency and Identity Using Technology and Real Data", conference_name="NCTM Research Conference 2023", talk_date="October 25, 2023, 3:35 PM", presenters=["Gail Burrill"], source_url="https://prime.natsci.msu.edu/news/msu-math-ed-at-2023-nctm-and-ncsm.aspx", location="Walter E. Washington Convention Center Room 203AB", city="Washington, DC", session_type="Research Report"))
    records.append(make_record(title="Open Doors for Students by Leveraging the Role of Technology", conference_name="NCTM Annual Meeting & Exposition 2023", talk_date="October 26, 2023, 11:00 AM – 12:00 PM", presenters=["Gail Burrill"], description="Technology contributes to student success and gives students opportunities to engage in interesting and challenging mathematics.", source_url="https://prime.natsci.msu.edu/news/msu-math-ed-at-2023-nctm-and-ncsm.aspx", location="Walter E. Washington Convention Center Room 146B", city="Washington, DC", session_type="Session"))
    records.append(make_record(title="Mathematical Practices: The Pathway to Equitable, Rigorous PBL Projects", conference_name="NCTM Annual Meeting & Exposition 2023", talk_date="October 27, 2023, 2:30 PM – 3:30 PM", presenters=["Sheila Orr", "Sarah DiMaria", "Carlee Madis"], description="Project-based learning is a powerful tool for students to engage deeply with and see themselves in mathematics.", source_url="https://prime.natsci.msu.edu/news/msu-math-ed-at-2023-nctm-and-ncsm.aspx", location="Walter E. Washington Convention Center Ballroom B", city="Washington, DC", session_type="Session"))
    records.append(make_record(title="President Series: What Does Algebra Look Like across the K-12 Curriculum: Experience the Progression!", conference_name="NCTM Annual Meeting & Exposition 2023", talk_date="October 28, 2023, 11:00 AM – 12:00 PM", presenters=["Gail Burrill", "Regina Kilday", "Jana Dean", "Lisa Conzemius"], description="Presidential Awardees will share creative ideas for teaching algebra and showing how fundamental algebraic concepts connect throughout a student's career.", source_url="https://prime.natsci.msu.edu/news/msu-math-ed-at-2023-nctm-and-ncsm.aspx", location="Walter E. Washington Convention Center Ballroom A", city="Washington, DC", session_type="President Series"))
    records.append(make_record(title="Let's Take Formative Assessment Seriously", conference_name="NCSM Annual Conference 2023", talk_date="October 31, 2023, 9:15 AM – 10:15 AM", presenters=["Gail Burrill"], description="Formative assessment is a powerful tool for ensuring that all students have their thinking heard.", source_url="https://prime.natsci.msu.edu/news/msu-math-ed-at-2023-nctm-and-ncsm.aspx", location="Westin Washington DC, Room 14", city="Washington, DC", session_type="Session"))
    
    # HMH NCTM 2023
    hmh2023 = [
        ("Trending Now: Using the Spies and Analyst Approach to Define What it Means to Go Viral", "October 26, 2023", "9:30 AM", "Aaron Levy", "Into AGA"),
        ("Dare to Differentiate in your Middle School Classroom", "October 26, 2023", "10:00 AM", "Aaron Levy", "Into Math"),
        ("The Power of Gamification", "October 26, 2023", "10:30 AM", "Rachel Hester", "Waggle"),
        ("Math 180 Flex: Intervention in the CORE Classroom", "October 26, 2023", "2:30 PM", "Mike Wagner", "Math 180"),
        ("Unlocking Understanding: Using Language Routines in the Math Classroom", "October 26, 2023", "3:00 PM", "Margaret Seclen", "Go Math!"),
        ("The Power of Gamification (repeat)", "October 26, 2023", "3:30 PM", "Rachel Hester", "Waggle"),
        ("Connect with an HMH Coach", "October 26, 2023", "4:00 PM", "Michelle Tan", "Professional Learning"),
        ("Connect with an HMH Coach", "October 27, 2023", "11:30 AM", "Michelle Tan", "Professional Learning"),
        ("Supporting Students with Learning Disabilities: Math 180, CASE-Endorsed Intensive Intervention", "October 27, 2023", "1:30 PM", "Mike Wagner", "Math 180"),
        ("The Power of Gamification", "October 27, 2023", "2:00 PM", "Rachel Hester", "Waggle"),
        ("Unlocking Understanding: Using Language Routines in the Math Classroom", "October 27, 2023", "2:30 PM", "Margaret Seclen", "Go Math!"),
        ("Adaptive Practice Made Easy with Waggle!", "October 27, 2023", "3:00 PM", "Margaret Seclen", "Waggle"),
        ("Problem Solving with Math in Focus", "October 27, 2023", "3:30 PM", "Aaron Levy", "Math in Focus"),
        ("Dare to Differentiate in your Middle School Classroom", "October 27, 2023", "4:00 PM", "Aaron Levy", "Into Math"),
    ]
    for title, date, time, presenter, prog in hmh2023:
        records.append(make_record(title=title, conference_name="NCTM Annual Meeting & Exposition 2023", talk_date=f"{date}, {time}", presenters=[presenter], description=f"Program: {prog}", source_url="https://www.hmhco.com/event/nctm-2023", city="Washington, DC", session_type="In-Booth Presentation"))
    
    records.append(make_record(title="Empower or Bust in the Mathematics Classroom: Affirmations, Engagement, Content, and Relationships with Students", conference_name="NCTM Annual Meeting & Exposition 2023", talk_date="October 26, 2023, 9:45 AM", presenters=["Dr. Thomasenia Lott Adams"], source_url="https://www.hmhco.com/event/nctm-2023", location="Convention Center, Room 149AB", city="Washington, DC", session_type="Author Session"))
    records.append(make_record(title="Trying to Find Your Way in Mathematics Education: Thomasenia Adams and Juli Dixon Share Their Journeys", conference_name="NCTM Annual Meeting & Exposition 2023", talk_date="October 27, 2023, 1:00 PM", presenters=["Dr. Thomasenia Lott Adams", "Dr. Juli Dixon"], source_url="https://www.hmhco.com/event/nctm-2023", location="Archives", city="Washington, DC", session_type="Author Session"))
    records.append(make_record(title="Reinventing Mathematics Intervention: Making Time for Understanding", conference_name="NCTM Annual Meeting & Exposition 2023", talk_date="October 26, 2023, 4:00 PM", presenters=["Dr. Juli Dixon"], source_url="https://www.hmhco.com/event/nctm-2023", location="Ballroom A", city="Washington, DC", session_type="Author Session"))
    
    # NCTM 2023 keynotes
    records.append(make_record(title="Rehumanizing Mathematics: A Vision for the Future", conference_name="NCTM Annual Meeting & Exposition 2023", talk_date="October 25-28, 2023", presenters=["Dr. Rochelle Gutiérrez"], source_url="https://steamspirationshub.com/blogs/news/stem-education-conferences-top-5-to-attend-in-2023", city="Washington, DC", session_type="Keynote"))
    records.append(make_record(title="Mathematical Mindsets: The Key to Equitable and Joyful Math Learning", conference_name="NCTM Annual Meeting & Exposition 2023", talk_date="October 25-28, 2023", presenters=["Dr. Jo Boaler"], source_url="https://steamspirationshub.com/blogs/news/stem-education-conferences-top-5-to-attend-in-2023", city="Washington, DC", session_type="Keynote"))
    
    # ========== ISTE 2023 Philadelphia ==========
    iste2023 = [
        ("Creating Projects for the Planet: Climate Action Education for PK-12 Classrooms", "June 28, 2023", "10:30am ET", ["Take Action Global"]),
        ("Teach Boldly Resource Share: Using Edtech for Social Good", "June 26, 2023", "12:30pm ET", ["Take Action Global"]),
        ("Connecting with Global Classrooms: Using Virtual Exchange for International and Interdisciplinary Collaborations", "June 27, 2023", "11:30am ET", ["Take Action Global"]),
        ("Global Collaboration Playground: Passport to Social Good", "June 28, 2023", "9:00am ET", ["Take Action Global"]),
        ("ISTE Books Open House: Meet Your Favorite Authors featuring Teach Boldly", "June 26, 2023", "3:00pm ET", ["Jennifer Williams"]),
        ("Technology for Good: Using Educational Technology to Drive Social Change", "June 26, 2023", "4:00pm ET", ["Take Action Global"]),
    ]
    for title, date, time, presenters in iste2023:
        records.append(make_record(title=title, conference_name="ISTE Live 2023", talk_date=f"{date}, {time}", presenters=presenters, source_url="https://www.takeactionglobal.org/lets-take-action-at-istelive-2023/", city="Philadelphia, PA", session_type="Session"))
    
    # ========== ISTE 2024 BrainPOP ==========
    brainpop_iste2024 = [
        ("Tales from the Field: Empowering Student-Led Learning Using BrainPOP", "June 24, 2024", "9:30-9:45 AM", ["Rayna Freedman"]),
        ("Science of Reading and BrainPOP's New Literacy Focus", "June 24, 2024", "10:00-10:15 AM", ["BrainPOP Team"]),
        ("Empowering Students through Engineering Design", "June 24, 2024", "10:30-10:45 AM", ["Nick Provenzano"]),
        ("Level the Playing Field: Differentiate Your Lessons with BrainPOP 3-8+", "June 24, 2024", "11:00-11:15 AM", ["BrainPOP Team"]),
        ("Tim, Moby, and the Power of a Pause", "June 24, 2024", "11:30-11:45 AM", ["BrainPOP Team"]),
        ("Reporting with a Reason: Harness the Power of Teacher Reports in BrainPOP 3-8+", "June 24, 2024", "12:00-12:15 PM", ["BrainPOP Team"]),
        ("Playful with a Purpose: Exploring BrainPOP Jr. for K-3", "June 24, 2024", "12:30-12:45 PM", ["BrainPOP Team"]),
        ("Multilingual and Multimodal: Supporting ELL Students in BrainPOP 3-8+", "June 24, 2024", "1:00-1:15 PM", ["BrainPOP Team"]),
        ("Empowering Scientific Minds: The Vital Role of CERs in Fostering Scientific Reasoning", "June 24, 2024", "2:30-3:00 PM", ["Dr. Melissa Hogan", "Dr. Michelle Newstadt"]),
        ("ISTE Seal: BrainPOP Science Poster Session", "June 24, 2024", "4:00 PM", ["Dr. Michelle Newstadt"]),
        ("ISTE Seal: BrainPOP 3-8+ Poster Session", "June 25, 2024", "1:00 PM", ["Dr. Barbara Hubert"]),
    ]
    for title, date, time, presenters in brainpop_iste2024:
        records.append(make_record(title=title, conference_name="ISTE Live 2024", talk_date=f"{date}, {time}", presenters=presenters, source_url="https://go.brainpop.com/iste2024", city="Denver, CO", session_type="In-Booth Session"))
    
    # ========== NSTA 2024 ==========
    records.append(make_record(title="5D Assessment: Using student interest and identity to design meaningful, phenomenon-driven assessment opportunities", conference_name="NSTA National Conference 2024", talk_date="November 8, 2024, 10:40 AM – 11:40 AM", presenters=["Elaine Klein"], description="Learn how student interest and identity are co-equal dimensions when designing phenomenon-driven assessments aligned to NGSS.", source_url="https://bscs.org/resources/nsta-2024-new-orleans/", location="New Orleans Ernest N. Morial Convention Center – 272", city="New Orleans, LA", session_type="Hands-On Workshop"))
    records.append(make_record(title="OpenSciEd for Elementary is HERE!", conference_name="NSTA National Conference 2024", talk_date="November 6, 2024, 8:15 AM – 3:15 PM", presenters=["Susan Gomez Zwiep", "Janna Mahfoud", "Yanira Vazquez"], description="Learn about the new OpenSciEd program for elementary grades. Supports three-dimensional science learning for all students.", source_url="https://bscs.org/resources/nsta-2024-new-orleans/", location="Hilton New Orleans Riverside – Canal", city="New Orleans, LA", session_type="Professional Learning Institute"))
    records.append(make_record(title="Leadership for Evaluating and Selecting Instructional Materials Using NextGen TIME", conference_name="NSTA National Conference 2024", talk_date="November 7, 2024, 8:00 AM – 9:00 AM", presenters=["Jenine Cotton-Proby"], description="NextGen TIME supports districts in evaluating instructional materials for quality and design for the Next Generation Science Standards.", source_url="https://bscs.org/resources/nsta-2024-new-orleans/", location="New Orleans Ernest N. Morial Convention Center – 267", city="New Orleans, LA", session_type="Presentation"))
    records.append(make_record(title="Engaging All Students in STEM", conference_name="NSTA National Conference 2024", talk_date="November 7, 2024, 2:20 – 3:20 pm", presenters=["Teach Engineering Staff"], description="Learn how engineering design and design thinking can enhance K-12 student engagement and integrate engineering concepts with hands-on science activities.", source_url="https://ncwit.org/event/teach-engineering-nsta-2024/", location="New Orleans Ernest N. Morial Convention Center – 293", city="New Orleans, LA", session_type="Workshop"))
    records.append(make_record(title="Speed Sharing: Empowering Middle School Teachers", conference_name="NSTA National Conference 2024", talk_date="November 8, 2024, 1:20 – 2:20 pm", presenters=["Teach Engineering Staff"], description="Free online STEM resources from the Teach Engineering Digital Library for formal and informal educators.", source_url="https://ncwit.org/event/teach-engineering-nsta-2024/", location="New Orleans Ernest N. Morial Convention Center – 278", city="New Orleans, LA", session_type="Speed Sharing"))
    records.append(make_record(title="Poster: Standards-Aligned STEM Resources", conference_name="NSTA National Conference 2024", talk_date="November 9, 2024, 12 – 1 pm", presenters=["Teach Engineering Staff"], description="Teach Engineering provides free STEM resources that are educator-created, classroom-tested, peer-reviewed and NGSS-aligned.", source_url="https://ncwit.org/event/teach-engineering-nsta-2024/", location="Convention Center Exhibit Hall – Poster Session Aisle", city="New Orleans, LA", session_type="Poster"))
    records.append(make_record(title="How to Create Three-Dimensional Assessment Tasks", conference_name="NSTA National Conference 2024", talk_date="March 20, 2024, 8:00 a.m.–3:15 p.m.", presenters=["Joseph Krajcik", "Christopher Harris"], description="Short Course Session - Research to Practice strand.", source_url="https://www.wested.org/event/nsta-2024/", location="Colorado Convention Center – 107/109", city="Denver, CO", session_type="Short Course"))
    records.append(make_record(title="Needs Sensing During Curriculum Implementation: Gathering and Incorporating Feedback from Teachers to Improve Instruction", conference_name="NSTA National Conference 2024", talk_date="March 21, 2024, 2:45 p.m.–4:15 p.m.", presenters=["Vanessa Wolbrink", "Jenny Sarna", "Andy Weatherhead"], description="Leadership and Advocacy strand.", source_url="https://www.wested.org/event/nsta-2024/", location="Hyatt Regency Denver – Capitol Ballroom 1", city="Denver, CO", session_type="Presentation"))
    records.append(make_record(title="Science Notebooks as Tools for Guiding Instruction Around Students' Ideas", conference_name="NSTA National Conference 2024", talk_date="March 22, 2024, 9:20 a.m.–10:20 a.m.", presenters=["Jill Grace", "Jill Wertheim"], description="Hands-On Workshop - Instruction and Assessment: Implementing Standards strand.", source_url="https://www.wested.org/event/nsta-2024/", location="Colorado Convention Center – 210/212", city="Denver, CO", session_type="Hands-On Workshop"))
    records.append(make_record(title="Maps, Scatterplots, Histograms, and More: Leveraging NASA Data to Explore Wildfires", conference_name="NSTA National Conference 2024", talk_date="March 22, 2024, 1:20 p.m.–2:20 p.m.", presenters=["Karen Lionberger", "Sara Salisbury"], description="Teaching Strategies and Classroom Practice strand.", source_url="https://www.wested.org/event/nsta-2024/", location="Colorado Convention Center – Bluebird Ballroom 3H", city="Denver, CO", session_type="Hands-On Workshop"))
    records.append(make_record(title="Asset-Based 3D Assessment Using Ambitious Science Teaching (AST) to Drive Equitable Teaching and Learning", conference_name="NSTA National Conference 2024", talk_date="March 22, 2024, 4:00 p.m.–5:00 p.m.", presenters=["Jill Wertheim"], description="Instruction and Assessment: Implementing Standards strand.", source_url="https://www.wested.org/event/nsta-2024/", location="Colorado Convention Center – Bluebird Ballroom 3E", city="Denver, CO", session_type="Hands-On Workshop"))
    records.append(make_record(title="Using Photographs and Data Stories to Support Data Science in STEM", conference_name="NSTA National Conference 2024", talk_date="March 22, 2024, 4:00 p.m.–5:00 p.m.", presenters=["Leticia Perez"], description="Instruction and Assessment: Implementing Standards strand.", source_url="https://www.wested.org/event/nsta-2024/", location="Colorado Convention Center – Bluebird Ballroom 3F", city="Denver, CO", session_type="Hands-On Workshop"))
    records.append(make_record(title="Climate Justice Overview: Priority Areas and Educational Approaches", conference_name="NSTA National Conference 2024", talk_date="November 7, 2024, 8:00-9:00 AM", presenters=["Philip Bell", "Kelsie Fowler", "Deb Morrison", "Nancy Price"], description="Science education has a key role to play in supporting a just response to the climate crisis.", source_url="https://stemteachingtools.org/news/2024/nsta-nola-2024", location="Ernest N. Morial Convention Center - 276", city="New Orleans, LA", session_type="Session"))
    records.append(make_record(title="Teaching about the Intersections of Biology, Race, and Racism: Strategies, Curriculum Resources, and Research", conference_name="NSTA National Conference 2024", talk_date="November 7, 2024, 1:00-2:00 PM", presenters=["Jeanne Chowning", "Michal Robinson", "Deb Morrison", "Kelsie Fowler"], description="Participants will examine resources for engaging students in respectful and productive activity that contrast the social construct of race with scientific understandings of genetics.", source_url="https://stemteachingtools.org/news/2024/nsta-nola-2024", location="Ernest N. Morial Convention Center - 276", city="New Orleans, LA", session_type="Session"))
    records.append(make_record(title="Organizing Small Group Classroom Talk to Hear All Students' Ideas: Equity-focused 3D Formative Assessment Through Talk", conference_name="NSTA National Conference 2024", talk_date="November 7, 2024, 2:20-3:20 PM", presenters=["Deb Morrison", "Kelsie Fowler"], description="Talk strategies specifically designed for improving classroom equity while engaging in STEM learning experiences.", source_url="https://stemteachingtools.org/news/2024/nsta-nola-2024", location="Ernest N. Morial Convention Center - 276", city="New Orleans, LA", session_type="Workshop"))
    records.append(make_record(title="How to Adapt Instructional Materials to Focus on Climate Justice (Physics)", conference_name="NSTA National Conference 2024", talk_date="November 7, 2024, 3:40-4:40 PM", presenters=["Kelsie Fowler", "Philip Bell"], description="How instructional materials can be adapted for local contexts to elevate issues of climate justice and ethical responses to the climate crisis.", source_url="https://stemteachingtools.org/news/2024/nsta-nola-2024", location="Ernest N. Morial Convention Center - 276", city="New Orleans, LA", session_type="Session"))
    
    # NSTA 2023
    records.append(make_record(title="World's 1st Indoor Skydiving Robotics Program for Girls and Gender Expansive Youth", conference_name="NSTA National Conference 2023", talk_date="March 22-25, 2023", presenters=["Kenny Bae"], description="Developing and piloting the world's first skydiving robot competition program specifically designed for girls and gender-expansive youth ages 9-18.", source_url="https://ubtecheducation.com/nsta-2023-presentation-teacher-ambassador-kenny-bae/", city="Atlanta, GA", session_type="Presentation"))
    
    # ========== NCTE 2024 ==========
    records.append(make_record(title="Re-envisioning the Conditions of Writing Workshop in Order to Teach to Student Need, Equity, and Social Justice", conference_name="NCTE Annual Convention 2024", talk_date="November 22, 2024", presenters=["Doug Kaufman", "Tracey Lafayette"], description="Empowering students with writing.", source_url="https://twowritingteachers.org/2024/11/25/reflections-from-ncte-2024/", city="Boston, MA", session_type="Session"))
    records.append(make_record(title="Project-Based Research for Student Achievement", conference_name="NCTE Annual Convention 2024", talk_date="November 22, 2024", presenters=["Lauren Malanka", "Dana Maloney"], description="Presented at the NCTE Convention on fostering student achievement through project-based research.", source_url="https://thetenaflyecho.com/25959/showcase/mrs-malanka-presents-at-2024-ncte-convention/", city="Boston, MA", session_type="Session"))
    records.append(make_record(title='"It\'s About Time": Centering, Supporting, and Learning from HBCUs and Black Brilliance at NCTE', conference_name="NCTE Annual Convention 2024", talk_date="November 22, 2024", presenters=["Dr. Valerie Kinloch"], description="Featured session on centering HBCUs and Black brilliance in literacy education.", source_url="https://ncte.org/wp-content/uploads/2024_NCTE_Annual_Report.pdf", city="Boston, MA", session_type="Featured Session"))
    records.append(make_record(title="Sustaining Youth Voice in NCTE and Beyond: An Opening Dialogue", conference_name="NCTE Annual Convention 2024", talk_date="November 23, 2024", presenters=["Limarys Caraballo", "Lauren Leigh Kelly", "Nicole Mirra", "Leigh Patel", "Estrella Torrez", "Vaughn Watson"], description="Intergenerational speculative session on youth engagement and leadership at NCTE.", source_url="https://ncte.org/wp-content/uploads/2024_NCTE_Annual_Report.pdf", city="Boston, MA", session_type="Session"))
    records.append(make_record(title="Toward Solidarity/Beyond Solidarity: (Re)Envisioning Conexiones in Research and Teaching with Black, Asian, Latinx, and Indigenous Communities", conference_name="NCTE Annual Convention 2024", talk_date="November 23, 2024", presenters=["Jin Kyeong Jung", "Vaughn Watson", "Alice Lee", "Yolanda Sealey-Ruiz", "Danny Martinez", "Grace Player"], description="Educators and researchers showcased how communities move toward solidarity with youth and immigrant communities.", source_url="https://ncte.org/wp-content/uploads/2024_NCTE_Annual_Report.pdf", city="Boston, MA", session_type="Session"))
    records.append(make_record(title="Black Teacher Educators Centering Black Intellectualism and Humanity in Their Theory, Pedagogy, & Praxis", conference_name="NCTE Annual Convention 2024", talk_date="November 23, 2024", presenters=["Brooke Harris Gara", "Wintre Foxworth Johnson", "Davena Jackson", "Justin Coles"], description="Black teacher educators explore how they make Black intellectual thought prominent in their teaching.", source_url="https://ncte.org/wp-content/uploads/2024_NCTE_Annual_Report.pdf", city="Boston, MA", session_type="Session"))
    records.append(make_record(title="Youth Ingenuity and Artificial Intelligence", conference_name="NCTE Annual Convention 2024", talk_date="November 24, 2024", presenters=["Jennifer Higgs", "Clifford Lee", "Jose Lizarraga", "Anna Smith"], description="Exploring the intersection of youth creativity and artificial intelligence in literacy education.", source_url="https://ncte.org/wp-content/uploads/2024_NCTE_Annual_Report.pdf", city="Boston, MA", session_type="Session"))
    
    # NCTE-NCTM Joint 2024
    records.append(make_record(title="NCTE-NCTM Joint Conference on Elementary Literacy & Mathematics", conference_name="NCTE-NCTM Joint Conference 2024", talk_date="June 17-19, 2024", source_url="https://www.nctm.org/ncte24/", city="New Orleans, LA", session_type="Conference"))
    
    # ========== ASCD ==========
    records.append(make_record(title="Understanding by Design: Creating High-Quality Units", conference_name="ASCD Annual Conference 2024", talk_date="March 2024", presenters=["Jay McTighe"], source_url="https://event.ascd.org/2024/program/search/", city="Washington, DC", session_type="Workshop"))
    records.append(make_record(title="Empowering Culturally Responsive Teaching with Educational Technology", conference_name="ASCD Annual Conference 2025", talk_date="June 29, 2025", source_url="https://event.ascd.org/2025/program/search/detail_session.php?id=118110489", city="San Antonio, TX", session_type="Workshop"))
    
    # ========== NCSS 2024 ==========
    records.append(make_record(title="NCSS 104th Annual Conference", conference_name="NCSS Annual Conference 2024", talk_date="November 22-24, 2024", source_url="https://www.socialstudies.org/", city="Boston, MA", session_type="Conference"))
    
    # ========== Additional cross-cutting ==========
    records.append(make_record(title="Media Arts in STEAM Education", conference_name="ISTE Live 2024", talk_date="June 23-26, 2024", presenters=["Barbara Liedahl"], source_url="https://www.mediaartsedu.org/news", city="Denver, CO", session_type="Session"))
    records.append(make_record(title="Artificial Intelligence in Special Education: Paradigms, Programs, and Possibilities", conference_name="ISTE Live 2024", talk_date="June 2024", presenters=["Eleazar Vasquez", "James Basham", "Amit Kishore", "John Britten", "Thomas Courchaine"], description="Invited Panel Discussion on AI in Special Education at ISTE 2024.", source_url="https://specialedu.ku.edu/sites/specialedu/files/attached-files/T_Vasquez-08-19-25.pdf", city="Denver, CO", session_type="Panel"))
    
    # NCTM 2024 Research Conference (from Illinois State report)
    records.append(make_record(title="Adapting Lesson Study to Enhance Tutors' Understanding of Professional Knowledge for Tutoring", conference_name="NCTM Research Conference 2024", talk_date="September 25-27, 2024", presenters=["J. Barrett", "J. Kang", "C. Zuiderveen", "C. Borders", "C.A. Courtad"], source_url="https://education.illinoisstate.edu/downloads/2024%20Scholarship%20and%20Research%20Report%20FINAL%20022725.pdf", city="Chicago, IL", session_type="Research Report"))
    
    return records


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    os.makedirs("data", exist_ok=True)
    all_records = []
    
    sources = [
        ("ISTE ControlAltAchieve 2024", parse_iste_controlaltachieve_2024),
        ("SMART ISTE 2024", parse_smart_iste_2024),
        ("NCTE Keynotes 2024", parse_ncte_keynotes_2024),
        ("NCSS Keynotes 2024", parse_ncss_keynotes_2024),
        ("ASCD 2025", parse_ascd_2025_sessions),
        ("Curated", get_curated_records),
    ]
    
    for name, func in sources:
        try:
            recs = func()
            print(f"  {name}: {len(recs)} records")
            all_records.extend(recs)
        except Exception as e:
            print(f"  {name}: ERROR - {e}")
    
    # Deduplicate
    seen = set()
    unique_records = []
    for r in all_records:
        key = (r["title"].lower(), r["conference_name"].lower(), r["talk_date"].lower())
        if key not in seen and r["title"]:
            seen.add(key)
            unique_records.append(r)
    
    output_path = "data/teacher_conference_talks.csv"
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        fieldnames = [
            "title", "conference_name", "talk_date", "presenters",
            "description", "source_url", "location", "city",
            "session_type", "scraped_at", "confidence"
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in unique_records:
            writer.writerow(r)
    
    print(f"\nWrote {len(unique_records)} unique records to {output_path}")
    
    from collections import Counter
    conf_counts = Counter(r["conference_name"] for r in unique_records)
    print("\nBreakdown by conference:")
    for conf, count in conf_counts.most_common():
        print(f"  {conf}: {count}")


if __name__ == "__main__":
    main()
