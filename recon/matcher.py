"""Match purchase-register invoices against GSTR-2B portal invoices."""
import re
from decimal import Decimal

# tax amounts may differ by up to this much (rupees) and still count as a match
TOLERANCE = Decimal("1")

CATEGORIES = (
    "MATCHED",
    "AMOUNT_MISMATCH",
    "MISSING_IN_2B",
    "MISSING_IN_BOOKS",
    "GSTIN_MISMATCH",
)


def normalize_invoice_no(invoice_no):
    """Ignore case, spaces and separators: INV-001 and INV/001 are the same."""
    return re.sub(r"[^A-Za-z0-9]", "", invoice_no).upper()


def normalize_gstin(gstin):
    return gstin.strip().upper()


def _tax_total(row):
    return row["cgst"] + row["sgst"] + row["igst"]


def _amounts_match(book, portal):
    return (abs(book["taxable_value"] - portal["taxable_value"]) <= TOLERANCE
            and abs(_tax_total(book) - _tax_total(portal)) <= TOLERANCE)


def _missing_in_2b(book):
    return {
        "category": "MISSING_IN_2B",
        "invoice_no": book["invoice_no"],
        "supplier_gstin": book["supplier_gstin"],
    }


def _missing_in_books(portal):
    return {
        "category": "MISSING_IN_BOOKS",
        "invoice_no": portal["invoice_no"],
        "supplier_gstin": portal["supplier_gstin"],
    }


def _match_pair(book, portal):
    """Classify a pair found through the invoice number."""
    result = {
        "category": None,
        "invoice_no": book["invoice_no"],
        "supplier_gstin": book["supplier_gstin"],
        "portal_invoice_no": portal["invoice_no"],
        "portal_gstin": portal["supplier_gstin"],
        "taxable_diff": book["taxable_value"] - portal["taxable_value"],
        "tax_diff": _tax_total(book) - _tax_total(portal),
    }
    if normalize_gstin(book["supplier_gstin"]) != normalize_gstin(portal["supplier_gstin"]):
        result["category"] = "GSTIN_MISMATCH"
    elif not _amounts_match(book, portal):
        result["category"] = "AMOUNT_MISMATCH"
    else:
        result["category"] = "MATCHED"
    return result


def _same_number(portal, book):
    """Portal row with the same normalized invoice number."""
    return normalize_invoice_no(portal["invoice_no"]) == normalize_invoice_no(book["invoice_no"])


def _same_gstin(portal, book):
    return normalize_gstin(portal["supplier_gstin"]) == normalize_gstin(book["supplier_gstin"])


def reconcile(purchase_rows, gstr2b_rows):
    """Return one classification entry per books invoice, plus portal-only ones."""
    results = []
    portal_remaining = list(gstr2b_rows)

    for book in purchase_rows:
        # exact match first: same normalized GSTIN and invoice number
        exact = [p for p in portal_remaining
                 if _same_gstin(p, book) and _same_number(p, book)]
        if exact:
            portal = exact[0]
        else:
            # a different GSTIN is only trusted when the numbers are equal and
            # the taxable value agrees, otherwise common numbers like INV-001
            # would pair unrelated suppliers
            candidates = [p for p in portal_remaining if _same_number(p, book)]
            equal_no = candidates and normalize_invoice_no(book["invoice_no"]) == normalize_invoice_no(candidates[0]["invoice_no"])
            if equal_no and abs(book["taxable_value"] - candidates[0]["taxable_value"]) <= TOLERANCE:
                portal = candidates[0]
            else:
                # containment matching stays inside the same supplier
                fuzzy = [p for p in portal_remaining
                         if _same_gstin(p, book)
                         and normalize_invoice_no(book["invoice_no"]) != normalize_invoice_no(p["invoice_no"])
                         and normalize_invoice_no(book["invoice_no"]) in normalize_invoice_no(p["invoice_no"])]
                portal = fuzzy[0] if len(fuzzy) == 1 else None

        if portal is None:
            results.append(_missing_in_2b(book))
            continue

        portal_remaining.remove(portal)
        results.append(_match_pair(book, portal))

    # whatever is left on the portal was never booked
    for portal in portal_remaining:
        results.append(_missing_in_books(portal))
    return results
