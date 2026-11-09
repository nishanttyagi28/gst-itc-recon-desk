# Sample dataset

Two CSV files describe one quarter (Apr-Jun 2024) of purchases for a
Maharashtra-based SME whose own GSTIN is `27ABCDA1234B1Z1`. The purchase
register is what the accountant recorded in the books; the GSTR-2B file is
the same period as it appears on the GST portal. Several rows differ on
purpose so the reconciliation logic has real problems to find.

## Columns (same in both files)

| Column           | Meaning                                                              |
|------------------|----------------------------------------------------------------------|
| `supplier_gstin` | 15-character GSTIN of the supplier (first 2 digits = state code)     |
| `supplier_name`  | Supplier trade name                                                  |
| `invoice_no`     | Invoice number as recorded (books) or as uploaded (portal)           |
| `invoice_date`   | Invoice date, ISO format `YYYY-MM-DD`                                |
| `taxable_value`  | Amount before GST, in rupees with 2 decimals                         |
| `cgst`           | Central GST. Non-zero only for intra-state (Maharashtra) suppliers   |
| `sgst`           | State GST. Non-zero only for intra-state suppliers                   |
| `igst`           | Integrated GST. Non-zero only for inter-state suppliers              |

Tax rates used: 5% on every third invoice, 18% on the rest. Intra-state
invoices split the tax as CGST + SGST at half the rate each.

## Deliberate issues

### Invoice number format differences (books `INV-xxx`, portal `INV/xxx`)

| Books     | 2B        | Row invoice numbers |
|-----------|-----------|---------------------|
| INV-003   | INV/003   | both files          |
| INV-017   | INV/017   | both files          |
| INV-041   | INV/041   | both files          |

The supplier invoices with slashes; the accountant recorded them with
dashes. Amounts match exactly.

### Small rounding differences (portal tax differs by 1-2 paise)

| Invoice | Field | Books    | 2B       |
|---------|-------|----------|----------|
| INV-008 | sgst  | 742.50   | 742.52   |
| INV-018 | igst  | 912.50   | 912.49   |
| INV-051 | cgst  | 1281.25  | 1281.26  |

Taxable value and the other tax fields match exactly.

### Invoices in the books but missing in 2B

| Invoice | Supplier           | Date       | Taxable value |
|---------|--------------------|------------|---------------|
| INV-010 | Udaya Electricals  | 2024-04-10 | 10250.00      |
| INV-035 | Sen Packaging      | 2024-05-15 | 35250.00      |
| INV-058 | Prakash Enterprises| 2024-06-18 | 58250.00      |

The supplier did not file these invoices in the period.

### Invoices only in 2B (not in the books)

| Invoice   | Supplier          | Date       | Taxable value | Tax          |
|-----------|-------------------|------------|---------------|--------------|
| INV-020A  | Udaya Electricals | 2024-05-21 | 4750.00       | IGST 855.00  |
| INV-044-B | Udaya Electricals | 2024-06-14 | 9800.00       | IGST 1764.00 |

The supplier uploaded them to the portal but the accountant never booked
them.

### Wrong GSTIN in 2B

| Invoice | Books GSTIN      | 2B GSTIN         | Difference          |
|---------|------------------|------------------|---------------------|
| INV-015 | 27AAECS1234F1Z5  | 27AAECS1234F1Z4  | check digit differs |
| INV-043 | 27AAECS1234F1Z5  | 27AAECS1234F0Z5  | entity code differs |

Supplier name and amounts match; only the GSTIN is wrong on the portal.

### Date mismatches

| Invoice | Books date | 2B date   |
|---------|------------|-----------|
| INV-022 | 2024-05-02 | 2024-05-03|
| INV-049 | 2024-06-09 | 2024-06-10|

The portal shows the date the supplier reported at filing, one day later
than the books. Everything else matches.

## Row counts

- `data/purchase_register.csv`: 60 invoice rows.
- `data/gstr2b.csv`: 59 rows (60 - 3 missing + 2 portal-only).

Both files were generated with `scripts/gen_sample_data.py`.
