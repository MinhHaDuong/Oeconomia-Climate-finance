# mk/render.mk — Phase 3: Render (Quarto → PDF/DOCX)

manuscript: output/content/manuscript.pdf output/content/manuscript.docx

papers: check-corpus output/content/technical-report.pdf output/content/data-paper.pdf output/content/companion-paper.pdf

output/content/manuscript.pdf: $(SRC) $(BIB) $(CSL) $(MANUSCRIPT_FIGS) $(PROJECT_INCLUDES) content/manuscript-vars.yml
	quarto render $< --to pdf

output/content/manuscript.docx: $(SRC) $(BIB) $(CSL) $(MANUSCRIPT_FIGS) $(PROJECT_INCLUDES) content/manuscript-vars.yml
	quarto render $< --to docx

output/content/technical-report.pdf: content/technical-report.qmd $(PROJECT_INCLUDES) $(BIB) content/technical-report-vars.yml $(TECHREP_FIGS) $(COMPANION_FIGS) .lexical_tfidf.stamp
	quarto render $< --to pdf

output/content/data-paper.pdf: content/data-paper.qmd $(PROJECT_INCLUDES) $(BIB) content/data-paper-vars.yml
	quarto render $< --to pdf

output/content/companion-paper.pdf: content/companion-paper.qmd $(PROJECT_INCLUDES) $(BIB) content/companion-paper-vars.yml
	quarto render $< --to pdf
