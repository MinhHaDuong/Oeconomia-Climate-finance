#!/usr/bin/env python3
"""Count yearly economics works and climate-finance works from IDEAS/RePEc dumps.

This script parses local ReDIF metadata files (recommended from RePEc archives),
deduplicates records, and computes yearly counts for 1990-2025.

Outputs:
- $DATA/catalogs/repec_econ_yearly.csv

Usage:
    uv run python scripts/count_repec_econ_cf.py --repec-root ~/data/datasets/external/RePEc
"""

import argparse
import gzip
import os
import re
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
from utils import CATALOGS_DIR, RAW_DIR, normalize_doi, normalize_title, save_csv

YEAR_MIN = 1990
YEAR_MAX = 2025
CLIMATE_FINANCE_REGEX = re.compile(r"\bclimate[\s-]?finance\b", flags=re.IGNORECASE)
DEFAULT_REPEC_ROOT = os.path.expanduser(
    os.environ.get("REPEC_ROOT", "~/data/datasets/external/RePEc")
)


def parse_args():
    parser = argparse.ArgumentParser(description="Count yearly economics/climate-finance from RePEc")
    parser.add_argument(
        "--repec-root",
        type=str,
        default=DEFAULT_REPEC_ROOT,
        help="Root directory containing ReDIF files",
    )
    parser.add_argument(
        "--include-templates",
        type=str,
        default="ReDIF-Article,ReDIF-Paper,ReDIF-Book,ReDIF-Chapter",
        help="Comma-separated Template-Type prefixes to include",
    )
    parser.add_argument(
        "--out",
        type=str,
        default=os.path.join(CATALOGS_DIR, "repec_econ_yearly.csv"),
        help="Output CSV path",
    )
    return parser.parse_args()


def iter_metadata_files(root):
    if not os.path.isdir(root):
        return

    for base, _, files in os.walk(root):
        for name in files:
            lower = name.lower()
            if lower.endswith((".rdf", ".redif", ".txt", ".rdf.gz", ".txt.gz", ".redif.gz")):
                yield os.path.join(base, name)


def parse_redif_file(path):
    opener = gzip.open if path.lower().endswith(".gz") else open
    mode = "rt"

    records = []
    current = {}
    last_key = None

    with opener(path, mode, encoding="utf-8", errors="ignore") as handle:
        for raw_line in handle:
            line = raw_line.rstrip("\n")

            if not line.strip():
                continue

            if line.startswith("Template-Type:"):
                if current:
                    records.append(current)
                current = {}
                last_key = None

            if re.match(r"^[A-Za-z0-9_-]+:\s*", line):
                key, value = line.split(":", 1)
                key = key.strip().lower()
                value = value.strip()
                current.setdefault(key, []).append(value)
                last_key = key
            elif line.startswith((" ", "\t")) and last_key:
                continuation = line.strip()
                if current.get(last_key):
                    current[last_key][-1] = (current[last_key][-1] + " " + continuation).strip()

    if current:
        records.append(current)
    return records


def first_value(record, key):
    values = record.get(key.lower(), [])
    if not values:
        return ""
    return str(values[0]).strip()


def extract_year(record):
    for key in ("year", "creation-date", "issued", "date"):
        value = first_value(record, key)
        if not value:
            continue
        match = re.search(r"\b(19\d{2}|20\d{2})\b", value)
        if match:
            return int(match.group(1))
    return None


def include_template(record, allowed_prefixes):
    template = first_value(record, "template-type")
    if not template:
        return False
    template = template.strip()
    return any(template.startswith(prefix) for prefix in allowed_prefixes)


def build_dedup_key(title, year, doi, handle):
    if doi:
        return f"doi::{doi}"
    norm_title = normalize_title(title)
    if norm_title and year:
        return f"titleyear::{norm_title}::{year}"
    if handle:
        return f"handle::{handle}"
    return ""


def count_repec_yearly(repec_root, include_templates):
    allowed_templates = [x.strip() for x in include_templates.split(",") if x.strip()]

    if not os.path.isdir(repec_root):
        raise FileNotFoundError(
            f"RePEc root not found: {repec_root}. "
            "Provide --repec-root pointing to local ReDIF mirror."
        )

    files = list(iter_metadata_files(repec_root))
    if not files:
        raise FileNotFoundError(f"No ReDIF files found under {repec_root}")

    print(f"Found {len(files)} metadata files under {repec_root}")

    dedup_seen = set()
    records = []
    parsed = 0

    for idx, path in enumerate(files, start=1):
        rows = parse_redif_file(path)
        for row in rows:
            if not include_template(row, allowed_templates):
                continue

            year = extract_year(row)
            if year is None or year < YEAR_MIN or year > YEAR_MAX:
                continue

            title = first_value(row, "title")
            abstract = first_value(row, "abstract")
            doi = normalize_doi(first_value(row, "doi"))
            handle = first_value(row, "handle")

            dedup_key = build_dedup_key(title=title, year=year, doi=doi, handle=handle)
            if not dedup_key:
                continue
            if dedup_key in dedup_seen:
                continue
            dedup_seen.add(dedup_key)

            text = f"{title} {abstract}".strip()
            is_cf = bool(CLIMATE_FINANCE_REGEX.search(text))

            records.append({
                "year": year,
                "is_climate_finance": is_cf,
            })

        parsed += len(rows)
        if idx % 1000 == 0:
            print(f"  Parsed files: {idx}/{len(files)} | records scanned: {parsed:,} | kept: {len(records):,}")

    if not records:
        raise RuntimeError("No eligible RePEc records found after parsing/filtering")

    df = pd.DataFrame(records)
    by_year = (
        df.groupby("year", as_index=False)
        .agg(n_economics=("is_climate_finance", "size"),
             n_climate_finance=("is_climate_finance", "sum"))
    )

    full_years = pd.DataFrame({"year": list(range(YEAR_MIN, YEAR_MAX + 1))})
    out = full_years.merge(by_year, on="year", how="left").fillna(0)
    out["n_economics"] = out["n_economics"].astype(int)
    out["n_climate_finance"] = out["n_climate_finance"].astype(int)
    out["n_climate_finance_title"] = out["n_climate_finance"]
    out["n_climate_finance_abstract"] = out["n_climate_finance"]
    out["share_climate_finance"] = out["n_climate_finance"] / out["n_economics"].replace({0: pd.NA})
    out["share_climate_finance"] = out["share_climate_finance"].fillna(0.0)
    out["source"] = "repec"
    out["climate_finance_pattern"] = CLIMATE_FINANCE_REGEX.pattern
    out["economics_definition"] = "RePEc corpus (template-filtered)"
    out["query_mode"] = "local RedIF parse: title+abstract regex"
    out["types_filter"] = include_templates

    out = out[[
        "source", "year", "n_economics", "n_climate_finance_title",
        "n_climate_finance_abstract", "n_climate_finance", "share_climate_finance",
        "climate_finance_pattern", "economics_definition", "query_mode", "types_filter",
    ]]

    return out


def main():
    args = parse_args()
    out = count_repec_yearly(
        repec_root=args.repec_root,
        include_templates=args.include_templates,
    )

    save_csv(out, args.out)

    print("Done.")
    print(f"  Years: {out['year'].min()}–{out['year'].max()}")
    print(f"  Total economics: {int(out['n_economics'].sum()):,}")
    print(f"  Total climate finance: {int(out['n_climate_finance'].sum()):,}")


if __name__ == "__main__":
    main()
