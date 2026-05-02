# venues.mk — Venue concentration analysis (ticket 0073)
#
# Include from the main Makefile:  include venues.mk
#
# Targets:
#   venue-concentration-table  Compute HHI + Shannon entropy per year
#   venue-concentration-figure Plot dual-panel concentration figure
#   venue-concentration        Both table and figure

# ── Paths ─────────────────────────────────────────────────────────────────

VENUE_TABLE := content/tables/tab_venue_concentration.csv
VENUE_FIG   := content/figures/fig_venue_concentration.png

# ── Phony targets ─────────────────────────────────────────────────────────

.PHONY: venue-concentration venue-concentration-table venue-concentration-figure

venue-concentration: venue-concentration-table venue-concentration-figure
venue-concentration-table: $(VENUE_TABLE)
venue-concentration-figure: $(VENUE_FIG)

# ── Table ─────────────────────────────────────────────────────────────────

$(VENUE_TABLE): scripts/compute_venue_concentration.py scripts/summarize_core_venues.py \
		scripts/schemas.py scripts/utils.py $(REFINED)
	$(UV_RUN) python $< --output $@

# ── Figure ────────────────────────────────────────────────────────────────

$(VENUE_FIG): scripts/plot_venue_concentration.py scripts/plot_style.py scripts/utils.py \
		$(VENUE_TABLE) content/tables/tab_breakpoints.csv
	$(UV_RUN) python $< --output $@ --input $(VENUE_TABLE) content/tables/tab_breakpoints.csv
