import os

import pytest
from datetime import date
from decimal import Decimal
from openpyxl import load_workbook

from recon.__main__ import main
from recon.io import load_gstr2b, load_purchase_register
from recon.matcher import reconcile
from recon.rules import decide, load_config
from recon.report import export_report

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")


def book(invoice_no, gstin="27AAECS1234F1Z5", taxable="1000.00",
         cgst="90.00", sgst="90.00", igst="0.00"):
    return {"supplier_gstin": gstin, "supplier_name": "Shree Traders",
            "invoice_no": invoice_no, "invoice_date": date(2024, 4, 1),
            "taxable_value": Decimal(taxable), "cgst": Decimal(cgst),
            "sgst": Decimal(sgst), "igst": Decimal(igst)}


def portal(invoice_no, gstin="27AAECS1234F1Z5", taxable="1000.00",
           cgst="90.00", sgst="90.00", igst="0.00"):
    return book(invoice_no, gstin, taxable, cgst, sgst, igst)


@pytest.fixture
def workbook(tmp_path, monkeypatch):
    # run the CLI end to end on a small dataset, then reopen the workbook
    monkeypatch.chdir(tmp_path)
    books_rows = [
        book("INV-001"),
        book("INV-002", taxable="1000.00", cgst="90.00", sgst="90.00"),
        book("INV-003", gstin="29AABCU9012L1Z8"),
        book("INV-004"),
    ]
    gstr2b_rows = [
        portal("INV/001"),
        portal("INV-002", taxable="1000.00", cgst="95.00", sgst="95.00"),
        portal("INV-005"),
    ]
    (tmp_path / "books.csv").write_text(
        "supplier_gstin,supplier_name,invoice_no,invoice_date,taxable_value,cgst,sgst,igst\n"
        + "".join(
            f'{r["supplier_gstin"]},{r["supplier_name"]},{r["invoice_no"]},'
            f'{r["invoice_date"]},{r["taxable_value"]},{r["cgst"]},{r["sgst"]},{r["igst"]}\n'
            for r in books_rows),
        encoding="utf-8")
    (tmp_path / "gstr2b.csv").write_text(
        "supplier_gstin,supplier_name,invoice_no,invoice_date,taxable_value,cgst,sgst,igst\n"
        + "".join(
            f'{r["supplier_gstin"]},{r["supplier_name"]},{r["invoice_no"]},'
            f'{r["invoice_date"]},{r["taxable_value"]},{r["cgst"]},{r["sgst"]},{r["igst"]}\n'
            for r in gstr2b_rows),
        encoding="utf-8")
    main(["run", "--books", "books.csv", "--gstr2b", "gstr2b.csv",
          "--out", "report.xlsx"])
    return load_workbook(tmp_path / "report.xlsx")


def test_workbook_has_the_three_sheets(workbook):
    assert workbook.sheetnames == ["Summary", "Exceptions", "Supplier follow-up"]


def test_summary_counts_and_itc_at_risk(workbook):
    ws = workbook["Summary"]
    counts = {ws[f"A{r}"].value: ws[f"B{r}"].value for r in range(4, 9)}
    # INV-001 matched, INV-002 amount mismatch (tax diff 10.00 -> REVIEW),
    # INV-003 missing in 2B, INV-004 missing in 2B; INV-005 portal-only
    assert counts == {"MATCHED": 1, "AMOUNT_MISMATCH": 1, "MISSING_IN_2B": 2,
                      "MISSING_IN_BOOKS": 1, "GSTIN_MISMATCH": 0}
    # tax at risk: INV-002 (180.00) + INV-003 (180.00) + INV-004 (180.00)
    assert ws["B10"].value == pytest.approx(540.00)


def test_summary_by_supplier(workbook):
    ws = workbook["Summary"]
    rows = [(ws[f"A{r}"].value, ws[f"C{r}"].value, ws[f"D{r}"].value)
            for r in range(14, ws.max_row + 1)]
    assert ("29AABCU9012L1Z8", 1, pytest.approx(180.00)) in rows
    assert ("27AAECS1234F1Z5", 2, pytest.approx(360.00)) in rows


def test_exceptions_sheet_lists_non_allowed_rows_with_filters(workbook):
    ws = workbook["Exceptions"]
    assert ws.auto_filter.ref == "A1:I5"
    categories = [ws[f"A{r}"].value for r in range(2, ws.max_row + 1)]
    assert "MATCHED" not in categories
    assert categories.count("MISSING_IN_2B") == 2
    assert categories.count("AMOUNT_MISMATCH") == 1
    assert categories.count("MISSING_IN_BOOKS") == 1


def test_supplier_followup_lists_suppliers_with_missing_invoices(workbook):
    ws = workbook["Supplier follow-up"]
    rows = [(ws[f"A{r}"].value, ws[f"C{r}"].value, ws[f"D{r}"].value)
            for r in range(2, ws.max_row + 1)]
    # both suppliers have one missing invoice each; tie broken by GSTIN
    assert rows == [("27AAECS1234F1Z5", 1, pytest.approx(180.00)),
                    ("29AABCU9012L1Z8", 1, pytest.approx(180.00))]


def test_export_report_with_full_sample_dataset(tmp_path, monkeypatch):
    # sanity check against the real sample data end to end
    monkeypatch.chdir(tmp_path)
    main(["run",
          "--books", os.path.join(DATA_DIR, "purchase_register.csv"),
          "--gstr2b", os.path.join(DATA_DIR, "gstr2b.csv"),
          "--out", "report.xlsx"])
    wb = load_workbook(tmp_path / "report.xlsx")
    ws = wb["Exceptions"]
    categories = [ws[f"A{r}"].value for r in range(2, ws.max_row + 1)]
    assert categories.count("MATCHED") == 0  # exceptions never list matched rows
    assert wb["Supplier follow-up"].max_row >= 2
