"""Compute one divergence method.

Thin dispatcher that loads data, calls the right method function from the
private _divergence_{semantic,lexical,citation} modules, validates the
output against DivergenceSchema, and writes a single CSV.

Usage:
    python3 scripts/compute_divergence.py --method S1_MMD \
        --output content/tables/tab_div_S1_MMD.csv

    # Smoke fixture:
    CLIMATE_FINANCE_DATA=tests/fixtures/smoke \
        python3 scripts/compute_divergence.py --method S2_energy \
        --output /tmp/tab_div_S2_energy.csv
"""

import importlib
import os

from pipeline_loaders import load_analysis_config
from schemas import C2STDivergenceSchema, DivergenceSchema
from script_io_args import parse_io_args, validate_io
from utils import get_logger

log = get_logger("compute_divergence")

# Registry: method_name -> (module, function_name, channel, needs_embeddings, needs_citations)
METHODS = {
    "S1_MMD": ("_divergence_semantic", "compute_s1_mmd", "semantic", True, False),
    "S2_energy": ("_divergence_semantic", "compute_s2_energy", "semantic", True, False),
    "S3_sliced_wasserstein": (
        "_divergence_semantic",
        "compute_s3_wasserstein",
        "semantic",
        True,
        False,
    ),
    "S4_frechet": (
        "_divergence_semantic",
        "compute_s4_frechet",
        "semantic",
        True,
        False,
    ),
    "L1": ("_divergence_lexical", "compute_l1_js", "lexical", False, False),
    "L2": ("_divergence_lexical", "compute_l2_novelty", "lexical", False, False),
    "L3": ("_divergence_lexical", "compute_l3_bursts", "lexical", False, False),
    "G1_pagerank": (
        "_citation_methods",
        "compute_g1_pagerank",
        "citation",
        False,
        True,
    ),
    "G2_spectral": (
        "_citation_methods",
        "compute_g2_spectral",
        "citation",
        False,
        True,
    ),
    "G3_coupling_age": (
        "_citation_methods",
        "compute_g3_age_shift",
        "citation",
        False,
        True,
    ),
    "G4_cross_tradition": (
        "_citation_methods",
        "compute_g4_cross_trad",
        "citation",
        False,
        True,
    ),
    "G5_pref_attachment": (
        "_citation_methods",
        "compute_g5_pa_exponent",
        "citation",
        False,
        True,
    ),
    "G6_entropy": (
        "_citation_methods",
        "compute_g6_entropy",
        "citation",
        False,
        True,
    ),
    "G7_disruption": (
        "_citation_methods",
        "compute_g7_disruption",
        "citation",
        False,
        True,
    ),
    "G8_betweenness": (
        "_citation_methods",
        "compute_g8_betweenness",
        "citation",
        False,
        True,
    ),
    "G9_community": (
        "_divergence_community",
        "compute_community_divergence",
        "citation",
        False,
        True,
    ),
    "C2ST_embedding": (
        "_divergence_c2st",
        "compute_c2st_embedding",
        "semantic",
        True,
        False,
    ),
    "C2ST_lexical": (
        "_divergence_c2st",
        "compute_c2st_lexical",
        "lexical",
        False,
        False,
    ),
}


def main():
    io_args, extra = parse_io_args()
    validate_io(output=io_args.output)

    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--method", required=True, choices=METHODS.keys())
    parser.add_argument(
        "--no-equal-n",
        dest="equal_n",
        action="store_false",
        default=None,
        help="Disable equal-n subsampling (override config equal_n: true)",
    )
    args = parser.parse_args(extra)

    cfg = load_analysis_config()

    # CLI override: --no-equal-n sets cfg["divergence"]["equal_n"] = False,
    # propagating to all private modules that read div_cfg.get("equal_n").
    if args.equal_n is not None:
        cfg["divergence"]["equal_n"] = args.equal_n
    module_name, func_name, channel, needs_emb, needs_cit = METHODS[args.method]

    # Lazy import
    mod = importlib.import_module(module_name)
    func = getattr(mod, func_name)

    # Load data based on what the method needs
    if needs_emb:
        from _divergence_semantic import load_semantic_data

        df, emb = load_semantic_data(io_args.input)
        result = func(df, emb, cfg)
    elif needs_cit:
        from _divergence_citation import load_citation_data

        works, citations, internal_edges = load_citation_data(io_args.input)
        result = func(works, citations, internal_edges, cfg)
    else:
        from _divergence_lexical import load_lexical_data

        df = load_lexical_data(io_args.input)
        result = func(df, cfg)

    result["channel"] = channel

    # Validate contract — C2ST methods carry extra CV-variance columns
    # (ticket 0068) and use a distinct strict schema.
    if args.method.startswith("C2ST_"):
        C2STDivergenceSchema.validate(result)
    else:
        DivergenceSchema.validate(result)

    # Ensure output directory exists
    out_dir = os.path.dirname(io_args.output)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    result.to_csv(io_args.output, index=False)
    log.info("Saved %s (%d rows) -> %s", args.method, len(result), io_args.output)


if __name__ == "__main__":
    main()
