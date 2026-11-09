import pytest
from datetime import date
from decimal import Decimal

from recon.matcher import reconcile


def book(invoice_no, gstin="27AAECS1234F1Z5", taxable="1000.00",
         cgst="90.00", sgst="90.00", igst="0.00"):
    return {"supplier_gstin": gstin, "supplier_name": "Shree Traders",
            "invoice_no": invoice_no, "invoice_date": date(2024, 4, 1),
            "taxable_value": Decimal(taxable), "cgst": Decimal(cgst),
            "sgst": Decimal(sgst), "igst": Decimal(igst)}


def portal(invoice_no, gstin="27AAECS1234F1Z5", taxable="1000.00",
           cgst="90.00", sgst="90.00", igst="0.00"):
    return book(invoice_no, gstin, taxable, cgst, sgst, igst)


def categories(results):
    return {r["invoice_no"]: r["category"] for r in results}


def test_exact_match():
    results = reconcile([book("INV-001")], [portal("INV-001")])
    assert categories(results) == {"INV-001": "MATCHED"}


def test_invoice_number_format_difference_still_matches():
    results = reconcile([book("INV-001")], [portal("INV/001")])
    assert categories(results) == {"INV-001": "MATCHED"}
    assert results[0]["portal_invoice_no"] == "INV/001"


def test_rounding_within_tolerance_matches():
    # 50 paise difference in total tax is within the Rs 1 tolerance
    results = reconcile([book("INV-001", cgst="90.00", sgst="90.00")],
                        [portal("INV-001", cgst="90.50", sgst="90.00")])
    assert categories(results) == {"INV-001": "MATCHED"}


def test_amount_mismatch():
    results = reconcile([book("INV-001", taxable="1000.00")],
                        [portal("INV-001", taxable="1200.00")])
    assert categories(results) == {"INV-001": "AMOUNT_MISMATCH"}


def test_amount_mismatch_beyond_tolerance():
    # Rs 2 tax difference exceeds the Rs 1 tolerance
    results = reconcile([book("INV-001", sgst="90.00")],
                        [portal("INV-001", sgst="92.00")])
    assert categories(results) == {"INV-001": "AMOUNT_MISMATCH"}


def test_missing_in_2b():
    results = reconcile([book("INV-001")], [])
    assert categories(results) == {"INV-001": "MISSING_IN_2B"}


def test_missing_in_books():
    results = reconcile([], [portal("INV-001")])
    assert categories(results) == {"INV-001": "MISSING_IN_BOOKS"}


def test_gstin_mismatch():
    results = reconcile([book("INV-001", gstin="27AAECS1234F1Z5")],
                        [portal("INV-001", gstin="27AAECS1234F1Z4")])
    assert categories(results) == {"INV-001": "GSTIN_MISMATCH"}


def test_gstin_mismatch_not_double_counted_as_missing():
    # the portal row must not also show up as MISSING_IN_BOOKS
    results = reconcile([book("INV-001", gstin="27AAECS1234F1Z5")],
                        [portal("INV-001", gstin="27AAECS1234F1Z4")])
    assert len(results) == 1


def test_fuzzy_match_on_invoice_number():
    # books INV-020, portal INV-020A (unique containment)
    results = reconcile([book("INV-020")], [portal("INV-020A")])
    assert categories(results) == {"INV-020": "MATCHED"}


def test_common_invoice_number_across_suppliers():
    # two suppliers both issued INV-001; one is missing from 2B
    books = [
        book("INV-001", gstin="27AAECS1234F1Z5"),
        book("INV-001", gstin="29AABCU9012L1Z8"),
    ]
    gstr2b = [portal("INV-001", gstin="27AAECS1234F1Z5")]
    results = reconcile(books, gstr2b)
    assert {(r["supplier_gstin"], r["category"]) for r in results} == {
        ("27AAECS1234F1Z5", "MATCHED"),
        ("29AABCU9012L1Z8", "MISSING_IN_2B"),
    }


def test_different_gstin_with_very_different_amount_is_not_gstin_mismatch():
    # same number, different supplier, taxable value far apart: no pair
    results = reconcile([book("INV-001", gstin="27AAECS1234F1Z5",
                              taxable="1000.00")],
                        [portal("INV-001", gstin="29AABCU9012L1Z8",
                                taxable="50000.00")])
    # no GSTIN_MISMATCH pair: books row missing, portal row unbooked
    assert sorted(r["category"] for r in results) == ["MISSING_IN_2B", "MISSING_IN_BOOKS"]


def test_all_categories_together():
    books = [
        book("INV-001"),
        book("INV-002", taxable="1000.00", cgst="90.00", sgst="90.00"),
        book("INV-003"),
        book("INV-004", gstin="29AABCU9012L1Z8"),
        book("INV-005"),
    ]
    gstr2b = [
        portal("INV/001"),
        portal("INV-002", taxable="1000.00", cgst="95.00", sgst="95.00"),
        portal("INV-004", gstin="29AABCU9012L1Z7"),
        portal("INV-006"),
    ]
    results = reconcile(books, gstr2b)
    assert categories(results) == {
        "INV-001": "MATCHED",
        "INV-002": "AMOUNT_MISMATCH",
        "INV-003": "MISSING_IN_2B",
        "INV-004": "GSTIN_MISMATCH",
        "INV-005": "MISSING_IN_2B",
        "INV-006": "MISSING_IN_BOOKS",
    }
