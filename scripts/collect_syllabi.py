#!/usr/bin/env python3
"""Collect climate finance course reading lists from universities worldwide.

Five-stage pipeline:
  1. search   — Discover candidate URLs via DuckDuckGo + seed list
  2. fetch    — Download page content (HTML/PDF)
  3. classify — LLM classifies pages as syllabi or not
  4. extract  — LLM extracts bibliographic references
  5. normalize — Deduplicate + enrich via CrossRef

Each stage reads the previous stage's output and writes JSONL checkpoints.
Interruptible: re-run any stage to resume from checkpoint.

Usage:
    python scripts/collect_syllabi.py --stage search [--limit N]
    python scripts/collect_syllabi.py --stage fetch
    python scripts/collect_syllabi.py --stage classify
    python scripts/collect_syllabi.py --stage extract
    python scripts/collect_syllabi.py --stage normalize
"""

import argparse
import json
import os
import re
import sys
import time
import urllib.request
from datetime import datetime, timezone

import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
from utils import (BASE_DIR, DATA_DIR, MAILTO, normalize_title,
                   polite_get, save_csv)

# --- Paths ---
SYLLABI_DIR = os.path.join(DATA_DIR, "syllabi")
PDF_DIR = os.path.join(SYLLABI_DIR, "pdfs")
SEARCH_PATH = os.path.join(SYLLABI_DIR, "search_results.jsonl")
PAGES_PATH = os.path.join(SYLLABI_DIR, "pages.jsonl")
CLASSIFIED_PATH = os.path.join(SYLLABI_DIR, "classified.jsonl")
REFERENCES_PATH = os.path.join(SYLLABI_DIR, "raw_references.jsonl")
OUTPUT_CSV = os.path.join(SYLLABI_DIR, "reading_lists.csv")

# --- Search queries ---
# (topic, suffix, language_hint)
SEARCH_QUERIES = [
    # English
    ("climate finance", "syllabus", "en"),
    ("climate finance", "reading list", "en"),
    ("climate finance", "course outline", "en"),
    ("climate finance", "course bibliography", "en"),
    ("green finance", "syllabus", "en"),
    ("green finance", "reading list", "en"),
    ("carbon finance", "syllabus", "en"),
    ("carbon finance", "reading list", "en"),
    ("sustainable finance", "syllabus", "en"),
    ("sustainable finance", "reading list", "en"),
    ("climate economics", "syllabus", "en"),
    ("climate economics", "reading list", "en"),
    ("environmental finance", "syllabus", "en"),
    # French
    ("finance climatique", "syllabus", "fr"),
    ("finance climatique", "bibliographie", "fr"),
    ("finance climatique", "plan de cours", "fr"),
    ("financement climatique", "syllabus", "fr"),
    ("finance verte", "syllabus", "fr"),
    ("finance durable", "syllabus", "fr"),
    # German
    ("Klimafinanzierung", "Syllabus", "de"),
    ("Klimafinanzierung", "Literaturliste", "de"),
    ("nachhaltige Finanzwirtschaft", "Syllabus", "de"),
    ("nachhaltige Finanzwirtschaft", "Seminarplan", "de"),
    ("Sustainable Finance", "Syllabus Universität", "de"),
    # Spanish
    ("finanzas climáticas", "syllabus", "es"),
    ("finanzas climáticas", "bibliografía", "es"),
    ("financiamiento climático", "programa curso", "es"),
    ("finanzas sostenibles", "syllabus", "es"),
    # Portuguese
    ("finanças climáticas", "programa", "pt"),
    ("finanças climáticas", "bibliografia", "pt"),
    ("finanças sustentáveis", "syllabus", "pt"),
    # Chinese
    ("气候金融 课程 教学大纲", "", "zh"),
    ("气候融资 课程 参考书目", "", "zh"),
    ("绿色金融 课程 教学大纲", "", "zh"),
    # Japanese
    ("気候ファイナンス シラバス", "", "ja"),
    ("グリーンファイナンス シラバス 参考文献", "", "ja"),
    # Korean
    ("기후금융 강의계획서", "", "ko"),
    ("녹색금융 강의계획서", "", "ko"),
    # Italian
    ("finanza climatica", "syllabus", "it"),
    ("finanza sostenibile", "syllabus bibliografia", "it"),
    # Dutch
    ("klimaatfinanciering", "syllabus", "nl"),
    ("duurzame financiering", "syllabus literatuurlijst", "nl"),
]

# --- Seed URLs (Tier 1 & 3) ---
SEED_URLS = [
    # Brown Syllabus Bank
    {"url": "https://climate.watson.brown.edu/syllabus-bank",
     "title": "Brown Climate Solutions Lab - Syllabus Bank",
     "source_tier": "curated", "language": "en"},
    # Harvard FECS 2025
    {"url": "https://salatainstitute.harvard.edu/wp-content/uploads/2024/12/FECS-2025-reading-list-15Dec24-1.pdf",
     "title": "Harvard FECS 2025 Reading List",
     "source_tier": "curated", "language": "en"},
    # Harvard FECS 2026
    {"url": "https://salatainstitute.harvard.edu/wp-content/uploads/2026/01/FECS-2026-Reading-List_05Jan26-2.pdf",
     "title": "Harvard FECS 2026 Reading List",
     "source_tier": "curated", "language": "en"},
    # Columbia Business School B8363
    {"url": "https://courses.business.columbia.edu/B8363",
     "title": "Columbia Business School - Climate Finance",
     "source_tier": "known_program", "language": "en"},
    # NYU Stern Climate Finance
    {"url": "https://www.stern.nyu.edu/experience-stern/about/departments-centers-initiatives/climate-finance/teaching/climate-finance-course",
     "title": "NYU Stern - Climate Finance Course",
     "source_tier": "known_program", "language": "en"},
    # UBC MBA Climate Finance
    {"url": "https://blogs.ubc.ca/ftmba2025/files/2024/10/BAFI-580C-Climate-Finance-MBA-Syllabus-2024W1.pdf",
     "title": "UBC MBA Climate Finance Syllabus",
     "source_tier": "known_program", "language": "en"},
    # SOAS Summer School
    {"url": "https://www.soas.ac.uk/sites/default/files/summerschool/subjects/course-handbooks/file144926.pdf",
     "title": "SOAS Sustainable Finance and Climate Change",
     "source_tier": "known_program", "language": "en"},
    # Edinburgh
    {"url": "http://www.drps.ed.ac.uk/20-21/dpt/cxcmse11498.htm",
     "title": "Edinburgh - International Climate Finance",
     "source_tier": "known_program", "language": "en"},
    # UQAM
    {"url": "https://etudier.uqam.ca/cours?sigle=DSR7621&p=9030",
     "title": "UQAM - Investissement et Financement climatique",
     "source_tier": "known_program", "language": "fr"},
    # CFA Institute Climate Finance
    {"url": "https://www.cfainstitute.org/programs/climate-finance",
     "title": "CFA Institute - Climate Finance Course",
     "source_tier": "known_program", "language": "en"},
    # UN CC:Learn Climate Finance
    {"url": "https://unccelearn.org/course/view.php?id=91&page=overview",
     "title": "UN CC:Learn - Climate Finance",
     "source_tier": "known_program", "language": "en"},
    # MACC Hub workbook
    {"url": "https://macchub.co.uk/wp-content/uploads/2025/02/English-Workbook-Short-Course-1-.pdf",
     "title": "MACC Hub - Basics of Climate Finance",
     "source_tier": "known_program", "language": "en"},
]


# ============================================================
# Helpers
# ============================================================

def load_jsonl(path):
    """Load all records from a JSONL file."""
    records = []
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    records.append(json.loads(line))
    return records


def append_jsonl(records, path):
    """Append records to a JSONL file."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def llm_call(prompt, api_key, model="google/gemma-2-27b-it", max_tokens=2000):
    """Call OpenRouter LLM. Returns response text or None on error."""
    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": 0,
    }).encode()

    req = urllib.request.Request(
        "https://openrouter.ai/api/v1/chat/completions",
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read())
        return result["choices"][0]["message"]["content"].strip()
    except Exception as e:
        print(f"  LLM error: {e}")
        return None


def extract_json_from_text(text):
    """Extract the first JSON object or array from LLM response text."""
    if not text:
        return None
    # Try to find JSON block in markdown code fence
    m = re.search(r"```(?:json)?\s*\n?([\s\S]*?)\n?```", text)
    if m:
        text = m.group(1)
    # Try to parse the whole thing
    text = text.strip()
    for start_char, end_char in [("{", "}"), ("[", "]")]:
        idx_start = text.find(start_char)
        idx_end = text.rfind(end_char)
        if idx_start != -1 and idx_end > idx_start:
            candidate = text[idx_start:idx_end + 1]
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                continue
    return None


# ============================================================
# Stage 1: Search
# ============================================================

def stage_search(limit=0):
    """Discover candidate URLs via DuckDuckGo + seed list."""
    from ddgs import DDGS

    os.makedirs(SYLLABI_DIR, exist_ok=True)

    # Load already-completed queries
    existing = load_jsonl(SEARCH_PATH)
    done_queries = {r.get("query", "") for r in existing}
    seen_urls = {r["url"] for r in existing}

    print(f"Search: {len(existing)} results already collected, "
          f"{len(done_queries)} queries done")

    # Add seed URLs first
    new_seeds = []
    for seed in SEED_URLS:
        if seed["url"] not in seen_urls:
            rec = {
                "url": seed["url"],
                "title": seed["title"],
                "snippet": "",
                "query": "__seed__",
                "language": seed["language"],
                "source_tier": seed["source_tier"],
            }
            new_seeds.append(rec)
            seen_urls.add(seed["url"])

    if new_seeds:
        append_jsonl(new_seeds, SEARCH_PATH)
        print(f"  Added {len(new_seeds)} seed URLs")

    # DuckDuckGo searches
    ddgs = DDGS()
    queries_run = 0

    for topic, suffix, lang in SEARCH_QUERIES:
        query = f'"{topic}" {suffix}' if suffix else topic

        if query in done_queries:
            continue

        if limit and queries_run >= limit:
            print(f"  Reached query limit ({limit}), stopping.")
            break

        print(f"  Searching: {query} [{lang}]")
        try:
            results = ddgs.text(query, max_results=30)
        except Exception as e:
            print(f"    Error: {e}")
            # Mark query as done to avoid retrying on resume
            append_jsonl([{
                "url": "", "title": f"ERROR: {e}", "snippet": "",
                "query": query, "language": lang,
                "source_tier": "search_error",
            }], SEARCH_PATH)
            done_queries.add(query)
            queries_run += 1
            time.sleep(2)
            continue

        new_records = []
        for r in (results or []):
            url = r.get("href", r.get("link", ""))
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)
            new_records.append({
                "url": url,
                "title": r.get("title", ""),
                "snippet": r.get("body", ""),
                "query": query,
                "language": lang,
                "source_tier": "search",
            })

        if new_records:
            append_jsonl(new_records, SEARCH_PATH)
            print(f"    Found {len(new_records)} new URLs")
        else:
            # Write a marker so we don't re-run this query
            append_jsonl([{
                "url": "", "title": "", "snippet": "",
                "query": query, "language": lang,
                "source_tier": "search_empty",
            }], SEARCH_PATH)

        done_queries.add(query)
        queries_run += 1
        time.sleep(1.5)  # Be polite to DuckDuckGo

    # Summary
    all_results = load_jsonl(SEARCH_PATH)
    valid = [r for r in all_results if r["url"] and r["source_tier"] not in ("search_error", "search_empty")]
    print(f"\nSearch complete: {len(valid)} candidate URLs from "
          f"{len({r['query'] for r in all_results})} queries")


# ============================================================
# Stage 2: Fetch
# ============================================================

def stage_fetch():
    """Download page content for each candidate URL."""
    from bs4 import BeautifulSoup

    os.makedirs(PDF_DIR, exist_ok=True)

    # Load search results
    search_results = load_jsonl(SEARCH_PATH)
    urls_to_fetch = [r for r in search_results
                     if r["url"] and r["source_tier"] not in ("search_error", "search_empty")]

    # Load already-fetched
    fetched = load_jsonl(PAGES_PATH)
    done_urls = {r["url"] for r in fetched}

    pending = [r for r in urls_to_fetch if r["url"] not in done_urls]
    print(f"Fetch: {len(done_urls)} already done, {len(pending)} pending")

    for i, rec in enumerate(pending):
        url = rec["url"]
        print(f"  [{i+1}/{len(pending)}] {url[:80]}")

        page_rec = {
            "url": url,
            "content_type": "",
            "text": "",
            "fetch_date": datetime.now(timezone.utc).isoformat(),
            "http_status": 0,
            "error": "",
        }

        try:
            headers = {"User-Agent": f"ClimateFinancePipeline/1.0 (mailto:{MAILTO})"}
            resp = polite_get(url, headers=headers, delay=0.5)
            ct = resp.headers.get("Content-Type", "")
            page_rec["http_status"] = resp.status_code
            page_rec["content_type"] = ct

            if "pdf" in ct.lower() or url.lower().endswith(".pdf"):
                # Save PDF, extract text
                pdf_name = re.sub(r'[^\w\-.]', '_', url.split("/")[-1] or "page.pdf")
                if not pdf_name.endswith(".pdf"):
                    pdf_name += ".pdf"
                pdf_path = os.path.join(PDF_DIR, pdf_name)
                with open(pdf_path, "wb") as f:
                    f.write(resp.content)

                try:
                    import pdfplumber
                    text_parts = []
                    with pdfplumber.open(pdf_path) as pdf:
                        for page in pdf.pages[:50]:  # Cap at 50 pages
                            t = page.extract_text()
                            if t:
                                text_parts.append(t)
                    page_rec["text"] = "\n\n".join(text_parts)[:20000]
                    page_rec["content_type"] = "application/pdf"
                except Exception as e:
                    page_rec["error"] = f"PDF parse error: {e}"
                    print(f"    PDF parse error: {e}")

            else:
                # HTML
                soup = BeautifulSoup(resp.text, "html.parser")
                # Remove script/style
                for tag in soup(["script", "style", "nav", "footer", "header"]):
                    tag.decompose()
                text = soup.get_text(separator="\n", strip=True)
                page_rec["text"] = text[:20000]
                page_rec["content_type"] = "text/html"

        except Exception as e:
            page_rec["error"] = str(e)
            print(f"    Error: {e}")

        append_jsonl([page_rec], PAGES_PATH)
        time.sleep(0.3)

    # Summary
    all_pages = load_jsonl(PAGES_PATH)
    ok = [p for p in all_pages if p["text"] and not p["error"]]
    print(f"\nFetch complete: {len(ok)}/{len(all_pages)} pages with text")


# ============================================================
# Stage 3: Classify
# ============================================================

CLASSIFY_PROMPT = """You are classifying web pages. Given the text below, determine if this is a university course syllabus or reading list related to climate finance, green finance, sustainable finance, carbon markets, or environmental economics.

Respond with ONLY a JSON object (no other text):
{{"is_syllabus": true/false, "course_name": "...", "institution": "...", "country": "...", "language": "...", "has_reading_list": true/false}}

If it is not a syllabus, set course_name/institution/country to empty strings.

TEXT (first 2000 chars):
{text}
"""


def stage_classify():
    """LLM classifies fetched pages as syllabi or not."""
    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    if not api_key:
        print("ERROR: OPENROUTER_API_KEY not set. Export it or add to ~/.bashrc")
        sys.exit(1)

    pages = load_jsonl(PAGES_PATH)
    pages_with_text = [p for p in pages if p.get("text") and not p.get("error")]

    classified = load_jsonl(CLASSIFIED_PATH)
    done_urls = {r["url"] for r in classified}

    pending = [p for p in pages_with_text if p["url"] not in done_urls]
    print(f"Classify: {len(done_urls)} already done, {len(pending)} pending")

    for i, page in enumerate(pending):
        url = page["url"]
        text_snippet = page["text"][:2000]
        print(f"  [{i+1}/{len(pending)}] {url[:80]}")

        prompt = CLASSIFY_PROMPT.format(text=text_snippet)
        response = llm_call(prompt, api_key)

        rec = {
            "url": url,
            "is_syllabus": False,
            "course_name": "",
            "institution": "",
            "country": "",
            "language": "",
            "has_reading_list": False,
            "llm_raw": (response or "")[:500],
        }

        parsed = extract_json_from_text(response)
        if parsed and isinstance(parsed, dict):
            rec["is_syllabus"] = bool(parsed.get("is_syllabus", False))
            rec["course_name"] = str(parsed.get("course_name", ""))
            rec["institution"] = str(parsed.get("institution", ""))
            rec["country"] = str(parsed.get("country", ""))
            rec["language"] = str(parsed.get("language", ""))
            rec["has_reading_list"] = bool(parsed.get("has_reading_list", False))

        status = "SYLLABUS" if rec["is_syllabus"] else "skip"
        reading = "+refs" if rec["has_reading_list"] else ""
        print(f"    → {status}{reading} | {rec['institution']} | {rec['course_name']}")

        append_jsonl([rec], CLASSIFIED_PATH)
        time.sleep(0.5)

    # Summary
    all_classified = load_jsonl(CLASSIFIED_PATH)
    syllabi = [c for c in all_classified if c["is_syllabus"]]
    with_refs = [c for c in syllabi if c["has_reading_list"]]
    print(f"\nClassify complete: {len(syllabi)} syllabi identified, "
          f"{len(with_refs)} with reading lists")

    if syllabi:
        countries = {}
        for s in syllabi:
            c = s.get("country", "unknown") or "unknown"
            countries[c] = countries.get(c, 0) + 1
        print("  Countries: " + ", ".join(
            f"{c}: {n}" for c, n in sorted(countries.items(), key=lambda x: -x[1])))


# ============================================================
# Stage 4: Extract
# ============================================================

EXTRACT_PROMPT = """Extract ALL bibliographic references (reading list, required readings, recommended readings, bibliography) from this course syllabus text.

Return ONLY a JSON array of references (no other text). Each reference:
[{{"title": "...", "authors": "...", "year": 2020, "journal_or_publisher": "...", "doi": null, "type": "article"}}]

Valid types: "article", "book", "chapter", "report", "other"
If year is unknown, use null. If DOI is unknown, use null.

SYLLABUS TEXT:
{text}
"""


def stage_extract():
    """LLM extracts bibliographic references from confirmed syllabi."""
    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    if not api_key:
        print("ERROR: OPENROUTER_API_KEY not set.")
        sys.exit(1)

    classified = load_jsonl(CLASSIFIED_PATH)
    syllabi = [c for c in classified if c["is_syllabus"] and c["has_reading_list"]]

    # Load full page text for these URLs
    pages = load_jsonl(PAGES_PATH)
    page_by_url = {p["url"]: p for p in pages}

    extracted = load_jsonl(REFERENCES_PATH)
    done_urls = {r["url"] for r in extracted}

    pending = [s for s in syllabi if s["url"] not in done_urls]
    print(f"Extract: {len(done_urls)} already done, {len(pending)} pending")

    total_refs = 0
    for i, syllabus in enumerate(pending):
        url = syllabus["url"]
        page = page_by_url.get(url, {})
        text = page.get("text", "")
        if not text:
            print(f"  [{i+1}/{len(pending)}] {url[:60]} — no text, skipping")
            append_jsonl([{"url": url, "references": [], "error": "no_text"}],
                         REFERENCES_PATH)
            continue

        print(f"  [{i+1}/{len(pending)}] {syllabus['course_name']} "
              f"({syllabus['institution']})")

        # For long texts, chunk and extract from each chunk
        chunk_size = 8000
        all_refs = []

        for chunk_start in range(0, len(text), chunk_size):
            chunk = text[chunk_start:chunk_start + chunk_size]
            prompt = EXTRACT_PROMPT.format(text=chunk)
            response = llm_call(prompt, api_key, max_tokens=4000)

            parsed = extract_json_from_text(response)
            if parsed and isinstance(parsed, list):
                all_refs.extend(parsed)
            elif parsed and isinstance(parsed, dict):
                all_refs.append(parsed)

            time.sleep(0.5)

        # Deduplicate within this syllabus by normalized title
        seen_titles = set()
        unique_refs = []
        for ref in all_refs:
            if not isinstance(ref, dict):
                continue
            t = normalize_title(ref.get("title", ""))
            if t and t not in seen_titles:
                seen_titles.add(t)
                unique_refs.append(ref)

        rec = {
            "url": url,
            "course_name": syllabus["course_name"],
            "institution": syllabus["institution"],
            "country": syllabus["country"],
            "language": syllabus["language"],
            "references": unique_refs,
            "n_refs": len(unique_refs),
            "error": "",
        }
        append_jsonl([rec], REFERENCES_PATH)
        total_refs += len(unique_refs)
        print(f"    → {len(unique_refs)} references extracted")

    # Summary
    all_extracted = load_jsonl(REFERENCES_PATH)
    total = sum(r.get("n_refs", 0) for r in all_extracted)
    print(f"\nExtract complete: {total} total references from "
          f"{len(all_extracted)} syllabi")


# ============================================================
# Stage 5: Normalize
# ============================================================

def crossref_lookup(title, authors=""):
    """Look up a reference on CrossRef by title. Returns DOI or empty string."""
    query = title
    authors = str(authors) if authors and authors == authors else ""  # handle NaN
    if authors:
        first_author = authors.split(",")[0].split(";")[0].strip()
        if first_author:
            query = f"{first_author} {title}"

    try:
        resp = polite_get(
            "https://api.crossref.org/works",
            params={"query": query[:200], "rows": 1},
            delay=0.3,
        )
        data = resp.json()
        items = data.get("message", {}).get("items", [])
        if items:
            item = items[0]
            cr_title = " ".join(item.get("title", []))
            # Check title similarity
            if normalize_title(cr_title) == normalize_title(title):
                return item.get("DOI", "")
            # Looser match: check if most words overlap
            t1_words = set(normalize_title(title).split())
            t2_words = set(normalize_title(cr_title).split())
            if t1_words and t2_words:
                overlap = len(t1_words & t2_words) / max(len(t1_words), 1)
                if overlap > 0.7:
                    return item.get("DOI", "")
    except Exception as e:
        print(f"    CrossRef error: {e}")
    return ""


def _dedup_courses(grouped, course_col, overlap_threshold=0.8,
                   min_shared=10):
    """Merge near-duplicate courses and recount n_courses.

    Two courses are considered duplicates if they share ≥ min_shared readings
    AND > overlap_threshold of the smaller course's readings. This prevents
    false merges when courses share just 1-2 popular papers by coincidence.

    Modifies the grouped DataFrame in place: updates courses, institutions,
    and adds/updates n_courses.
    """
    from collections import defaultdict

    # Build course → set of reading keys (row indices)
    course_readings = defaultdict(set)
    for idx, row in grouped.iterrows():
        courses = [c.strip() for c in row[course_col].split(" ; ")]
        for c in courses:
            if c:
                course_readings[c].add(idx)

    # Find courses that overlap significantly
    course_list = list(course_readings.keys())
    merged = {}  # course_name → canonical_name
    for i, c1 in enumerate(course_list):
        if c1 in merged:
            continue
        for c2 in course_list[i + 1:]:
            if c2 in merged:
                continue
            s1, s2 = course_readings[c1], course_readings[c2]
            if not s1 or not s2:
                continue
            n_shared = len(s1 & s2)
            overlap = n_shared / min(len(s1), len(s2))
            if n_shared >= min_shared and overlap > overlap_threshold:
                # Merge c2 into c1 (keep shorter name as canonical)
                canonical = c1 if len(c1) <= len(c2) else c2
                alias = c2 if canonical == c1 else c1
                merged[alias] = canonical
                print(f"  Course dedup: '{alias[:50]}' → '{canonical[:50]}'")

    if not merged:
        grouped["n_courses"] = grouped[course_col].apply(
            lambda x: len(set(x.split(" ; "))) if x else 0)
        return grouped

    # Apply merges to each row
    def apply_merge(courses_str):
        courses = [c.strip() for c in courses_str.split(" ; ")]
        deduped = []
        seen = set()
        for c in courses:
            canonical = merged.get(c, c)
            if canonical not in seen:
                deduped.append(canonical)
                seen.add(canonical)
        return " ; ".join(sorted(deduped))

    grouped[course_col] = grouped[course_col].apply(apply_merge)
    grouped["n_courses"] = grouped[course_col].apply(
        lambda x: len(set(x.split(" ; "))) if x else 0)

    n_merged = len(merged)
    print(f"  Merged {n_merged} duplicate course names")
    return grouped


def stage_normalize():
    """Deduplicate and enrich references via CrossRef."""
    extracted = load_jsonl(REFERENCES_PATH)

    # Flatten all references with course metadata
    flat = []
    for rec in extracted:
        for ref in rec.get("references", []):
            if not isinstance(ref, dict):
                continue
            flat.append({
                "title": ref.get("title", ""),
                "authors": ref.get("authors", ""),
                "year": ref.get("year"),
                "journal_or_publisher": ref.get("journal_or_publisher", ""),
                "doi": ref.get("doi") or "",
                "type": ref.get("type", "other"),
                "course_name": rec.get("course_name", ""),
                "institution": rec.get("institution", ""),
                "country": rec.get("country", ""),
            })

    print(f"Normalize: {len(flat)} raw references from {len(extracted)} syllabi")

    if not flat:
        print("  No references to normalize.")
        return

    df = pd.DataFrame(flat)
    df["title_norm"] = df["title"].apply(normalize_title)

    # CrossRef DOI lookup for references without DOIs
    no_doi = df[df["doi"] == ""]
    print(f"  {len(no_doi)} references without DOIs, looking up on CrossRef...")

    lookup_count = 0
    for idx in no_doi.index:
        title = df.at[idx, "title"]
        authors = df.at[idx, "authors"]
        if not title or len(title) < 10:
            continue

        doi = crossref_lookup(title, authors)
        if doi:
            df.at[idx, "doi"] = doi.lower()
            lookup_count += 1
            print(f"    Found DOI: {doi} ← {title[:60]}")

        # Progress
        if (idx + 1) % 50 == 0:
            print(f"    ... {idx + 1}/{len(no_doi)} looked up, "
                  f"{lookup_count} DOIs found")

    print(f"  CrossRef: found {lookup_count} DOIs")

    # Deduplicate: group by DOI (if available) or normalized title
    df["dedup_key"] = df.apply(
        lambda r: r["doi"] if r["doi"] else r["title_norm"], axis=1)

    grouped = df.groupby("dedup_key").agg({
        "doi": "first",
        "title": "first",
        "authors": "first",
        "year": "first",
        "journal_or_publisher": "first",
        "type": "first",
        "course_name": lambda x: " ; ".join(sorted(set(x))),
        "institution": lambda x: " ; ".join(sorted(set(x))),
        "country": lambda x: " ; ".join(sorted(set(x))),
    }).reset_index(drop=True)

    # Deduplicate near-identical courses before counting.
    # Some courses appear under multiple institution names (e.g., co-organized
    # MOOCs). We detect these by reading overlap: if two courses share >80%
    # of their readings, they are the same course and should count as one.
    grouped = _dedup_courses(grouped, "course_name")

    # Sort by number of courses (most assigned first)
    grouped = grouped.sort_values("n_courses", ascending=False).reset_index(drop=True)

    # Rename columns for clarity
    grouped = grouped.rename(columns={
        "course_name": "courses",
        "institution": "institutions",
        "country": "countries",
    })

    # Optionally cross-reference with existing corpus
    corpus_path = os.path.join(DATA_DIR, "catalogs", "refined_works.csv")
    if os.path.exists(corpus_path):
        corpus = pd.read_csv(corpus_path)
        corpus_titles = set(corpus["title"].dropna().apply(normalize_title))
        corpus_dois = set(corpus["doi"].dropna().str.lower())

        grouped["in_corpus"] = grouped.apply(
            lambda r: (r["doi"] and r["doi"] in corpus_dois) or
                      (normalize_title(r["title"]) in corpus_titles),
            axis=1,
        )
        n_in = grouped["in_corpus"].sum()
        print(f"  {n_in}/{len(grouped)} references found in existing corpus")
    else:
        grouped["in_corpus"] = False

    save_csv(grouped, OUTPUT_CSV)

    print(f"\nNormalize complete:")
    print(f"  Unique references: {len(grouped)}")
    print(f"  With DOI: {(grouped['doi'] != '').sum()}")
    print(f"  Most assigned (top 10):")
    for _, row in grouped.head(10).iterrows():
        print(f"    [{row['n_courses']} courses] {row['title'][:70]}")


# ============================================================
# Main
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description="Collect climate finance course reading lists")
    parser.add_argument("--stage", required=True,
                        choices=["search", "fetch", "classify", "extract", "normalize"],
                        help="Pipeline stage to run")
    parser.add_argument("--limit", type=int, default=0,
                        help="Limit number of queries (search) or items to process")
    args = parser.parse_args()

    os.makedirs(SYLLABI_DIR, exist_ok=True)

    if args.stage == "search":
        stage_search(limit=args.limit)
    elif args.stage == "fetch":
        stage_fetch()
    elif args.stage == "classify":
        stage_classify()
    elif args.stage == "extract":
        stage_extract()
    elif args.stage == "normalize":
        stage_normalize()


if __name__ == "__main__":
    main()
