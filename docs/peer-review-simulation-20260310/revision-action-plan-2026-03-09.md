# Revision Action Plan — Based on Simulated Peer Review (2026-03-09)

Handoff document for the next revision agent. All three reviewers recommend **major revision** but consider the paper publishable after revision.

## Convergent Diagnoses

| Issue | R1 | R2 | R3 | Priority |
|-------|:--:|:--:|:--:|:--------:|
| Theory decorative / separated from narrative | x | | x | **HIGH** |
| "Economists as architects" overstated | x | x | | **HIGH** |
| Performativity used imprecisely | x | | x | **HIGH** |
| Computational method needs reflexive discussion | x | | x | MEDIUM |
| Missing institutions (GCF, MDBs, IDFC) | | x | | MEDIUM |
| Efficiency/accountability binary oversimplifies | x | x | x | MEDIUM |
| Governance-by-indicators literature missing | | | x | MEDIUM |
| "No break at Paris" needs qualification | | x | | MEDIUM |
| Prosopographic depth insufficient for HET | x | | | MEDIUM |
| Francophone/Global South coverage thin | x | x | x | LOW |

## Recommended Revision Strategy

### Structural changes (highest impact)

1. **Integrate theory into Sections 1–3** rather than concentrating in Section 4. Use commensuration and performativity as analytical lenses *within* the narrative. Reduce Section 4 to a shorter synthesis.

2. **Sharpen performativity claim:** Choose Callon's "formatting" sense. Demonstrate with specific devices (Rio markers as formatting devices, $100bn target as market-formatting commitment). Drop or clarify the "speech act" framing.

3. **Reduce four lenses to two or three.** Commensuration and performativity are load-bearing; economization overlaps with commensuration; boundary work could be replaced by boundary objects (Star & Griesemer). Consider Latour's "centres of calculation" as a unifying alternative.

### Content additions

4. **Add GCF, MDB joint methodology, and CPI** as alternative measurement regimes (1-2 paragraphs in Section 3) — strengthens the "competing commensurations" argument.

5. **Qualify "no break at Paris"** — distinguish semantic continuity from institutional change. Acknowledge ETF and TCFD as governance shifts even if vocabulary is stable.

6. **Deepen one episode** (Rio marker design OR AGF methodology) with primary-source detail — at least one page of close institutional history.

7. **Acknowledge developing country negotiators and NGOs** as co-architects, not just critics. The demand for measurability came from G77+China, not just OECD supply.

8. **Add reflexive paragraph** on computational method as itself an act of commensuration (Section 1.5 or methodological note).

### Literature to add

| Reference | Why | Where |
|-----------|-----|-------|
| Merry (2016) *The Seductions of Quantification* | Indicators constitute objects | Section 4 / throughout |
| Rottenburg et al. (2015) *The World of Indicators* | Governance by numbers | Section 4 |
| Davis et al. (2012) *Governance by Indicators* | Power of measurement | Section 4 |
| Star & Griesemer (1989) boundary objects | Better fit than Gieryn alone | Section 4.4 |
| Hynes & Scott (2013) ODA measurement history | DAC conventions genealogy | Section 1.2 |
| Severino & Ray (2009) end of ODA | Development finance categories | Section 1.2 |
| Weikmans & Roberts (2019) additionality review | Updates Stadelmann | Section 3.2 |
| Latour (1987) centres of calculation | Unifying framework option | Section 4 |
| Miller & Rose (1990) governmentality | If keeping "governable object" title | Section 4 |
| Canfin & Grandjean (2015), Aglietta & Espagne (2016) | Francophone coverage | Section 2.4 |

### Minor fixes

9. Explain Negishi weights genealogy for Œconomia readers.
10. Comment on "Sustainability" journal in Table 1 (MDPI publication model vs intellectual influence).
11. Strengthen Kaul (2003, 2017) engagement on global public goods.
12. Consider whether "governable object" in title needs Foucauldian grounding or rewording.
13. Note CDM Executive Board's role in additionality framework (Section 1.3).
14. Loss-and-damage in Section 3.3: emphasise it challenges mitigation/adaptation binary, not just ODA categories.

### Word count management

Current: ~9,400 words. Additions above could add ~1,500 words. To stay within journal norms:
- Condensing Section 4 (from 4 lenses to 2-3, integrated into narrative) should save ~500 words.
- Tightening Section 1.1 (the externality/Pigou/Coase story is well-known for Œconomia readers) could save ~300 words.
- Corpus evidence subsections can be compressed if key figures are referenced more efficiently: ~200 words.
- Net: manageable within 10,000-word target.

## Verification after revision

```bash
# Build clean
make clean && make manuscript

# AI-tell sweep (targets: 0 blacklisted words)
grep -ciE 'delve|nuanced|multifaceted|pivotal|tapestry|intricate|meticulous|vibrant|showcasing|underscores' content/manuscript.qmd

# Em-dash heavy paragraphs (target: 0)
grep -cP '---.*---.*---' content/manuscript.qmd

# Contrast farming (target: ≤3)
grep -cP 'not .{3,60}, but ' content/manuscript.qmd

# Word count
wc -w content/manuscript.qmd

# Bibliography check — all new references exist
grep -oP '@\w+' content/manuscript.qmd | sort -u > /tmp/cited.txt
grep -oP '^\s*@\w+\{(\w+),' content/bibliography/main.bib | sed 's/.*{//' | sed 's/,//' | sort -u > /tmp/bibed.txt
comm -23 /tmp/cited.txt /tmp/bibed.txt  # should be empty
```

## Source files

- Referee reports: `docs/peer-review-simulation-2026-03-09.md`
- This action plan: `docs/revision-action-plan-2026-03-09.md`
- Manuscript: `content/manuscript.qmd`
- Bibliography: `content/bibliography/main.bib`
- Style guide: `.agent/guidelines/oeconomia-style.md`
- Writing guidelines: `AGENTS.md`
