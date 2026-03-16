"""Detect and fix language tags in the refined corpus.

Uses langdetect on title+abstract text to identify the actual language,
then compares with the existing `language` field. Fixes mismatches and
fills NaN values.

Usage:
    uv run python scripts/qa_detect_language.py [--apply] [--sample N]

Outputs:
    - stdout: summary of changes
    - data/catalogs/refined_works.csv: updated in-place (with --apply)
    - content/tables/qa_language_report.csv: full comparison report
"""

import argparse
import os
import sys

import pandas as pd
from langdetect import detect, LangDetectException

sys.path.insert(0, os.path.dirname(__file__))
from utils import CATALOGS_DIR, get_logger, save_csv, BASE_DIR

log = get_logger("qa_detect_language")

# Normalize ISO 639 codes to 2-letter lowercase
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
    """Normalize a language code to 2-letter ISO 639-1."""
    if pd.isna(code) or not code:
        return None
    code = str(code).lower().strip()
    if code in ("nan", "none", "", "unknown", "und", "un"):
        return None
    # Already 2-letter?
    if len(code) == 2:
        return code
    # Strip regional suffix (en_US -> en)
    if "_" in code:
        code = code.split("_")[0]
        if len(code) == 2:
            return code
    return LANG_NORMALIZE.get(code, code[:2] if len(code) >= 2 else None)


def detect_language(text):
    """Detect language from text using langdetect. Returns 2-letter code or None."""
    if not text or len(str(text).strip()) < 20:
        return None
    try:
        return detect(str(text))
    except LangDetectException:
        return None


def main():
    parser = argparse.ArgumentParser(description="Detect and fix language tags")
    parser.add_argument("--apply", action="store_true", help="Write fixes to refined_works.csv")
    parser.add_argument("--sample", type=int, default=0, help="Only process N random records (0=all)")
    args = parser.parse_args()

    path = os.path.join(CATALOGS_DIR, "refined_works.csv")
    df = pd.read_csv(path)
    log.info("Loaded %d works", len(df))

    if args.sample > 0:
        df = df.sample(min(args.sample, len(df)), random_state=42).copy()
        log.info("Sampling %d records", len(df))

    # Normalize existing language codes
    df["lang_original"] = df["language"].copy()
    df["lang_normalized"] = df["language"].apply(normalize_lang)

    # Build detection text: prefer abstract, fall back to title
    df["detect_text"] = df["abstract"].fillna("").astype(str)
    short_abstract = df["detect_text"].str.len() < 50
    df.loc[short_abstract, "detect_text"] = df.loc[short_abstract, "title"].fillna("")

    # Detect language
    log.info("Detecting languages...")
    total = len(df)
    detected = []
    for i, text in enumerate(df["detect_text"]):
        if i % 2000 == 0 and i > 0:
            log.info("  %d/%d...", i, total)
        detected.append(detect_language(text))
    df["lang_detected"] = detected

    # Compare
    df["lang_final"] = df["lang_normalized"]

    # Fix 1: fill NaN normalized with detected
    was_null = df["lang_normalized"].isna()
    has_detection = df["lang_detected"].notna()
    filled = was_null & has_detection
    df.loc[filled, "lang_final"] = df.loc[filled, "lang_detected"]

    # Fix 2: mismatch between normalized and detected
    both_present = df["lang_normalized"].notna() & df["lang_detected"].notna()
    mismatch = both_present & (df["lang_normalized"] != df["lang_detected"])

    # Trust detected over original for short/suspicious codes,
    # but keep original if detected is low-confidence (short text)
    text_len = df["detect_text"].str.len()
    confident_detect = mismatch & (text_len >= 100)
    df.loc[confident_detect, "lang_final"] = df.loc[confident_detect, "lang_detected"]

    # Summary
    log.info("=== Language detection summary ===")
    log.info("Total records:       %d", total)
    log.info("Original NaN/empty:  %d", was_null.sum())
    log.info("  -> filled by detection:  %d", filled.sum())
    log.info("  -> still unknown:        %d", (was_null & ~has_detection).sum())
    log.info("Normalized != detected (confident): %d", confident_detect.sum())
    log.info("Normalized != detected (low-conf):  %d", (mismatch & ~confident_detect).sum())

    # Show language distribution before/after
    log.info("=== Language distribution: before ===")
    before = df["lang_normalized"].fillna("(unknown)")
    log.info("\n%s", before.value_counts().head(15).to_string())
    log.info("=== Language distribution: after ===")
    after = df["lang_final"].fillna("(unknown)")
    log.info("\n%s", after.value_counts().head(15).to_string())

    # Show some interesting mismatches
    if mismatch.any():
        log.info("=== Sample mismatches (original -> detected) ===")
        sample_mm = df[mismatch].head(10)
        for _, row in sample_mm.iterrows():
            title = str(row["title"])[:80]
            log.info("  %s -> %s: %s", row['lang_normalized'], row['lang_detected'], title)

    # Save report
    report = df[["lang_original", "lang_normalized", "lang_detected", "lang_final"]].copy()
    report["changed"] = df["lang_original"].apply(normalize_lang) != df["lang_final"]
    report_path = os.path.join(BASE_DIR, "content", "tables", "qa_language_report.csv")
    save_csv(report[report["changed"]], report_path)

    if args.apply:
        # Write back to refined_works.csv
        full_df = pd.read_csv(path)
        if args.sample > 0:
            # Only update sampled rows
            full_df["lang_normalized"] = full_df["language"].apply(normalize_lang)
            for idx in df.index:
                full_df.loc[idx, "language"] = df.loc[idx, "lang_final"]
        else:
            full_df["language"] = df["lang_final"]
        full_df.to_csv(path, index=False)
        log.info("Updated %s", path)
    else:
        log.info("Dry run. Use --apply to write changes.")


if __name__ == "__main__":
    main()
