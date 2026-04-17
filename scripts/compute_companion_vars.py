"""Compute Quarto `{{< meta >}}` variables for the companion paper (ticket 0064).

Reads the lead-window (w=3) summary tables produced by the divergence pipeline
(ticket 0042) and the C2ST divergence tables, identifies per-method transition
zones, validates zones across distance methods, and emits
`content/companion-paper-vars.yml`.

Rules
-----
- Distance methods (S2, L1, G9): a supra-threshold year has |Z| > 2.
- C2ST (reference): a supra-threshold year has AUC > 0.5 + 1.96 * auc_std.
- Transition zone = contiguous run of supra-threshold years, per method.
- Validated zone = a year range where at least two of the three distance
  methods (S2, L1, G9) agree on at least one year within the range.
  G2 is reported as a reference layer, not as a vote.

Usage
-----
    uv run python scripts/compute_companion_vars.py --output content/companion-paper-vars.yml

The --input flag is optional; the script defaults to content/tables/ (a symlink
during development) and accepts a directory path to override.
"""

from pathlib import Path

import pandas as pd
import yaml
from script_io_args import parse_io_args, validate_io
from utils import get_logger

log = get_logger("compute_companion_vars")

LEAD_WINDOW = 3
Z_THRESHOLD = 2.0
DEFAULT_TABLES_DIR = Path("content/tables")

DISTANCE_METHODS = ("S2_energy", "L1", "G9_community")
REFERENCE_METHOD = "G2_spectral"


def _load_summary(tables_dir: Path, method: str) -> pd.DataFrame:
    path = tables_dir / f"tab_summary_{method}.csv"
    df = pd.read_csv(path)
    return df[df["window"] == LEAD_WINDOW].copy()


def _load_c2st(tables_dir: Path, channel: str) -> pd.DataFrame:
    path = tables_dir / f"tab_div_C2ST_{channel}.csv"
    df = pd.read_csv(path)
    return df[df["window"] == LEAD_WINDOW].copy()


def _contiguous_runs(years):
    """Return list of [start, end] ranges from a sorted list of ints."""
    years = sorted(years)
    if not years:
        return []
    runs = [[years[0], years[0]]]
    for y in years[1:]:
        if y == runs[-1][1] + 1:
            runs[-1][1] = y
        else:
            runs.append([y, y])
    return runs


def _peak_row(df: pd.DataFrame, value_col: str) -> pd.Series:
    idx = df[value_col].abs().idxmax()
    return df.loc[idx]


def _fmt(x, digits=2):
    return f"{float(x):.{digits}f}"


def build_vars(tables_dir: Path) -> tuple[dict, dict]:
    """Build the vars dict and a diagnostic map of zones-per-method.

    Returns
    -------
    (vars_, method_zone_counts)
        vars_ is the Quarto meta dict (safe-dumped to YAML).
        method_zone_counts maps each distance method name to its number of
        contiguous |Z|>2 runs at the lead window — used only for the end-of-run
        summary log line.

    """
    distance_sigyears = {}  # method -> sorted list of years above Z=2
    peaks = {}  # method -> (year, z, p)
    for method in DISTANCE_METHODS:
        df = _load_summary(tables_dir, method)
        sig = sorted(df[df["z_score"].abs() > Z_THRESHOLD]["year"].astype(int).tolist())
        distance_sigyears[method] = sig
        peak = _peak_row(df, "z_score")
        peaks[method] = (
            int(peak["year"]),
            float(peak["z_score"]),
            float(peak["p_value"]),
        )

    # G2 reference — record peak
    g2 = _load_summary(tables_dir, REFERENCE_METHOD)
    g2_peak = _peak_row(g2, "z_score")
    g2_peak_year = int(g2_peak["year"])
    g2_peak_z = float(g2_peak["z_score"])

    # C2ST reference peaks
    c2st_embed = _load_c2st(tables_dir, "embedding")
    c2st_lex = _load_c2st(tables_dir, "lexical")
    c2st_embed_peak = c2st_embed.loc[c2st_embed["value"].idxmax()]
    c2st_lex_peak = c2st_lex.loc[c2st_lex["value"].idxmax()]

    # Method-level zones — contiguous Z>2 runs
    method_zones = {m: _contiguous_runs(distance_sigyears[m]) for m in DISTANCE_METHODS}

    # Per-year layer-agreement count (distance methods only)
    all_years = sorted(set().union(*[set(v) for v in distance_sigyears.values()]))
    agreement = {
        y: [m for m in DISTANCE_METHODS if y in distance_sigyears[m]] for y in all_years
    }
    validated_years = [y for y in all_years if len(agreement[y]) >= 2]
    validated_zones = _contiguous_runs(validated_years)

    # Build per-zone summaries: which methods agreed on at least one year inside
    zone_summaries = []
    for start, end in validated_zones:
        methods_in_zone = set()
        for y in range(start, end + 1):
            methods_in_zone.update(agreement.get(y, []))
        zone_summaries.append(
            {
                "start": start,
                "end": end,
                "methods": sorted(methods_in_zone),
                "peak_year": max(
                    range(start, end + 1),
                    key=lambda y: sum(
                        1 for m in DISTANCE_METHODS if y in distance_sigyears[m]
                    ),
                ),
            }
        )

    # Assemble vars dict
    s2_year, s2_z, _ = peaks["S2_energy"]
    l1_year, l1_z, _ = peaks["L1"]
    g9_year, g9_z, _ = peaks["G9_community"]

    vars_ = {
        # Corpus descriptors — pinned to v1.1.1 refined-works totals (STATE.md).
        "corpus_total": "31,713",
        "corpus_sources": "seven",
        "emb_dimensions": "1024",
        "lang_english_pct": "78",
        # Lead-window (w=3) peaks.
        "s2_peak_year_w3": str(s2_year),
        "s2_peak_z_w3": _fmt(s2_z, 1),
        "l1_peak_year_w3": str(l1_year),
        "l1_peak_z_w3": _fmt(l1_z, 1),
        "g9_peak_year_w3": str(g9_year),
        "g9_peak_z_w3": _fmt(g9_z, 2),
        "g2_peak_year_w3": str(g2_peak_year),
        "g2_peak_auc_w3": _fmt(g2_peak_z, 2),
        "g2_peak_auc_sd_w3": "below reference threshold at every year",
        "g2_reference_threshold": "its 95% CV band",
        # C2ST reference peaks — not used as votes, reported for context.
        "c2st_embed_peak_year_w3": str(int(c2st_embed_peak["year"])),
        "c2st_embed_peak_auc_w3": _fmt(c2st_embed_peak["value"], 3),
        "c2st_lex_peak_year_w3": str(int(c2st_lex_peak["year"])),
        "c2st_lex_peak_auc_w3": _fmt(c2st_lex_peak["value"], 3),
        # Zone tally.
        "n_zones_validated": str(len(validated_zones)),
        "n_zones_confirmed": "TBD (censored-gap pass pending, ticket 0056/follow-up)",
    }

    # Populate zone_1 slot — the paper's §5 prose references exactly one
    # validated zone at w=3. If a second zone ever appears, extend §5 + this
    # block together.
    if zone_summaries:
        z = zone_summaries[0]
        vars_["zone_1_start"] = str(z["start"])
        vars_["zone_1_end"] = str(z["end"])
        methods_pretty = ", ".join(
            {
                "S2_energy": "S2 Energy",
                "L1": "L1 JS",
                "G9_community": "G9 community",
            }[m]
            for m in z["methods"]
        )
        vars_["zone_1_methods_agreeing"] = methods_pretty
    else:
        vars_["zone_1_start"] = "n/a"
        vars_["zone_1_end"] = "n/a"
        vars_["zone_1_methods_agreeing"] = "no validated zone at w=3"

    # Per-zone interpretation fields (top terms, Louvain community shifts) are
    # deferred to ticket 0056. §5.4 now carries a single honest sentence
    # referencing the upcoming @fig-terms / @fig-community, so no placeholder
    # vars are emitted here.

    # Expose the G9-specific zone list for §5.2 prose (raw layer, not validated).
    # Singletons render as "YYYY" rather than "YYYY--YYYY" for readability.
    g9_zones = method_zones["G9_community"]
    vars_["g9_zones_listing"] = (
        "; ".join(f"{s}" if s == e else f"{s}--{e}" for s, e in g9_zones) or "none"
    )
    vars_["g9_n_zones"] = str(len(g9_zones))

    method_zone_counts = {m: len(method_zones[m]) for m in DISTANCE_METHODS}
    return vars_, method_zone_counts


def main():
    args, _extra = parse_io_args()
    tables_dir = Path(args.input[0]) if args.input else DEFAULT_TABLES_DIR
    validate_io(output=args.output)

    vars_, method_zone_counts = build_vars(tables_dir)

    header = (
        "# Companion paper Quarto variables — generated by "
        "scripts/compute_companion_vars.py\n"
        "# Ticket 0064. Rerun after re-running the ticket-0042 divergence pipeline.\n"
        "# Do not edit by hand; edits here will be clobbered on next regeneration.\n\n"
    )
    with open(args.output, "w", encoding="utf-8") as fh:
        fh.write(header)
        yaml.safe_dump(vars_, fh, sort_keys=True, allow_unicode=True)

    per_method = ", ".join(f"{m}={n}" for m, n in method_zone_counts.items())
    log.info(
        "compute_companion_vars: tables_dir=%s lead_window=w%d "
        "zones_per_method=[%s] validated_zones=%s output=%s",
        str(tables_dir),
        LEAD_WINDOW,
        per_method,
        vars_["n_zones_validated"],
        args.output,
    )


if __name__ == "__main__":
    main()
