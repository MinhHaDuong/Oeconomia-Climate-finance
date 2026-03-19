"""QA checks on the manuscript PDF: word count + Oeconomia editorial compliance.

Extracts text from the PDF, counts words (total and per-section), and checks
editorial requirements from docs/oeconomia-style.md and docs/Informations aux
auteurs.md:
  - Abstracts in both French and English
  - Keywords in both languages
  - Section numbering (1., 1.1 — max two levels)
  - Bibliography section present
  - AI-tell blacklisted words (from AGENTS.md)

Usage:
    uv run python scripts/qa_word_count.py [path/to/manuscript.pdf]

If no path is given, defaults to output/content/manuscript.pdf.
"""

import argparse
import re
import sys

import pdfplumber

from utils import get_logger

log = get_logger("qa_word_count")


DEFAULT_PDF = "output/content/manuscript.pdf"

# Section headings: numbered (1. Foo, 2.1 Bar) or known unnumbered headings
HEADING_RE = re.compile(
    r"^(?:"
    r"(?:\d+\.[\d.]*\s+[A-Z])"  # numbered: "1. Intro", "2.1 Back"
    r"|(?:Abstract|Résumé|References|Bibliography|Acknowledgements|Appendix|Conclusion)"
    r"|(?:[A-Z][A-Z\s]{4,}$)"  # ALL-CAPS line (≥5 chars)
    r")",
    re.MULTILINE,
)

# AI-tell blacklisted words (from AGENTS.md)
BLACKLISTED_WORDS = [
    "delve", "nuanced", "multifaceted", "pivotal", "crucial",
    "intricate", "comprehensive", "meticulous", "vibrant", "arguably",
    "showcasing", "underscores", "foster", "tapestry", "landscape",
]

# Blacklisted phrases
BLACKLISTED_PHRASES = [
    "it is important to note", "in the realm of", "stands as a testament to",
    "plays a vital role", "the landscape of", "navigating the complexities",
    "the interplay between", "sheds light on", "a growing body of literature",
    "offers a lens through which", "it is worth noting", "cannot be overstated",
]

# "robust" is only blacklisted in non-statistical sense — flag for manual review
REVIEW_WORDS = ["robust"]


def count_words(text: str) -> int:
    """Count words in a string, excluding pure numbers and punctuation."""
    return len([w for w in text.split() if re.search(r"[a-zA-Z]", w)])


def extract_sections(pages_text: list[str]) -> list[tuple[str, int]]:
    """Split full text into (heading, word_count) pairs."""
    full = "\n".join(pages_text)
    matches = list(HEADING_RE.finditer(full))
    if not matches:
        return [("(entire document)", count_words(full))]

    sections = []
    pre = full[: matches[0].start()]
    pre_wc = count_words(pre)
    if pre_wc > 0:
        sections.append(("(front matter)", pre_wc))

    for i, m in enumerate(matches):
        line_end = full.index("\n", m.start()) if "\n" in full[m.start() :] else len(full)
        heading = full[m.start() : line_end].strip()
        body_start = line_end
        body_end = matches[i + 1].start() if i + 1 < len(matches) else len(full)
        body = full[body_start:body_end]
        sections.append((heading, count_words(body)))

    return sections


def check_structure(full_text: str) -> list[str]:
    """Check Oeconomia structural requirements. Returns list of warnings."""
    warnings = []
    lower = full_text.lower()

    # Abstracts: need both French (Résumé) and English (Abstract)
    has_resume = bool(re.search(r"\brésumé\b", lower))
    has_abstract = bool(re.search(r"\babstract\b", lower))
    if not has_resume:
        warnings.append("MISSING: French abstract (Résumé)")
    if not has_abstract:
        warnings.append("MISSING: English abstract (Abstract)")

    # Keywords in both languages
    has_motscles = bool(re.search(r"mots[- ]cl[ée]s\s*:", lower))
    has_keywords = bool(re.search(r"keywords\s*:", lower))
    if not has_motscles:
        warnings.append("MISSING: French keywords (Mots-clés)")
    if not has_keywords:
        warnings.append("MISSING: English keywords (Keywords)")

    # Bibliography / References
    has_bib = bool(re.search(r"\b(?:bibliography|references)\b", lower))
    if not has_bib:
        warnings.append("MISSING: Bibliography/References section")

    # Conclusion
    has_conclusion = bool(re.search(r"\bconclusion\b", lower))
    if not has_conclusion:
        warnings.append("MISSING: Conclusion section")

    # Section numbering — check for three-level numbering (1.1.1) which is discouraged
    deep_sections = re.findall(r"^\d+\.\d+\.\d+\s", full_text, re.MULTILINE)
    if deep_sections:
        warnings.append(
            f"STYLE: {len(deep_sections)} section(s) with 3+ numbering levels "
            f"(max 2 recommended): {deep_sections[0].strip()!r}..."
        )

    return warnings


def check_ai_tells(full_text: str) -> list[str]:
    """Check for AI-tell blacklisted words and phrases. Returns list of findings."""
    findings = []
    lower = full_text.lower()

    # Blacklisted words
    for word in BLACKLISTED_WORDS:
        # "landscape" is OK in "Global Landscape" (CPI report title)
        if word == "landscape":
            count = len(re.findall(r"\blandscape\b", lower))
            ok_count = len(re.findall(r"global landscape", lower))
            bad_count = count - ok_count
            if bad_count > 0:
                findings.append(f"  BLACKLISTED WORD: '{word}' x{bad_count} (excluding 'Global Landscape')")
        else:
            count = len(re.findall(rf"\b{word}\b", lower))
            if count > 0:
                findings.append(f"  BLACKLISTED WORD: '{word}' x{count}")

    # Blacklisted phrases
    for phrase in BLACKLISTED_PHRASES:
        count = lower.count(phrase)
        if count > 0:
            findings.append(f"  BLACKLISTED PHRASE: '{phrase}' x{count}")

    # Review words (flag but don't fail)
    for word in REVIEW_WORDS:
        count = len(re.findall(rf"\b{word}\b", lower))
        if count > 0:
            findings.append(f"  REVIEW: '{word}' x{count} (OK if statistical sense)")

    # Contrast farming: "not X, but Y"
    contrasts = re.findall(r"not .{3,60}, but ", lower)
    if len(contrasts) > 3:
        findings.append(f"  CONTRAST FARMING: {len(contrasts)} instances (target: ≤3)")
    elif contrasts:
        findings.append(f"  Contrast 'not X, but Y': {len(contrasts)} (OK, target: ≤3)")

    # Em-dash density (3+ per paragraph = too many)
    paragraphs = full_text.split("\n\n")
    heavy_paras = 0
    for para in paragraphs:
        dashes = para.count("—") + para.count("--")
        if dashes >= 3:
            heavy_paras += 1
    if heavy_paras > 0:
        findings.append(f"  EM-DASH HEAVY: {heavy_paras} paragraph(s) with 3+ em-dashes")

    return findings


def main():
    pdf_path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_PDF

    try:
        pdf = pdfplumber.open(pdf_path)
    except FileNotFoundError:
        log.error("Error: %s not found.", pdf_path)
        log.error("Build it first with: make manuscript")
        sys.exit(1)

    pages_text = []
    for page in pdf.pages:
        text = page.extract_text() or ""
        pages_text.append(text)
    pdf.close()

    full_text = "\n".join(pages_text)
    total = count_words(full_text)

    # --- Word counts ---
    log.info("PDF: %s", pdf_path)
    log.info("Pages: %d", len(pages_text))
    log.info("Total words: %s", f"{total:,}")

    # Per-section breakdown
    sections = extract_sections(pages_text)
    if len(sections) > 1:
        log.info("%-50s %7s", "Section", "Words")
        log.info("-" * 58)
        for heading, wc in sections:
            label = heading[:48] if len(heading) > 48 else heading
            log.info("%-50s %7s", label, f"{wc:,}")
        log.info("-" * 58)
        log.info("%-50s %7s", "Total", f"{total:,}")

    # Per-page word counts
    log.info("%-6s %7s", "Page", "Words")
    log.info("-" * 14)
    for i, text in enumerate(pages_text, 1):
        log.info("%-6d %7s", i, f"{count_words(text):,}")

    # --- Editorial checks ---
    log.info("=" * 58)
    log.info("EDITORIAL CHECKS (Oeconomia style)")
    log.info("=" * 58)

    warnings = check_structure(full_text)
    if warnings:
        for w in warnings:
            log.warning("%s", w)
    else:
        log.info("All structural checks passed.")

    # --- AI-tell checks ---
    log.info("AI-TELL CHECKS")
    log.info("-" * 58)
    findings = check_ai_tells(full_text)
    if findings:
        for f in findings:
            log.warning("%s", f)
    else:
        log.info("No AI tells detected.")

    # Exit code: non-zero if blacklisted words/phrases found
    has_blacklisted = any("BLACKLISTED" in f for f in findings)
    if has_blacklisted or warnings:
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_known_args()
    main()
