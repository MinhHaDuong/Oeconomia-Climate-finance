"""Generate docs/missing_references.txt.

Lists bibliography entries that lack a corresponding PDF in docs/articles/.
Matching tries, in order:
  1. Exact bib key:  {bib_key}.pdf
  2. DOI slug:       last path component of DOI, with special chars → '_'
  3. Filename contains bib key as substring (case-insensitive)
  4. Filename contains first author lastname + year (e.g., "weitzman" + "2007")

Output format mirrors the doifetch input convention:
  doi:<doi>    TAB  <Label>
  url:<url>    TAB  <Label>
  isbn:<isbn>  TAB  <Label>
  # No DOI or ISBN:
  #	<Label>

Run with:
  uv run python scripts/gen_missing_references.py
"""

import argparse
import os
import re

import bibtexparser

from utils import get_logger

log = get_logger("gen_missing_references")

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BIB_PATH = os.path.join(BASE_DIR, "content", "bibliography", "main.bib")
ARTICLES_DIR = os.path.join(BASE_DIR, "docs", "articles")
OUTPUT_PATH = os.path.join(BASE_DIR, "docs", "missing_references.txt")

# ---------------------------------------------------------------------------
# Hard-coded ISBNs for books that lack a DOI in the .bib file.
# Update this dict whenever you add ISBNs for new books.
# ---------------------------------------------------------------------------
KNOWN_ISBNS: dict[str, str] = {
    "desrosieres1998":  "9780674009691",
    "porter1995":       "9780691029085",
    "callon1998":       "9780631206088",
    "mackenzie2006":    "9780262134606",
    "kaul2003":         "9780195157406",
    "merry2016":        "9780226514277",
    "power1997":        "9780198296034",
    "pottier2016":      "9782021234831",
    "aykut_dahan2015":  "9782724616804",
    "stern2009":        "9781847920386",
}


def doi_segments(doi: str) -> list[str]:
    """Return candidate filename substrings for a DOI.

    Includes the raw last path segment and a slugified version (hyphens → _).
    """
    segment = doi.rstrip("/").rsplit("/", 1)[-1]
    slug = re.sub(r"[^\w]", "_", segment)
    # Also try replacing slashes for full-DOI filenames (e.g. 10.1787_5k44...)
    full_slug = re.sub(r"[^\w]", "_", doi)
    return list({segment.lower(), slug.lower(), full_slug.lower()})


def first_author_lastname(author_field: str) -> str:
    """Extract the last name of the first author (lowercase, no accents stripped)."""
    if not author_field:
        return ""
    first = author_field.split(" and ")[0].strip()
    if "," in first:
        last = first.split(",")[0].strip()
    else:
        tokens = first.split()
        last = tokens[-1] if tokens else first
    return re.sub(r"[{}\\]", "", last).lower().strip()


def extract_last_name(person: str) -> str:
    """Extract last name from a single author string (may be 'Last, First' or 'First Last')."""
    person = person.strip()
    if "," in person:
        last = person.split(",")[0]
    else:
        tokens = person.split()
        last = tokens[-1] if tokens else person
    return last.strip("{}").strip()


def build_label(entry: dict) -> str:
    """Build a human-readable label from bib entry metadata."""
    author = entry.get("author", "")
    year = entry.get("year", "")
    title = entry.get("title", "").replace("{", "").replace("}", "")

    # Author label: corporate / 1 author / 2 authors / 3+
    if author.startswith("{"):
        author_label = author.strip("{}")
    else:
        parts = [p.strip() for p in author.split(" and ") if p.strip()]
        if len(parts) == 0:
            author_label = ""
        elif len(parts) == 1:
            author_label = extract_last_name(parts[0])
        elif len(parts) == 2:
            author_label = f"{extract_last_name(parts[0])} & {extract_last_name(parts[1])}"
        else:
            author_label = f"{extract_last_name(parts[0])} et al."

    # Shorten title to ≤60 chars
    short_title = title if len(title) <= 60 else title[:57] + "..."

    return f"{author_label} {year} - {short_title}"


def load_existing_pdfs(articles_dir: str) -> list[str]:
    """Return lowercased stems of all PDF filenames in articles_dir."""
    if not os.path.isdir(articles_dir):
        return []
    return [
        f.lower()
        for f in os.listdir(articles_dir)
        if f.lower().endswith(".pdf")
    ]


def has_pdf(entry: dict, pdf_stems: list[str]) -> bool:
    """Return True if a matching PDF exists for this bib entry."""
    bib_key = entry.get("ID", "").lower()
    doi = entry.get("doi", "").strip().lower()
    year = entry.get("year", "").strip()
    first_last = first_author_lastname(entry.get("author", ""))

    # 1. Exact bib key
    if f"{bib_key}.pdf" in pdf_stems:
        return True

    # 2. DOI segments (last path segment, slugified, full slugified)
    if doi:
        for seg in doi_segments(doi):
            if seg:
                for stem in pdf_stems:
                    if seg in stem:
                        return True

    # 3. Bib key as substring
    for stem in pdf_stems:
        if bib_key and bib_key in stem:
            return True

    # 4. First author lastname + year in filename
    if first_last and year:
        for stem in pdf_stems:
            if first_last in stem and year in stem:
                return True

    return False


def identifier_line(entry: dict) -> tuple[str, str]:
    """Return (prefix, identifier_string) for the missing-references output.

    prefix is one of: 'doi', 'url', 'isbn', 'none'
    """
    doi = entry.get("doi", "").strip()
    url = entry.get("url", "").strip()
    bib_key = entry.get("ID", "")

    if doi:
        return ("doi", doi)
    if url:
        return ("url", url)
    isbn = KNOWN_ISBNS.get(bib_key)
    if isbn:
        return ("isbn", isbn)
    return ("none", "")


def _format_output_lines(doi_lines, url_lines, isbn_lines, no_id_lines):
    """Combine identifier sections with blank-line separators."""
    sections = [doi_lines, url_lines, isbn_lines]
    lines = []
    for section in sections:
        if section:
            if lines:
                lines.append("")
            lines.extend(section)
    if no_id_lines:
        if lines:
            lines.append("")
        lines.append("# No DOI or ISBN:")
        lines.extend(no_id_lines)
    return lines


def main() -> None:
    # Parse bibliography
    with open(BIB_PATH, encoding="utf-8") as f:
        bib_db = bibtexparser.load(f)

    pdf_stems = load_existing_pdfs(ARTICLES_DIR)
    log.info("Found %d PDFs in %s", len(pdf_stems), ARTICLES_DIR)

    doi_lines: list[str] = []
    url_lines: list[str] = []
    isbn_lines: list[str] = []
    no_id_lines: list[str] = []

    for entry in bib_db.entries:
        if has_pdf(entry, pdf_stems):
            continue

        label = build_label(entry)
        prefix, ident = identifier_line(entry)

        if prefix == "doi":
            doi_lines.append(f"doi:{ident}\t{label}")
        elif prefix == "url":
            url_lines.append(f"url:{ident}\t{label}")
        elif prefix == "isbn":
            isbn_lines.append(f"isbn:{ident}\t{label}")
        else:
            no_id_lines.append(f"#\t{label}")

    lines = _format_output_lines(doi_lines, url_lines, isbn_lines, no_id_lines)

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    sections = [("DOI", doi_lines), ("URL", url_lines),
                ("ISBN", isbn_lines), ("no identifier", no_id_lines)]
    n_missing = sum(len(s) for _, s in sections)
    log.info("Written %d missing entries to %s", n_missing, OUTPUT_PATH)
    for label, section in sections:
        if section:
            log.info("  %d with %s", len(section), label)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    main()
