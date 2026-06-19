# Analysis reproducibility archive

Companion to: Ha-Duong M. (2026) "Inventing Climate Finance", Oeconomia.

This archive verifies that all figures and tables in the manuscript are
reproducible from the Phase 1 corpus data (refined_works.csv).

## Prerequisites

- [uv](https://docs.astral.sh/uv/) (Python package manager), **or**
- [Podman](https://podman.io/) or Docker

## Usage

```bash
tar xzf climate-finance-analysis.tar.gz
cd climate-finance-analysis

# Option A: native (requires uv)
uv sync              # install Python dependencies (pinned in uv.lock)
make corpus-handoff  # (optional) convert CSV to Feather for ~30× faster reads
make                 # rebuild all figures and tables from data
make verify          # check outputs match expected checksums

# Option B: container (requires podman or docker, no other install needed)
podman build -t climate-finance .
podman run climate-finance

# Cleanup: remove container and image from local storage
podman rm -a && podman rmi climate-finance && podman system prune -f
```

## Contents

| Path | Description |
|------|-------------|
| `data/catalogs/` | Phase 1 corpus data (refined works + embeddings) |
| `scripts/` | Analysis scripts (deterministic, no API calls) |
| `config/` | Analysis configuration (periods, thresholds) |
| `expected_outputs.md5` | Checksums of expected outputs |
| `Makefile` | Build and verify targets |
| `pyproject.toml`, `uv.lock` | Pinned Python dependencies |
| `Dockerfile` | OCI container build (Podman/Docker) |

## Verification

`make verify` runs `md5sum -c expected_outputs.md5`, checking that every
rebuilt figure and table is bitwise identical to the author's outputs.
All outputs are deterministic (`PYTHONHASHSEED=0`, `SOURCE_DATE_EPOCH=0`).
