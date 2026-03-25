"""Export language distribution table for the data paper.

Produces:
- content/tables/tab_languages.md: Quarto-includable markdown table

Shows language distribution in the refined corpus with ISO 639-1 codes
normalised (e.g., en_US → en) and grouped into major languages + "Other".
"""

import argparse
import os

import pandas as pd

from utils import CATALOGS_DIR, get_logger, BASE_DIR

log = get_logger("export_language_table")

REFINED_PATH = os.path.join(CATALOGS_DIR, "refined_works.csv")
OUTPUT_DIR = os.path.join(BASE_DIR, "content", "tables")
OUTPUT_MD = os.path.join(OUTPUT_DIR, "tab_languages.md")

# ISO 639-1 → display name for languages we want to show individually
LANGUAGE_NAMES = {
    "en": "English",
    "pt": "Portuguese",
    "de": "German",
    "es": "Spanish",
    "fr": "French",
    "id": "Indonesian",
    "tr": "Turkish",
    "ko": "Korean",
    "ru": "Russian",
    "sv": "Swedish",
    "ar": "Arabic",
    "uk": "Ukrainian",
    "nl": "Dutch",
    "pl": "Polish",
    "ja": "Japanese",
    "zh": "Chinese",
    "it": "Italian",
    "fi": "Finnish",
    "no": "Norwegian",
    "hu": "Hungarian",
    "cs": "Czech",
    "da": "Danish",
    "hr": "Croatian",
    "ca": "Catalan",
    "ms": "Malay",
    "th": "Thai",
    "vi": "Vietnamese",
    "el": "Greek",
    "ro": "Romanian",
    "sk": "Slovak",
    "hi": "Hindi",
    "fa": "Persian",
    "he": "Hebrew",
    "bn": "Bengali",
    "lt": "Lithuanian",
    "sl": "Slovenian",
    "et": "Estonian",
    "lv": "Latvian",
    "bg": "Bulgarian",
    "sr": "Serbian",
}

# Minimum count to show individually (otherwise grouped as "Other")
MIN_COUNT = 20


def normalise_language(code: str) -> str:
    """Normalise language codes: en_US → en, zh_CN → zh, etc."""
    if pd.isna(code):
        return "unknown"
    code = str(code).strip().lower()
    if "_" in code:
        code = code.split("_")[0]
    if "-" in code:
        code = code.split("-")[0]
    return code


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()

    df = pd.read_csv(REFINED_PATH, usecols=["language"])
    df["lang"] = df["language"].apply(normalise_language)

    counts = df["lang"].value_counts()
    total = len(df)

    rows = []
    other_count = 0
    other_langs = []

    for lang, count in counts.items():
        if count >= MIN_COUNT and lang != "unknown":
            name = LANGUAGE_NAMES.get(lang, lang.upper())
            rows.append({
                "Language": name,
                "Code": lang,
                "Works": count,
                "Share (%)": f"{100 * count / total:.1f}",
            })
        elif lang != "unknown":
            other_count += count
            other_langs.append(lang)

    unknown_count = counts.get("unknown", 0)

    rows.sort(key=lambda r: -int(r["Works"]))

    if other_count > 0:
        rows.append({
            "Language": f"Other ({len(other_langs)} languages)",
            "Code": "—",
            "Works": other_count,
            "Share (%)": f"{100 * other_count / total:.1f}",
        })

    if unknown_count > 0:
        rows.append({
            "Language": "Unclassified",
            "Code": "—",
            "Works": unknown_count,
            "Share (%)": f"{100 * unknown_count / total:.1f}",
        })

    rows.append({
        "Language": "**Total**",
        "Code": "",
        "Works": total,
        "Share (%)": "100.0",
    })

    table = pd.DataFrame(rows)

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    lines = [
        f"| {' | '.join(table.columns)} |",
        "| :---------- | :---- | ----: | --------: |",
    ]
    for _, row in table.iterrows():
        lines.append(f"| {' | '.join(str(v) for v in row)} |")

    lines.append("")
    lines.append(": Language distribution in the refined corpus. {#tbl-languages}")

    md = "\n".join(lines) + "\n"
    with open(OUTPUT_MD, "w", encoding="utf-8") as f:
        f.write(md)

    log.info("Wrote %s (%d language rows)", OUTPUT_MD, len(rows))

    for row in rows:
        log.info("  %s: %s (%s%%)", row["Language"], row["Works"], row["Share (%)"])


if __name__ == "__main__":
    main()
