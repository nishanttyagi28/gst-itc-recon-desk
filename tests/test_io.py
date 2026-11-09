import os

import pytest
from decimal import Decimal
from datetime import date

from recon.io import LoadError, load_gstr2b, load_purchase_register

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")


def test_loads_sample_purchase_register():
    rows = load_purchase_register(os.path.join(DATA_DIR, "purchase_register.csv"))
    assert len(rows) == 60
    first = rows[0]
    assert first["invoice_no"] == "INV-001"
    assert first["invoice_date"] == date(2024, 4, 1)
    assert first["taxable_value"] == Decimal("1250.00")
    assert first["cgst"] == Decimal("112.50")
    assert first["supplier_gstin"] == "27AAECS1234F1Z5"


def test_loads_sample_gstr2b():
    rows = load_gstr2b(os.path.join(DATA_DIR, "gstr2b.csv"))
    # 60 register invoices, 3 missing in 2B, 2 extra rows on the portal
    assert len(rows) == 59


def test_gstr2b_contains_known_issues():
    rows = load_gstr2b(os.path.join(DATA_DIR, "gstr2b.csv"))
    by_no = {r["invoice_no"]: r for r in rows}

    # invoice number format difference
    assert "INV/003" in by_no
    # rounding difference
    assert by_no["INV-008"]["sgst"] == Decimal("742.52")
    # wrong GSTIN
    assert by_no["INV-015"]["supplier_gstin"] == "27AAECS1234F1Z4"
    # date mismatch
    assert by_no["INV-022"]["invoice_date"] == date(2024, 5, 3)
    # invoices only in 2B
    assert "INV-020A" in by_no and "INV-044-B" in by_no
    # invoices missing in 2B
    assert "INV-010" not in by_no


def test_missing_field_raises(tmp_path):
    bad = tmp_path / "bad.csv"
    bad.write_text(
        "supplier_gstin,supplier_name,invoice_no,invoice_date,taxable_value,cgst,sgst,igst\n"
        "27AAECS1234F1Z5,Shree Traders,INV-001,2024-04-01,1250.00,112.50,112.50,\n",
        encoding="utf-8",
    )
    with pytest.raises(LoadError, match="missing fields"):
        load_purchase_register(bad)


def test_bad_amount_raises(tmp_path):
    bad = tmp_path / "bad.csv"
    bad.write_text(
        "supplier_gstin,supplier_name,invoice_no,invoice_date,taxable_value,cgst,sgst,igst\n"
        "27AAECS1234F1Z5,Shree Traders,INV-001,2024-04-01,12a50.00,112.50,112.50,0.00\n",
        encoding="utf-8",
    )
    with pytest.raises(LoadError, match="bad amount"):
        load_purchase_register(bad)
