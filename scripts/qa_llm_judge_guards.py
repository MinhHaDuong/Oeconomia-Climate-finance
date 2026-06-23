"""LLM-judge reduction guards (ticket 0148).

A *reduction* is any LLM operation that rewrites prose to be shorter or cleaner
(descaffold, voiceprint, abstract realign) or that condenses it into a verdict.
Such operations can silently fabricate: pad the length, invent a number, or
smuggle a verdict the source never made (in the AEDIST run-1 case the engine
added a "does little better" clause that no source supported). These guards are
the mechanical checks an LLM-judge output must pass before it is trusted —
ported from the AEDIST reduction-guard spec in
`docs/editorial-skills-design.md`:

  1. output words <= input words        — a reduction must not grow;
  2. em-dash count == 0 in the output   — the AI-tell punctuation;
  3. every number in the output appears verbatim in the input — no invented
     figures (a single hallucinated `$300 billion` corrupts the record);
  4. no LLMism-list word introduced     — the lexical signature of a smuggled
     summary verdict.

Each guard is a pure function; :func:`check_reduction` runs them all and returns
a :class:`GuardReport`. As a CLI it compares an ``--input`` prose file against a
``--reduced`` output and exits non-zero if any guard fails.

This is a *review-time* QA aid, not a pipeline data transform: it produces no
committed artifact, only a pass/fail report (mirrors `qa_word_count.py`).
"""

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from utils import get_logger

log = get_logger("qa_llm_judge_guards")

# A "word": a maximal run of letters/digits (apostrophes kept inside).
_WORD_RE = re.compile(r"\w[\w'’-]*", re.UNICODE)
# A "number": an integer or decimal, with optional thousands separators, so
# "2009", "100", "2.5", and "1,000" are each one token. Surrounding $ and % are
# not part of the token — they are compared on the bare digits.
_NUMBER_RE = re.compile(r"\d[\d,.]*\d|\d")


_FRONTMATTER_RE = re.compile(r"\A---\n.*?\n---\n", re.DOTALL)


def strip_front_matter(text: str) -> str:
    """Drop a leading YAML front-matter block (so its ``---`` fences are not
    miscounted as em dashes when a raw ``.qmd`` is passed to the CLI)."""
    return _FRONTMATTER_RE.sub("", text, count=1)


def word_count(text: str) -> int:
    """Number of word tokens in ``text``."""
    return len(_WORD_RE.findall(text))


def count_em_dashes(text: str) -> int:
    """Em dashes: literal U+2014 plus the Markdown ``---`` ligature."""
    return text.count("—") + text.count("---")


def _normalize_number(tok: str) -> str:
    """Drop thousands separators so ``1,000`` and ``1000`` compare equal."""
    return tok.replace(",", "")


def extract_numbers(text: str) -> set[str]:
    """Set of normalized numeric tokens in ``text``."""
    return {_normalize_number(m.group(0)) for m in _NUMBER_RE.finditer(text)}


def invented_numbers(input_text: str, reduced_text: str) -> list[str]:
    """Numbers present in the reduction but absent from the source."""
    src = extract_numbers(input_text)
    return sorted(extract_numbers(reduced_text) - src)


def introduced_llmisms(reduced_text: str, llmisms: list[str]) -> list[str]:
    """LLMism-list words present in the reduction (whole-word, case-insensitive).

    Source-agnostic by design: any LLMism in the reduction is flagged, even if
    the source already contained it. A reduction is meant to *clean* prose, so
    carrying a tell forward is itself a defect.
    """
    low = reduced_text.lower()
    return [w for w in llmisms if re.search(rf"\b{re.escape(w.lower())}\b", low)]


def load_llmisms(ai_tells_path: Path) -> list[str]:
    """Blacklisted words from config/ai-tells.yml (the single source).

    The ``conditional_words`` (e.g. ``robust``, ``landscape``) are folded in
    *unconditionally* — stricter than the /review-pr-prose auditor, which honours
    their ``ok_when`` context. A reduction has no licence to introduce them, so
    the conservative reading is intentional.
    """
    with open(ai_tells_path, encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    words = list(data.get("blacklisted_words", []))
    words += [c["word"] for c in data.get("conditional_words", [])]
    return words


@dataclass
class GuardReport:
    """Outcome of the four reduction guards for one (input, reduced) pair."""

    input_words: int
    reduced_words: int
    em_dashes: int
    invented_numbers: list[str] = field(default_factory=list)
    introduced_llmisms: list[str] = field(default_factory=list)

    @property
    def word_reduction_ok(self) -> bool:
        return self.reduced_words <= self.input_words

    @property
    def em_dash_ok(self) -> bool:
        return self.em_dashes == 0

    @property
    def ok(self) -> bool:
        return (
            self.word_reduction_ok
            and self.em_dash_ok
            and not self.invented_numbers
            and not self.introduced_llmisms
        )

    def render(self) -> str:
        def mark(passed: bool) -> str:
            return "PASS" if passed else "FAIL"

        lines = [
            f"[{mark(self.word_reduction_ok)}] word reduction: "
            f"{self.reduced_words} reduced <= {self.input_words} input",
            f"[{mark(self.em_dash_ok)}] em dashes in output: {self.em_dashes} (must be 0)",
            f"[{mark(not self.invented_numbers)}] invented numbers: "
            f"{self.invented_numbers or 'none'}",
            f"[{mark(not self.introduced_llmisms)}] introduced LLMisms: "
            f"{self.introduced_llmisms or 'none'}",
            f"=> {'OK' if self.ok else 'GUARD FAILURE'}",
        ]
        return "\n".join(lines)


def check_reduction(
    input_text: str, reduced_text: str, llmisms: list[str]
) -> GuardReport:
    """Run all four reduction guards over an (input, reduced) prose pair."""
    return GuardReport(
        input_words=word_count(input_text),
        reduced_words=word_count(reduced_text),
        em_dashes=count_em_dashes(reduced_text),
        invented_numbers=invented_numbers(input_text, reduced_text),
        introduced_llmisms=introduced_llmisms(reduced_text, llmisms),
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    repo_root = Path(__file__).resolve().parent.parent
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--input", type=Path, required=True, help="Source prose file.")
    p.add_argument("--reduced", type=Path, required=True, help="LLM-reduced output file.")
    p.add_argument(
        "--ai-tells",
        type=Path,
        default=repo_root / "config" / "ai-tells.yml",
        help="ai-tells.yml supplying the LLMism wordlist.",
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    llmisms = load_llmisms(args.ai_tells)
    report = check_reduction(
        strip_front_matter(args.input.read_text(encoding="utf-8")),
        strip_front_matter(args.reduced.read_text(encoding="utf-8")),
        llmisms,
    )
    log.info("%s", report.render())
    return 0 if report.ok else 1


if __name__ == "__main__":
    sys.exit(main())
