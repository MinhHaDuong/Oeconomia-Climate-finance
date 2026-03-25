#!/usr/bin/env python3
"""Enrich missing language tags in the enriched corpus.

Two-pass pipeline:
  Pass 1 — OpenAlex API backfill: batch-query language for DOI-bearing records,
           then query by openalex_id for records without DOIs.
  Pass 2 — Local text detection: langdetect on title+abstract for remaining nulls.

Cache: data/catalogs/enrich_cache/language_resolved.csv

Usage:
    uv run python scripts/enrich_language.py [--dry-run]
                                              [--works-input PATH]
                                              [--run-id ID]
"""

import argparse
import os
import time

import pandas as pd
from langdetect import detect, LangDetectException

from utils import (CATALOGS_DIR, MAILTO, OPENALEX_API_KEY,
                   normalize_doi, retry_get, save_csv, save_run_report,
                   make_run_id, get_logger)

log = get_logger("enrich_language")

CACHE_DIR = os.path.join(CATALOGS_DIR, "enrich_cache")

# ISO 639-1 valid language codes (the 184 codes from the standard).
# We include only the most common ones actually seen in bibliographic data;
# langdetect itself only returns codes from this set.
ISO_639_1_CODES = frozenset({
    "aa", "ab", "af", "ak", "am", "an", "ar", "as", "av", "ay", "az",
    "ba", "be", "bg", "bh", "bi", "bm", "bn", "bo", "br", "bs",
    "ca", "ce", "ch", "co", "cr", "cs", "cu", "cv", "cy",
    "da", "de", "dv", "dz",
    "ee", "el", "en", "eo", "es", "et", "eu",
    "fa", "ff", "fi", "fj", "fo", "fr", "fy",
    "ga", "gd", "gl", "gn", "gu", "gv",
    "ha", "he", "hi", "ho", "hr", "ht", "hu", "hy", "hz",
    "ia", "id", "ie", "ig", "ii", "ik", "io", "is", "it", "iu",
    "ja", "jv",
    "ka", "kg", "ki", "kj", "kk", "kl", "km", "kn", "ko", "kr", "ks", "ku", "kv", "kw", "ky",
    "la", "lb", "lg", "li", "ln", "lo", "lt", "lu", "lv",
    "mg", "mh", "mi", "mk", "ml", "mn", "mr", "ms", "mt", "my",
    "na", "nb", "nd", "ne", "ng", "nl", "nn", "no", "nr", "nv", "ny",
    "oc", "oj", "om", "or", "os",
    "pa", "pi", "pl", "ps", "pt",
    "qu",
    "rm", "rn", "ro", "ru", "rw",
    "sa", "sc", "sd", "se", "sg", "si", "sk", "sl", "sm", "sn", "so", "sq", "sr", "ss", "st", "su", "sv", "sw",
    "ta", "te", "tg", "th", "ti", "tk", "tl", "tn", "to", "tr", "ts", "tt", "tw", "ty",
    "ug", "uk", "ur", "uz",
    "ve", "vi", "vo",
    "wa", "wo",
    "xh",
    "yi", "yo",
    "za", "zh", "zu",
})

# Normalize ISO 639 codes to 2-letter lowercase.
# Extracted from qa_detect_language.py — maps 3-letter ISO 639-3 codes
# and full language names to their 2-letter ISO 639-1 equivalents.
LANG_NORMALIZE = {
    "eng": "en", "en_us": "en", "en_gb": "en", "english": "en",
    "fre": "fr", "fra": "fr", "french": "fr",
    "ger": "de", "deu": "de", "german": "de",
    "spa": "es", "spanish": "es",
    "por": "pt", "portuguese": "pt",
    "chi": "zh", "zho": "zh", "chinese": "zh",
    "jpn": "ja", "japanese": "ja",
    "kor": "ko", "korean": "ko",
    "ara": "ar", "arabic": "ar",
    "rus": "ru", "russian": "ru",
    "ita": "it", "italian": "it",
    "pol": "pl", "polish": "pl",
    "tur": "tr", "turkish": "tr",
    "ind": "id", "indonesian": "id",
    "swe": "sv", "swedish": "sv",
    "ukr": "uk", "ukrainian": "uk",
    "hun": "hu", "hungarian": "hu",
    "vie": "vi", "vietnamese": "vi",
    "tha": "th", "thai": "th",
    "nob": "no", "nor": "no", "norwegian": "no",
    "dan": "da", "danish": "da",
    "fin": "fi", "finnish": "fi",
    "dut": "nl", "nld": "nl", "dutch": "nl",
    "cat": "ca", "catalan": "ca",
    "ron": "ro", "rum": "ro", "romanian": "ro",
    "ces": "cs", "cze": "cs", "czech": "cs",
    "slk": "sk", "slo": "sk", "slovak": "sk",
    "hrv": "hr", "croatian": "hr",
    "srp": "sr", "serbian": "sr",
    "bul": "bg", "bulgarian": "bg",
    "lit": "lt", "lithuanian": "lt",
    "lav": "lv", "latvian": "lv",
    "est": "et", "estonian": "et",
    "may": "ms", "msa": "ms", "malay": "ms",
    "fil": "tl", "tagalog": "tl",
    "urd": "ur", "urdu": "ur",
    "hin": "hi", "hindi": "hi",
    "ben": "bn", "bengali": "bn",
    "per": "fa", "fas": "fa", "persian": "fa",
    "heb": "he", "hebrew": "he",
}


def normalize_lang(code):
    """Normalize a language code to 2-letter ISO 639-1.

    Handles: ISO 639-3 codes (eng→en), full names (english→en),
    regional suffixes (en_US→en), and sentinel values (und, unknown, nan).
    Returns None for null/unknown/unrecognizable inputs.
    """
    if pd.isna(code) or not code:
        return None
    code = str(code).lower().strip()
    if code in ("nan", "none", "", "unknown", "und", "un",
                 "mis", "mul", "zxx"):
        return None
    # Already 2-letter?
    if len(code) == 2:
        return code
    # Strip regional suffix (en_US -> en)
    if "_" in code:
        code = code.split("_")[0]
        if len(code) == 2:
            return code
    return LANG_NORMALIZE.get(code)


def is_valid_iso639_1(code):
    """Return True if code is a recognized ISO 639-1 two-letter language code."""
    if not code or not isinstance(code, str):
        return False
    return code.lower().strip() in ISO_639_1_CODES


def detect_language(text):
    """Detect language from text using langdetect. Returns 2-letter code or None.

    Requires at least 20 characters to attempt detection — shorter texts
    produce unreliable results.
    """
    if not text or len(str(text).strip()) < 20:
        return None
    try:
        return detect(str(text))
    except LangDetectException:
        return None


# --- Cache I/O ---

def load_lang_cache(cache_dir, name):
    """Load a language cache CSV as {key: language} dict."""
    path = os.path.join(cache_dir, f"{name}.csv")
    if not os.path.exists(path):
        return {}
    df = pd.read_csv(path)
    return dict(zip(df["key"].astype(str), df["language"].fillna("")))


def save_lang_cache(data, cache_dir, name):
    """Save {key: language} dict as CSV cache."""
    os.makedirs(cache_dir, exist_ok=True)
    path = os.path.join(cache_dir, f"{name}.csv")
    df = pd.DataFrame([
        {"key": k, "language": v} for k, v in data.items()
    ])
    df.to_csv(path, index=False)


# --- OpenAlex helpers ---

OA_BASE = "https://api.openalex.org/works"


def build_oa_doi_filter(dois):
    """Build a pipe-separated DOI filter string for OpenAlex batch queries."""
    return "|".join(dois)


def _oa_params(extra):
    """Build OpenAlex query params with polite pool credentials."""
    params = {"mailto": MAILTO}
    if OPENALEX_API_KEY:
        params["api_key"] = OPENALEX_API_KEY
    params.update(extra)
    return params


# --- Pass 1: OpenAlex API backfill ---

def pass1_fetch_by_doi(dois, cache, counters,
                       request_timeout=60.0, max_retries=5,
                       retry_backoff=2.0, retry_jitter=1.0):
    """Batch-query OpenAlex for language by DOI. Updates cache in place.

    Queries 50 DOIs at a time using filter=doi:{d1}|{d2}|...&select=doi,language.
    """
    # Filter out DOIs already in cache
    to_query = [d for d in dois if d not in cache]
    counters["pass1_doi_total"] = len(dois)
    counters["pass1_doi_cached"] = len(dois) - len(to_query)
    counters["pass1_doi_to_query"] = len(to_query)

    if not to_query:
        return

    batch_size = 50
    for i in range(0, len(to_query), batch_size):
        batch = to_query[i:i + batch_size]
        doi_filter = build_oa_doi_filter(batch)
        params = _oa_params({
            "filter": f"doi:{doi_filter}",
            "select": "doi,language",
            "per_page": batch_size,
        })
        try:
            resp = retry_get(
                OA_BASE, params=params, delay=0.15,
                timeout=max(1, request_timeout),
                max_retries=max_retries,
                backoff_base=retry_backoff,
                jitter_max=retry_jitter,
                counters=counters,
            )
            for r in resp.json().get("results", []):
                doi_raw = r.get("doi", "")
                lang = r.get("language") or ""
                doi_norm = normalize_doi(doi_raw)
                if doi_norm:
                    cache[doi_norm] = lang
        except Exception as e:
            log.warning("DOI batch %d failed: %s", i, e)
            counters["pass1_errors"] = counters.get("pass1_errors", 0) + 1

        # Mark queried-but-not-returned DOIs as empty
        for d in batch:
            cache.setdefault(d, "")

        if (i // batch_size + 1) % 10 == 0:
            log.info("Pass 1 DOI: %d/%d batches",
                     i // batch_size + 1,
                     (len(to_query) + batch_size - 1) // batch_size)


def pass1_fetch_by_openalex_id(df, cache, counters,
                                request_timeout=60.0, max_retries=5,
                                retry_backoff=2.0, retry_jitter=1.0):
    """Query OpenAlex by openalex_id for records without DOIs.

    For records where language is still null and we have a source_id
    that starts with 'W' (OpenAlex work ID).
    """
    # Find records with null language, no DOI, but with an openalex_id
    mask = (
        df["language"].isna()
        & (df["doi"].isna() | (df["doi"] == ""))
        & df["source_id"].astype(str).str.startswith("W")
    )
    ids_to_query = df.loc[mask, "source_id"].astype(str).tolist()

    # Filter out cached
    to_query = [sid for sid in ids_to_query if sid not in cache]
    counters["pass1_oaid_total"] = len(ids_to_query)
    counters["pass1_oaid_to_query"] = len(to_query)

    if not to_query:
        return

    batch_size = 50
    for i in range(0, len(to_query), batch_size):
        batch = to_query[i:i + batch_size]
        id_filter = "|".join(batch)
        params = _oa_params({
            "filter": f"openalex_id:{id_filter}",
            "select": "id,language",
            "per_page": batch_size,
        })
        try:
            resp = retry_get(
                OA_BASE, params=params, delay=0.15,
                timeout=max(1, request_timeout),
                max_retries=max_retries,
                backoff_base=retry_backoff,
                jitter_max=retry_jitter,
                counters=counters,
            )
            for r in resp.json().get("results", []):
                oa_id = r.get("id", "").replace("https://openalex.org/", "")
                lang = r.get("language") or ""
                if oa_id:
                    cache[oa_id] = lang
        except Exception as e:
            log.warning("OA-ID batch %d failed: %s", i, e)
            counters["pass1_errors"] = counters.get("pass1_errors", 0) + 1

        for sid in batch:
            cache.setdefault(sid, "")


def pass1_apply_cache(df, cache):
    """Apply cached language values to the DataFrame.

    Only fills records where language is currently null.
    Returns number of records filled.
    """
    filled = 0
    for idx in df.index:
        if pd.notna(df.at[idx, "language"]) and str(df.at[idx, "language"]).strip():
            continue

        # Try DOI lookup
        doi = normalize_doi(df.at[idx, "doi"]) if pd.notna(df.at[idx, "doi"]) else ""
        if doi and doi in cache and cache[doi]:
            lang = normalize_lang(cache[doi])
            if lang and is_valid_iso639_1(lang):
                df.at[idx, "language"] = lang
                filled += 1
                continue

        # Try source_id lookup
        sid = str(df.at[idx, "source_id"]) if "source_id" in df.columns else ""
        if sid and sid in cache and cache[sid]:
            lang = normalize_lang(cache[sid])
            if lang and is_valid_iso639_1(lang):
                df.at[idx, "language"] = lang
                filled += 1

    return filled


# --- Pass 2: local text detection ---

def pass2_local_detect(df):
    """Fill remaining null language values using langdetect on title+abstract.

    Also flags nonsensical existing values (codes not in ISO 639-1).
    Returns number of records filled.
    """
    filled = 0
    for idx in df.index:
        current = df.at[idx, "language"]
        if pd.notna(current) and str(current).strip():
            # Check if current value is valid
            norm = normalize_lang(current)
            if norm and is_valid_iso639_1(norm):
                continue
            # Invalid code — try to detect
            log.debug("Invalid language code '%s' at index %d, re-detecting", current, idx)

        # Build detection text: prefer abstract, fall back to title
        abstract = str(df.at[idx, "abstract"]) if pd.notna(df.at[idx, "abstract"]) else ""
        title = str(df.at[idx, "title"]) if pd.notna(df.at[idx, "title"]) else ""

        text = abstract if len(abstract) >= 50 else title
        if not text or len(text.strip()) < 20:
            text = f"{title} {abstract}".strip()

        detected = detect_language(text)
        if detected and is_valid_iso639_1(detected):
            df.at[idx, "language"] = detected
            filled += 1

    return filled


# --- Main ---

def main():
    parser = argparse.ArgumentParser(
        description="Enrich missing language tags via OpenAlex + local detection")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show counts, don't modify data")
    parser.add_argument("--works-input",
                        default=os.path.join(CATALOGS_DIR, "enriched_works.csv"),
                        help="Input/output works CSV (default: enriched_works.csv)")
    parser.add_argument("--run-id", default=None,
                        help="Unique run identifier (default: timestamp)")
    parser.add_argument("--request-timeout", type=float, default=60.0,
                        help="Per-request timeout in seconds (default: 60)")
    parser.add_argument("--max-retries", type=int, default=5,
                        help="Maximum retries for transient failures (default: 5)")
    parser.add_argument("--retry-backoff", type=float, default=2.0,
                        help="Base for exponential backoff (default: 2.0)")
    parser.add_argument("--retry-jitter", type=float, default=1.0,
                        help="Max random jitter added to backoff (default: 1.0)")
    args = parser.parse_args()

    run_id = args.run_id or make_run_id()
    t0 = time.time()

    path = args.works_input
    df = pd.read_csv(path)
    log.info("Loaded %d works from %s", len(df), path)

    # Normalize existing language codes first
    df["language"] = df["language"].apply(normalize_lang)

    null_before = int(df["language"].isna().sum())
    log.info("Language null before enrichment: %d / %d (%.1f%%)",
             null_before, len(df), null_before / len(df) * 100)

    if args.dry_run:
        log.info("Dry run — not modifying data.")
        return

    counters = {
        "total_works": len(df),
        "null_before": null_before,
    }

    # --- Pass 1: OpenAlex API backfill ---
    log.info("Pass 1: OpenAlex API backfill")
    cache = load_lang_cache(CACHE_DIR, "language_resolved")

    # 1a: query by DOI
    dois_to_query = []
    for idx in df.index:
        if pd.notna(df.at[idx, "language"]) and str(df.at[idx, "language"]).strip():
            continue
        doi = normalize_doi(df.at[idx, "doi"]) if pd.notna(df.at[idx, "doi"]) else ""
        if doi:
            dois_to_query.append(doi)

    log.info("Pass 1a: %d DOIs to query", len(dois_to_query))
    pass1_fetch_by_doi(
        dois_to_query, cache, counters,
        args.request_timeout, args.max_retries,
        args.retry_backoff, args.retry_jitter,
    )

    # 1b: query by openalex_id
    log.info("Pass 1b: querying by openalex_id")
    pass1_fetch_by_openalex_id(
        df, cache, counters,
        args.request_timeout, args.max_retries,
        args.retry_backoff, args.retry_jitter,
    )

    save_lang_cache(cache, CACHE_DIR, "language_resolved")

    # Apply cache results
    filled_pass1 = pass1_apply_cache(df, cache)
    counters["pass1_filled"] = filled_pass1
    null_after_pass1 = int(df["language"].isna().sum())
    log.info("Pass 1 filled %d, remaining null: %d", filled_pass1, null_after_pass1)

    # --- Pass 2: local text detection ---
    log.info("Pass 2: local text detection (langdetect)")
    filled_pass2 = pass2_local_detect(df)
    counters["pass2_filled"] = filled_pass2
    null_after_pass2 = int(df["language"].isna().sum())
    log.info("Pass 2 filled %d, remaining null: %d", filled_pass2, null_after_pass2)

    # Save
    save_csv(df, path)

    elapsed = time.time() - t0
    counters.update({
        "null_after": null_after_pass2,
        "total_filled": null_before - null_after_pass2,
        "elapsed_seconds": round(elapsed, 1),
    })

    log.info("Done. Language coverage: %d/%d (%.1f%%). Filled %d total. Elapsed: %.0fs",
             len(df) - null_after_pass2, len(df),
             (len(df) - null_after_pass2) / len(df) * 100,
             null_before - null_after_pass2, elapsed)

    report_path = save_run_report(counters, run_id, "enrich_language")
    log.info("Run report: %s", report_path)


if __name__ == "__main__":
    main()
