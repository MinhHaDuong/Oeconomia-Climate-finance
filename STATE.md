# State

Last updated: 2026-03-14

## Manuscript

- ~9,600 words (target ~9,000), 61 bib entries
- 3 figures (emergence, breakpoints, alluvial) + 2 tables (traditions, poles)
- Variable dependencies reduced to 1 (`corpus_total_approx`)
- Phase 2→3 contract documented in manuscript.qmd header comment
- ΔBIC values, cluster counts, language % moved out of prose (belong in companion)

## Corpus

- 28,442 refined works (from 35,046 enriched), 34,081 embeddings cached, 2,342 core
- Citation graph: 775,288 rows, 65% coverage
- Validation: 44-check acceptance test passes (`make corpus-validate`)
- Ecology filter tightened — need extend + filter + figures regen

## Figures & tables

- Fig 1 (bars): self-explaining legend, grayscale, 120mm, starts 1992
- Fig 2 (composition): relocated to §3.4 (thematic decomposition argument)
- Fig S1 (traditions): co-citation network, color, Electronic Supplement — PR #88 open
- Table 2 (poles): efficiency vs accountability terms — done
- Table 1 (traditions): caption updated; §1.5 cites co-citation evidence (Q=0.68)

## Blockers

- Table 1 pending: co-citation communities don't cleanly separate pre-2007 traditions
- Corpus regen needed after ecology filter tightening

## Active PRs

- #99: docs — reasoning levels for git messages

## Next priorities

1. Human proofread of full manuscript
2. Review and merge PR #99
3. Corpus update (enrichment pipeline)
4. Regen period detection curves + terms table for §2.5
5. Move ΔBIC details + cluster counts to companion paper
