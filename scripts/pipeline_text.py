"""Pure text-transform utilities for the literature indexing pipeline.

All functions here are stateless: no I/O, no side effects, no imports
beyond stdlib + pandas. Safe to import in any context.

Exports
-------
normalize_doi
    Strip URL prefix, lowercase, trim a DOI string.
normalize_title
    Lowercase, strip punctuation, collapse spaces for fuzzy dedup.
reconstruct_abstract
    Rebuild plain text from an OpenAlex abstract_inverted_index dict.
clean_doi
    Extract a bare 10.xxxx/... DOI from a raw or URL-prefixed string.
ISO_639_1_CODES
    Frozenset of all 184 valid ISO 639-1 two-letter language codes.
LANG_NORMALIZE
    Dict mapping ISO 639-3 codes and full names to ISO 639-1.
normalize_lang
    Normalise any language code or name to 2-letter ISO 639-1.
is_valid_iso639_1
    Return True if a string is a recognised ISO 639-1 code.
detect_language
    Detect language from text using langdetect (seeded for reproducibility).
"""

import re

import pandas as pd


# ---------------------------------------------------------------------------
# DOI helpers
# ---------------------------------------------------------------------------

def normalize_doi(doi_raw):
    """Normalize a DOI: handle lists, strip URL prefix, lowercase, trim."""
    if doi_raw is None:
        return ""
    if isinstance(doi_raw, list):
        if not doi_raw:
            return ""
        doi_raw = doi_raw[0]
    doi = str(doi_raw).strip()
    for prefix in ("https://doi.org/", "http://doi.org/", "http://dx.doi.org/",
                    "https://dx.doi.org/", "doi:"):
        if doi.lower().startswith(prefix):
            doi = doi[len(prefix):]
            break
    return doi.strip().lower()


def clean_doi(raw):
    """Extract a clean DOI (10.xxxx/...) from a raw string.

    Handles URL-prefixed DOIs from LLM extraction:
    - https://doi.org/10.xxx → 10.xxx
    - http://dx.doi.org/10.xxx → 10.xxx
    - https://doi.org/doi:10.xxx → 10.xxx
    - https://publisher.com/doi/full/10.xxx → 10.xxx
    - Already-clean 10.xxx → 10.xxx
    - Non-DOI URLs (SSRN, HDL) → ""
    - None / "" → ""
    """
    if not raw:
        return ""
    raw = str(raw).strip()
    if not raw:
        return ""
    # Extract the 10.xxxx/... DOI pattern from anywhere in the string
    m = re.search(r"(10\.\d{4,}[^\s]*)", raw)
    if m:
        return m.group(1).lower()
    return ""


# ---------------------------------------------------------------------------
# Title helpers
# ---------------------------------------------------------------------------

def normalize_title(title):
    """Normalize a title for fuzzy dedup: lowercase, strip punctuation, collapse spaces."""
    if not title:
        return ""
    t = title.lower()
    t = re.sub(r"[^\w\s]", "", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


# ---------------------------------------------------------------------------
# Abstract helpers
# ---------------------------------------------------------------------------

def reconstruct_abstract(inverted_index):
    """Rebuild plain text from an OpenAlex abstract_inverted_index dict."""
    if not inverted_index:
        return ""
    word_positions = []
    for word, positions in inverted_index.items():
        for pos in positions:
            word_positions.append((pos, word))
    word_positions.sort()
    return " ".join(w for _, w in word_positions)


# ---------------------------------------------------------------------------
# Language normalisation
# ---------------------------------------------------------------------------

# ISO 639-1 valid language codes (the 184 codes from the standard).
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

# Map ISO 639-3 codes and full language names to 2-letter ISO 639-1.
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


_langdetect_seeded = False


def detect_language(text):
    """Detect language from text using langdetect. Returns 2-letter code or None.

    Requires at least 20 characters to attempt detection — shorter texts
    produce unreliable results. Seeds the detector on first call for
    reproducibility (langdetect is non-deterministic by default).
    """
    global _langdetect_seeded
    if not text or len(str(text).strip()) < 20:
        return None
    try:
        from langdetect import detect, LangDetectException
        if not _langdetect_seeded:
            from langdetect import DetectorFactory
            DetectorFactory.seed = 0
            _langdetect_seeded = True
        return detect(str(text))
    except LangDetectException:
        return None
