#!/usr/bin/env python3
"""
Fetch NYU course data from Schedge and write a minimal QuACS-style JSON.

MVP choices:
- Pull a small slice (one school+subject) for Fall 2025 to prove the pipeline.
- You can expand to all schools/subjects after MVP works.

NOTE: Schedge API base and endpoints may evolve. If an endpoint 404s, open
the docs page in a browser and copy the current path, then update BASE/API below.
Docs: https://nyu.a1liu.com/api/
Repo: https://github.com/BUGS-NYU/schedge
"""

import json, os, sys, time
from pathlib import Path
from typing import Dict, Any, List
import requests

BASE = "https://nyu.a1liu.com/api"
# Common patterns (adjust if docs show different versions/paths):
TERMS_ENDPOINT = f"{BASE}/v3/terms"
# Example endpoints you can try if above differ:
# SUBJECTS_ENDPOINT = f"{BASE}/v3/subjects"  # often needs ?year=YYYY&term=fa&school=EG
# COURSES_ENDPOINT  = f"{BASE}/v3/courses"   # often needs params year, term, school, subject

OUT_DIR = Path("semester_data/2025/fa")
OUT_DIR.mkdir(parents=True, exist_ok=True)
OUT_FILE = OUT_DIR / "courses.json"

# Choose one school+subject for MVP (easy to change here)
MVP_SCHOOL = "EG"      # Tandon
MVP_SUBJECT = "CS"     # Computer Science (example subject – change as you like)
YEAR = 2025
TERM = "fa"            # fa, sp, su

def get_json(url: str, params: Dict[str, Any] = None) -> Any:
    r = requests.get(url, params=params, timeout=30)
    r.raise_for_status()
    return r.json()

def guess_schedge_endpoints() -> Dict[str, str]:
    """
    Try to infer/construct endpoints Schedge commonly uses.
    If docs change, tweak here. We keep this centralized for easy fixes.
    """
    endpoints = {
        "subjects": f"{BASE}/v3/subjects",
        "courses":  f"{BASE}/v3/courses",
    }
    return endpoints

def fetch_courses(year: int, term: str, school: str, subject: str) -> List[Dict[str, Any]]:
    eps = guess_schedge_endpoints()
    # Typical Schedge query params (adjust if docs specify differently)
    params = {"year": year, "term": term, "school": school, "subject": subject}
    data = get_json(eps["courses"], params=params)
    # Expecting a list of course dicts with sections/meetings inside
    return data

def transform_to_quacs_schema(raw_courses: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Produce a minimal schema the QuACS UI can read.
    Since QuACS is flexible, we mirror quacs-data style:
    - top-level { "courses": [ ... ] }
    - each course has: id, subject, number, title, credits
    - sections array with: crn/section, instructors, meetings [{days, start, end, campus, room}]
    """
    out_courses = []
    for c in raw_courses:
        # Schedge field names vary; we map defensively.
        subject = c.get("subjectCode") or c.get("subject") or ""
        number  = c.get("courseNumber") or c.get("code") or c.get("catalogNumber") or ""
        title   = c.get("name") or c.get("title") or ""
        credits = c.get("credits") or c.get("minCredits") or 0

        # Schedge often has "sections" with meeting patterns
        sections_out = []
        for s in c.get("sections", []):
            sec_code = s.get("sectionCode") or s.get("code") or s.get("registrationNumber") or ""
            instrs = []
            for i in s.get("instructors", []):
                # Normalize instructor name
                name = i.get("name") or f"{i.get('firstName','')} {i.get('lastName','')}".strip()
                if name:
                    instrs.append(name)

            meetings_out = []
            for m in s.get("meetings", []):
                days = m.get("days") or m.get("pattern") or ""
                meetings_out.append({
                    "days": days,                          # e.g., "MWF" or "TuTh"
                    "start": m.get("startTime"),           # "09:00"
                    "end": m.get("endTime"),               # "10:15"
                    "campus": m.get("campus") or m.get("campusName"),
                    "building": m.get("building") or m.get("buildingName"),
                    "room": m.get("room") or "",
                    "modality": m.get("instructionMode") or m.get("mode") or ""
                })

            sections_out.append({
                "section": sec_code,
                "instructors": instrs,
                "meetings": meetings_out
            })

        out_courses.append({
            "id": f"{subject} {number}".strip(),
            "subject": subject,
            "number": str(number),
            "title": title,
            "credits": credits,
            "sections": sections_out
        })

    return {"courses": out_courses}

def main():
    print("Fetching terms (sanity check)…")
    try:
        terms = get_json(TERMS_ENDPOINT)
        print("Schedge terms example:", str(terms)[:200], "…")
    except Exception as e:
        print("Warning: Could not fetch terms from", TERMS_ENDPOINT, "->", e)

    print(f"Fetching {YEAR} {TERM} {MVP_SCHOOL} {MVP_SUBJECT}…")
    raw_courses = fetch_courses(YEAR, TERM, MVP_SCHOOL, MVP_SUBJECT)

    print(f"Transforming {len(raw_courses)} courses…")
    out = transform_to_quacs_schema(raw_courses)

    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_FILE, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    print("Wrote:", OUT_FILE.resolve())

if __name__ == "__main__":
    main()
