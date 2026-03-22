#!/usr/bin/env python3
"""Build teaching_sources.yaml from scraped reading lists.

Reads:
  data/syllabi/reading_lists.csv    — automated web scraping (collect_syllabi.py)

Writes:
  data/teaching_sources.yaml

Selection criteria:
  - has DOI AND n_courses >= 2, OR
  - no DOI AND n_courses >= 3

Usage:
    python scripts/build_teaching_yaml.py
"""

import argparse
import math
import os
from collections import defaultdict

import pandas as pd
import yaml

from utils import DATA_DIR, get_logger

log = get_logger("build_teaching_yaml")

INPUT_CSV = os.path.join(DATA_DIR, "syllabi", "reading_lists.csv")
OUTPUT_YAML = os.path.join(DATA_DIR, "teaching_sources.yaml")

MIN_COURSES = 2  # DOI entries: keep if appearing on >=2 syllabi
MIN_COURSES_NO_DOI = 3  # Title-only entries: higher bar (>=3 syllabi)
MIN_READINGS_DETAILED = 20  # Courses with >=20 DOI readings are "detailed syllabi"
OVERLAP_THRESHOLD = 0.8  # Course pairs sharing >80% readings are duplicates
MIN_SHARED_READINGS = 10  # Require >=10 shared readings to consider dedup


def _clean(val):
    """Return stripped string or empty string for NaN/None."""
    if val is None or (isinstance(val, float) and math.isnan(val)):
        return ""
    return str(val).strip()


def _infer_level(course_name):
    """Infer course level from name heuristics."""
    low = course_name.lower()
    if any(k in low for k in ("doctoral", "phd", "research seminar")):
        return "doctoral"
    if "mba" in low:
        return "mba"
    if any(k in low for k in ("mooc", "coursera", "edx", "online")):
        return "mooc"
    if any(k in low for k in ("master", "graduate", "msc", "m.sc")):
        return "masters"
    return "other"


def _infer_region(countries_str):
    """Map semicolon-separated country names to a broad region."""
    if not countries_str:
        return "Global"

    na = {"usa", "united states", "canada"}
    eu = {"france", "uk", "united kingdom", "germany", "spain", "italy",
          "netherlands", "switzerland", "sweden", "denmark", "norway",
          "belgium", "austria", "ireland", "portugal"}
    asia = {"china", "japan", "india", "singapore", "hong kong", "south korea",
            "taiwan", "thailand", "indonesia", "malaysia"}
    latam = {"brazil", "mexico", "ecuador", "colombia", "chile", "argentina",
             "peru"}

    regions = set()
    for c in countries_str.split(";"):
        c = c.strip().lower()
        if not c:
            continue
        if c in na:
            regions.add("North America")
        elif c in eu:
            regions.add("Europe")
        elif c in asia:
            regions.add("Asia")
        elif c in latam:
            regions.add("Latin America")
        else:
            regions.add("Global")

    if not regions or len(regions) > 1:
        return "Global"
    return regions.pop()


def _dedup_course_names(df):
    """Merge near-duplicate course names and recompute n_courses.

    Two courses are considered duplicates if they share >=MIN_SHARED_READINGS
    AND >OVERLAP_THRESHOLD of the smaller course's readings. This catches
    co-organized MOOCs listed under multiple institution names.
    """
    # Build course -> set of row indices
    course_rows = defaultdict(set)
    for idx, row in df.iterrows():
        for c in str(row.get("courses", "")).split(";"):
            c = c.strip()
            if c:
                course_rows[c].add(idx)

    # Find overlapping course pairs
    courses = list(course_rows.keys())
    merged = {}  # alias -> canonical
    for i, c1 in enumerate(courses):
        if c1 in merged:
            continue
        for c2 in courses[i + 1:]:
            if c2 in merged:
                continue
            s1, s2 = course_rows[c1], course_rows[c2]
            if not s1 or not s2:
                continue
            n_shared = len(s1 & s2)
            overlap = n_shared / min(len(s1), len(s2))
            if n_shared >= MIN_SHARED_READINGS and overlap > OVERLAP_THRESHOLD:
                canonical = c1 if len(c1) <= len(c2) else c2
                alias = c2 if canonical == c1 else c1
                merged[alias] = canonical

    if not merged:
        return df

    log.info("  Course dedup: merged %d duplicate course names", len(merged))

    def apply_merge(courses_str):
        parts = [c.strip() for c in str(courses_str).split(";")]
        deduped = []
        seen = set()
        for c in parts:
            canonical = merged.get(c, c)
            if canonical and canonical not in seen:
                deduped.append(canonical)
                seen.add(canonical)
        return " ; ".join(sorted(deduped))

    df = df.copy()
    df["courses"] = df["courses"].apply(apply_merge)
    df["n_courses"] = df["courses"].apply(
        lambda x: len([c for c in x.split(" ; ") if c.strip()]))
    return df


# --- Source 1: scraped readings ---

def _find_detailed_courses(df):
    """Identify courses that are detailed syllabi (many DOI readings).

    A course with >= MIN_READINGS_DETAILED DOI readings is a curated reading
    list (e.g., Harvard FECS doctoral seminar). Its readings pass at n_courses=1
    because the syllabus itself is a quality signal — no cross-course
    corroboration needed.
    """
    has_doi = df["doi"].notna() & (df["doi"].str.strip() != "")

    # Count DOI readings per individual course
    course_doi_counts = defaultdict(int)
    for _, row in df[has_doi].iterrows():
        for c in str(row.get("courses", "")).split(";"):
            c = c.strip()
            if c:
                course_doi_counts[c] += 1

    detailed = {c for c, n in course_doi_counts.items()
                if n >= MIN_READINGS_DETAILED}
    if detailed:
        log.info("  Detailed syllabi (>=%d DOI readings): %s",
                 MIN_READINGS_DETAILED,
                 ", ".join(sorted(detailed)[:5]))
    return detailed


def load_scraped(csv_path):
    """Load scraped readings, apply course dedup and selection filter.

    Two-tier filter:
    - Tier 1 (detailed syllabi): courses with >= MIN_READINGS_DETAILED DOI
      readings.  Their DOI readings pass at n_courses >= 1.
    - Tier 2 (standard): DOI + n_courses >= 2, or no DOI + n_courses >= 3.

    Returns list of (institution, course, reading) record dicts.
    """
    df = pd.read_csv(csv_path)
    df = _dedup_course_names(df)

    has_doi = df["doi"].notna() & (df["doi"].str.strip() != "")

    # Identify detailed syllabi
    detailed_courses = _find_detailed_courses(df)

    # Tier 1: DOI reading from a detailed syllabus
    from_detailed = df["courses"].apply(
        lambda x: any(c.strip() in detailed_courses
                      for c in str(x).split(";")))
    tier1 = has_doi & from_detailed

    # Tier 2: standard convergence filter
    tier2 = (has_doi & (df["n_courses"] >= MIN_COURSES)) | \
            (~has_doi & (df["n_courses"] >= MIN_COURSES_NO_DOI))

    keep = tier1 | tier2
    df = df[keep]
    n_tier1 = tier1[keep].sum()
    n_tier2_only = (~tier1[keep] & tier2[keep]).sum()
    n_doi = has_doi[keep].sum()
    n_nodoi = len(df) - n_doi
    log.info("  After filter: %d readings (%d tier1-detailed, %d tier2-convergence)",
             len(df), n_tier1, n_tier2_only)
    log.info("  %d with DOI, %d title-only", n_doi, n_nodoi)

    records = []
    for _, row in df.iterrows():
        courses = [c.strip() for c in str(row.get("courses", "")).split(";")]
        institutions = [i.strip() for i in str(row.get("institutions", "")).split(";")]
        countries = _clean(row.get("countries", ""))

        while len(institutions) < len(courses):
            institutions.append("")

        for course, inst in zip(courses, institutions):
            if not course:
                continue
            records.append({
                "institution": inst if inst else "Unknown",
                "course": course,
                "doi": _clean(row.get("doi", "")),
                "title": _clean(row.get("title", "")),
                "authors": _clean(row.get("authors", "")),
                "year": _clean(row.get("year", "")),
                "countries": countries,
                "origin": "scraped",
            })

    return records


# --- Build output ---

def build_yaml_structure(records):
    """Group records by (institution, course) and build YAML-ready structure."""
    groups = defaultdict(lambda: {"readings": [], "countries": ""})

    for r in records:
        key = (r["institution"], r["course"])
        groups[key]["readings"].append(r)
        if r.get("countries"):
            groups[key]["countries"] = r["countries"]

    sources = []
    for (inst, course), group in sorted(groups.items()):
        region = _infer_region(group["countries"])
        level = _infer_level(course)

        # Deduplicate readings within this course by DOI or title
        seen = set()
        yaml_readings = []
        for r in group["readings"]:
            doi = r["doi"]
            title = r["title"]
            key = doi.lower() if doi else title.lower()
            if not key or key in seen:
                continue
            seen.add(key)

            entry = {}
            if doi:
                entry["doi"] = doi
            if title:
                entry["title"] = title
            if r["authors"]:
                entry["authors"] = r["authors"]
            year_str = r["year"]
            if year_str:
                try:
                    entry["year"] = int(float(year_str))
                except (ValueError, OverflowError):
                    pass
            yaml_readings.append(entry)

        if not yaml_readings:
            continue

        source = {
            "institution": inst,
            "course": course,
            "level": level,
            "region": region,
            "readings": yaml_readings,
        }
        sources.append(source)

    return sources


def main():
    if os.path.exists(INPUT_CSV):
        log.info("Reading scraped data: %s", INPUT_CSV)
        records = load_scraped(INPUT_CSV)
        log.info("  %d (reading, course) pairs", len(records))
    else:
        log.info("No reading_lists.csv found at %s", INPUT_CSV)
        records = []

    sources = build_yaml_structure(records)
    total_readings = sum(len(s["readings"]) for s in sources)
    unique_dois = set()
    for s in sources:
        for r in s["readings"]:
            if r.get("doi"):
                unique_dois.add(r["doi"].lower())

    # Write YAML
    os.makedirs(os.path.dirname(OUTPUT_YAML), exist_ok=True)
    with open(OUTPUT_YAML, "w", encoding="utf-8") as f:
        yaml.dump(sources, f, allow_unicode=True, default_flow_style=False,
                  sort_keys=False, width=120)

    log.info("Wrote %s", OUTPUT_YAML)
    log.info("  %d courses", len(sources))
    log.info("  %d readings (across all courses)", total_readings)
    log.info("  %d unique DOIs", len(unique_dois))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    main()
