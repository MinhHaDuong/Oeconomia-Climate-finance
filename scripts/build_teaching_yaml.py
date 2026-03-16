#!/usr/bin/env python3
"""Build teaching_sources.yaml from reading_lists.csv.

Reads:  data/syllabi/reading_lists.csv
Writes: data/teaching_sources.yaml

This script bridges the syllabi scraper (collect_syllabi.py) and the
teaching catalog builder (build_teaching_canon.py). It converts the flat
CSV of scraped syllabus readings into the hierarchical YAML format that
build_teaching_canon.py expects.

Each reading in the CSV may belong to multiple courses (semicolon-separated
courses/institutions columns). The script explodes these into per-course
groups and outputs one YAML entry per (institution, course) pair.

Usage:
    python scripts/build_teaching_yaml.py
"""

import math
import os
import re
import sys
from collections import defaultdict

import pandas as pd
import yaml

sys.path.insert(0, os.path.dirname(__file__))
from utils import DATA_DIR

INPUT_CSV = os.path.join(DATA_DIR, "syllabi", "reading_lists.csv")
OUTPUT_YAML = os.path.join(DATA_DIR, "teaching_sources.yaml")


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


MIN_COURSES = 2  # DOI entries: keep if appearing on ≥2 syllabi
MIN_COURSES_NO_DOI = 3  # Title-only entries: higher bar (≥3 syllabi)
OVERLAP_THRESHOLD = 0.8  # Course pairs sharing >80% readings are duplicates
MIN_SHARED_READINGS = 10  # Require ≥10 shared readings to consider dedup


def _dedup_course_names(df):
    """Merge near-duplicate course names and recompute n_courses.

    Two courses are considered duplicates if they share >OVERLAP_THRESHOLD
    of their readings (by row index). This catches co-organized MOOCs listed
    under multiple institution names.
    """
    from collections import defaultdict

    # Build course → set of row indices
    course_rows = defaultdict(set)
    for idx, row in df.iterrows():
        for c in str(row.get("courses", "")).split(";"):
            c = c.strip()
            if c:
                course_rows[c].add(idx)

    # Find overlapping course pairs
    courses = list(course_rows.keys())
    merged = {}  # alias → canonical
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

    n_merged = len(merged)
    print(f"  Course dedup: merged {n_merged} duplicate course names")

    # Apply merges and recompute n_courses
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


def load_and_explode(csv_path):
    """Read CSV, filter, and explode semicolon-separated courses/institutions.

    Selection criteria:
      - has DOI AND n_courses ≥ MIN_COURSES, OR
      - no DOI AND n_courses ≥ MIN_COURSES_NO_DOI
    Title-only entries need stronger convergence signal since they
    cannot be matched to the corpus by DOI.

    Returns a list of dicts, each representing one (reading, course, institution)
    triple.
    """
    df = pd.read_csv(csv_path)

    # Recompute n_courses after deduplicating near-identical course names.
    # Some courses appear under multiple institution names (co-organized MOOCs).
    # We detect these by reading overlap within each row's course list.
    df = _dedup_course_names(df)

    # Filter: (DOI + n≥2) OR (no DOI + n≥3)
    has_doi = df["doi"].notna() & (df["doi"].str.strip() != "")
    keep = (has_doi & (df["n_courses"] >= MIN_COURSES)) | \
           (~has_doi & (df["n_courses"] >= MIN_COURSES_NO_DOI))
    df = df[keep]
    n_doi = (has_doi & keep).sum()
    n_nodoi = (~has_doi & keep).sum()
    print(f"  After filter: {len(df)} readings ({n_doi} with DOI, {n_nodoi} title-only)")

    records = []

    for _, row in df.iterrows():
        courses = [c.strip() for c in str(row.get("courses", "")).split(";")]
        institutions = [i.strip() for i in str(row.get("institutions", "")).split(";")]
        countries = _clean(row.get("countries", ""))

        # Pad to same length (some entries have fewer institutions than courses)
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
            })

    return records


def build_yaml_structure(records):
    """Group records by (institution, course) and build YAML-ready structure."""
    groups = defaultdict(lambda: {"readings": [], "countries": ""})

    for r in records:
        key = (r["institution"], r["course"])
        groups[key]["readings"].append(r)
        if r["countries"]:
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
    if not os.path.exists(INPUT_CSV):
        print(f"ERROR: {INPUT_CSV} not found. Run collect_syllabi.py first.",
              file=sys.stderr)
        sys.exit(1)

    print(f"Reading {INPUT_CSV}...")
    records = load_and_explode(INPUT_CSV)
    print(f"  {len(records)} (reading, course) pairs extracted")

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

    print(f"\nWrote {OUTPUT_YAML}")
    print(f"  {len(sources)} courses")
    print(f"  {total_readings} readings (across all courses)")
    print(f"  {len(unique_dois)} unique DOIs")


if __name__ == "__main__":
    main()
