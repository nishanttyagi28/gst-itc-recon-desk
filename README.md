# GST ITC Reconciliation Desk

A small tool for an Indian SME's finance person: it compares the purchase
register kept in the books against the GSTR-2B statement from the GST
portal, shows every invoice that does not line up, and says whether input
tax credit (ITC) can be claimed.

## The problem in plain words

Businesses buy goods and pay GST on those purchases. They can claim that
GST back as input tax credit (ITC), but only for invoices that the supplier
actually reported on the GST portal (GSTR-2B). In practice the books and
the portal never agree perfectly: invoice numbers get typed differently,
tax amounts are rounded differently, invoices go missing on either side,
suppliers upload wrong GSTINs, and dates drift. Before filing a return,
someone has to sit down with both lists and tick off the differences. This
tool does that ticking automatically and leaves only the real problems.

## How the reconciliation works

1. **Normalize.** Invoice numbers are compared without separators and case
   (`INV-001` and `INV/001` are the same). GSTINs are trimmed and uppercased.
2. **Match.** Every books invoice first looks for a portal invoice with the
   same normalized GSTIN and invoice number. If that fails, a fuzzy pass
   looks for portal invoices whose number contains the books number
   (e.g. `INV020` inside `INV020A`), but only from the same supplier. A pair
   with different GSTINs is accepted only when the numbers are equal and the
   taxable value agrees within Rs 1.
3. **Classify.** Each invoice gets one category:
   - `MATCHED` - books and portal agree (small rounding within Rs 1 is fine)
   - `AMOUNT_MISMATCH` - same invoice, but amounts differ beyond Rs 1
   - `MISSING_IN_2B` - in the books but the supplier never filed it
   - `MISSING_IN_BOOKS` - on the portal but never booked
   - `GSTIN_MISMATCH` - same invoice, different GSTIN
4. **Decide.** Rules from `config/itc_rules.yaml` turn each category into an
   ITC decision: `ALLOW`, `REVIEW`, or `BLOCK`, with a plain-language reason.
   An accountant can change the actions and the review threshold in the YAML.
5. **Report.** An Excel workbook with a Summary sheet (counts, ITC at risk,
   per supplier), an Exceptions sheet with filters, and a Supplier
   follow-up sheet for chasing suppliers with missing invoices.

## Screenshots

- Web app upload screen: `docs/screenshots/upload.png`
- Summary and exceptions after reconciliation: `docs/screenshots/results.png`
- Excel report, Summary sheet: `docs/screenshots/excel.png`

## How to run

Requires Python 3.12+. Install the dependencies first:

```bash
pip install -r requirements.txt
```

```bash
# CLI: reconcile and export the Excel report
python -m recon run --books data/purchase_register.csv --gstr2b data/gstr2b.csv --out report.xlsx

# Web app: upload the two CSVs in a browser
uvicorn recon.app:app --reload
# then open http://127.0.0.1:8000
```

A sample dataset with every known problem baked in lives in `data/`; see
`docs/DATA.md` for what each problem row demonstrates. Regenerate it with
`python scripts/gen_sample_data.py`.

Run the tests with:

```bash
python -m pytest -q
```

## Design decisions

- **Plain dicts, no ORM or pandas.** Rows are dicts with `Decimal` amounts
  and ISO dates. The whole pipeline is small; the standard library plus
  openpyxl covers it.
- **Matching is deliberately conservative.** Fuzzy matching only accepts
  containment (`INV020` in `INV020A`) within the same supplier, and only
  when unambiguous. Cross-GSTIN pairs need equal numbers and a close
  taxable value, because invoice numbers like `INV-001` repeat across
  suppliers.
- **Amount comparison uses total tax, not per-field.** CGST and SGST are
  one tax split in two; comparing the total keeps the tolerance logic
  simple.
- **Rules live in YAML, not code.** The accountant-facing policy (what goes
  to REVIEW vs BLOCK, and the rupee threshold) is editable without touching
  Python. An unknown action in the YAML fails loudly.
- **Dates are ignored when matching.** Portal filing dates commonly differ
  by a day; date mismatches are not a category in this version.
- **In-memory sessions in the web app.** Results live in a dict keyed by a
  session id. Good enough for a single desk; not for multiple users.

## Known limitations

- No persistence: web sessions and their download links are lost on restart.
- Invoice matching is number-based only; no supplier-name similarity, no
  line-item matching, no multi-period carry-forward of unmatched invoices.
- The tolerance is a flat Rs 1, not a percentage, so it behaves differently
  on very large invoices.
- CSV loaders are strict: one bad row fails the whole file with a line
  number instead of skipping and warning.
- The web app has no authentication; it is meant to run locally.
- No reverse-charge, amendment, or credit-note handling that real GSTR-2B
  files contain.

## What I would do next

1. Persist reconciliation runs (SQLite would be enough) so history and
   trends per supplier survive restarts.
2. Add a supplier-name-based fallback match and a review of near-miss
   suggestions in the UI.
3. Carry unmatched invoices across periods instead of treating each run
   independently.
4. Add authentication and multi-user support to the web app if it ever
   leaves one desk.
5. Package it properly (pyproject.toml, pinned dependencies) so install is
   one command.
