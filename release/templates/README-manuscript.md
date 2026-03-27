# Manuscript reproducibility archive

Companion to: Ha-Duong M. (2026) "Inventing Climate Finance", Oeconomia.

This archive verifies that the manuscript PDF renders from pre-built
figures and content. No Python, no data, no scripts required.

## Prerequisites

- [Quarto](https://quarto.org/) >= 1.4
- XeLaTeX (via TeX Live or Quarto's bundled TinyTeX)

## Usage

```bash
tar xzf climate-finance-manuscript.tar.gz
cd climate-finance-manuscript
make             # render manuscript PDF
make verify      # check inputs match + compare PDF to shipped reference
```

## Contents

| Path | Description |
|------|-------------|
| `content/` | Manuscript source (.qmd), figures, tables, bibliography |
| `expected-manuscript.pdf` | Pre-built reference PDF for comparison |
| `checksums.md5` | MD5 checksums of all input files |
| `TOOLCHAIN.txt` | Quarto and xdvipdfmx versions used to build the shipped PDF |
| `Makefile` | Build and verify targets |
| `_quarto.yml` | Quarto project configuration |

## Verification

`make verify` checks two things:

1. **Inputs** (deterministic): `md5sum -c checksums.md5` must pass.
   All input files must be bitwise identical to the author's sources.

2. **Output PDF** (toolchain-dependent): compared against
   `expected-manuscript.pdf`. If your Quarto/XeLaTeX version differs
   from the one recorded in `TOOLCHAIN.txt`, the PDF binaries will
   differ even though the content is identical. This is reported as
   a warning, not a failure.
