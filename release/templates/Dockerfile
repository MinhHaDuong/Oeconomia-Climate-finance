# Reproducibility container for the climate finance corpus pipeline
#
# Builds the complete corpus from source APIs, producing:
#   data/catalogs/refined_works.csv, embeddings.npz, citations.csv, corpus_audit.csv
#
# Usage:
#   docker build -t climate-finance-corpus .
#   docker run -v $(pwd)/output:/app/data climate-finance-corpus make corpus
#
# Note: corpus building requires internet access for API calls (OpenAlex, ISTEX,
# World Bank, Crossref). Full build takes 4-6 hours depending on network speed
# and API rate limits. bibCNRS and SciSpace exports are included pre-harvested.

FROM python:3.12-slim

# System deps for sentence-transformers (torch CPU) and PDF extraction
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Copy dependency specification first (cache layer)
COPY pyproject.toml uv.lock ./

# Install dependencies (CPU-only torch for reproducibility)
RUN uv sync --group corpus --extra cpu --frozen

# Copy project files
COPY . .

# Default .env pointing data to local directory
RUN echo 'CLIMATE_FINANCE_DATA=data' > .env

# Pre-harvested exports (bibCNRS, SciSpace) are in data/exports/
# API pool data will be fetched during corpus build

ENV PYTHONHASHSEED=0
ENV SOURCE_DATE_EPOCH=0

CMD ["make", "corpus"]
