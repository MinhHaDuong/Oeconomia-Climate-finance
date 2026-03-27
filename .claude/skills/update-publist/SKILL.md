---
name: update-publist
description: Add or update entries in the author's list of scientific productions (Ha-Duong.bib) and archive on HAL
disable-model-invocation: false
user-invocable: true
---

# Update list of scientific productions

Update the author's BibTeX database and archive on HAL. Covers all scientific productions, including unpublished work.

## Source of truth

- **BibTeX file**: `~/CNRS/html/src/Ha-Duong.bib`
- **Build**: `cd ~/CNRS/html/src && make` (generates `index.html`)
- **Deploy**: `cd ~/CNRS/html && make sync` (FTP to ouvaton.coop)
- Not a git repo — edits are direct.

## BibTeX entry type rules

| Status | BibTeX type | Notes |
|--------|-------------|-------|
| Peer-reviewed and accepted | `@article` | Include `journaltitle`, `doi` |
| Under review / preprint | `@techreport` | `type` = "Preprint, under review at {Journal}". NO `institution` field |
| CIRED Working Paper series | `@techreport` | Only these get `institution = {CIRED}` |
| Conference presentation | `@inproceedings` | Include `booktitle`, `location`, `date` |
| Dataset | `@misc` | `howpublished = {Zenodo}`, include `doi` |
| Book | `@book` | Include `publisher`, `isbn` |

## Common fields

- `eprint` = full HAL URL (e.g., `https://hal.science/hal-05558422`)
- `doi` = DOI without URL prefix (e.g., `10.5281/zenodo.19097045`)
- `file` = PDF filename in `~/CNRS/html/files/` (optional, for local download link)
- `date` = ISO format (`2026-03-18`)

## HAL deposit via SWORD

Every scientific production must be archived on HAL. This is not optional.

### Pre-upload PDF review (GATE)

Before uploading, **review the PDF with vision** (read every page) and check against HAL deposit guidelines:
- Author name must appear in the document (no "[Anonymous]" or anonymized versions)
- Affiliations must be present and match HAL metadata
- No placeholder text, draft watermarks that contradict the deposit status
- File is complete (all pages, figures, tables render correctly)
- No embedded sensitive data (API keys, personal emails beyond correspondence address)

Reference: HAL deposit guidelines at https://doc.hal.science/en/deposit/

Only proceed to upload after the review passes.

### Build metadata and upload

1. **Build AOfr/TEI metadata XML** with:
   - Author: Minh Ha-Duong, ORCID 0000-0001-9988-2100, CIRED (struct-1002424)
   - Stamps: CIRED, CNRS
   - File reference: `<ref type="file" target="paper.pdf" subtype="author" n="1"/>`
   - HAL domains: `shs.eco`, `shs.hisphilso` (adjust per paper)
   - Look up `halJournalId` via: `https://api.archives-ouvertes.fr/ref/journal/?q=title_t:{name}&fl=docid,title_s,valid_s&wt=json`

2. **Package**: ZIP with `meta.xml` + PDF

3. **Dry run first** (`-H "X-test: 1"`), then real deposit:
   ```
   curl -u "$HAL_ID:$HAL_PASSWORD" -X POST \
     -H "Packaging: http://purl.org/net/sword-types/AOfr" \
     -H "Content-Type: application/zip" \
     -H "Content-Disposition: attachment; filename=meta.xml" \
     --data-binary @depot.zip \
     https://api.archives-ouvertes.fr/sword/hal
   ```

4. **Update** existing deposit: same but `PUT` to `.../sword/{hal-id}`

5. Credentials from `.env`: `HAL_ID`, `HAL_PASSWORD`

## Steps

1. Read `~/CNRS/html/src/Ha-Duong.bib` to see current entries.
2. Determine what to add/update (from conversation context, STATE.md, or user input).
3. Add or edit BibTeX entries following the type rules above.
4. **PDF review gate**: vision-review every page of the PDF against HAL guidelines before upload.
5. Run the HAL SWORD workflow (dry run, then real).
6. Tell the user to rebuild: `cd ~/CNRS/html/src && make`
7. Update STATE.md if HAL IDs changed.
