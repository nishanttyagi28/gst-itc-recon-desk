"""Export reconciliation results to an Excel workbook."""
from collections import defaultdict
from decimal import Decimal

from openpyxl import Workbook
from openpyxl.utils import get_column_letter

CATEGORIES = ("MATCHED", "AMOUNT_MISMATCH", "MISSING_IN_2B",
              "MISSING_IN_BOOKS", "GSTIN_MISMATCH")
MONEY_FORMAT = "#,##0.00"


def _tax(row):
    return row["cgst"] + row["sgst"] + row["igst"]


def _books_lookup(purchase_rows):
    return {(r["supplier_gstin"], r["invoice_no"]): r for r in purchase_rows}


def _supplier_names(purchase_rows, gstr2b_rows):
    names = {}
    for row in purchase_rows + gstr2b_rows:
        names.setdefault(row["supplier_gstin"], row["supplier_name"])
    return names


def _at_risk_total(entries, books):
    """Total ITC (books tax) on invoices not allowed."""
    total = Decimal("0")
    for entry in entries:
        if entry["decision"] == "ALLOW":
            continue
        book = books.get((entry["supplier_gstin"], entry["invoice_no"]))
        if book is not None:
            total += _tax(book)
    return total


def _set_money(ws, cell, value):
    ws[cell] = float(value)
    ws[cell].number_format = MONEY_FORMAT


def summarize(entries, purchase_rows):
    """Counts, ITC at risk and per-supplier totals, shared by report and web app."""
    books = _books_lookup(purchase_rows)
    counts = defaultdict(int)
    for entry in entries:
        counts[entry["category"]] += 1
    by_supplier = defaultdict(lambda: [0, Decimal("0")])
    for entry in entries:
        if entry["decision"] == "ALLOW":
            continue
        book = books.get((entry["supplier_gstin"], entry["invoice_no"]))
        if book is None:
            continue  # portal-only invoices are not booked credit
        row = by_supplier[entry["supplier_gstin"]]
        row[0] += 1
        row[1] += _tax(book)
    return {
        "counts": dict(counts),
        "itc_at_risk": _at_risk_total(entries, books),
        "by_supplier": {gstin: {"invoices": count, "tax_at_risk": tax}
                        for gstin, (count, tax) in by_supplier.items()},
    }


def _write_summary(ws, entries, purchase_rows):
    summary = summarize(entries, purchase_rows)
    names = _supplier_names(purchase_rows, [])

    ws["A1"] = "ITC reconciliation summary"
    ws["A3"] = "Category"
    ws["B3"] = "Invoices"
    counts = summary["counts"]
    for i, category in enumerate(CATEGORIES):
        ws[f"A{4 + i}"] = category
        ws[f"B{4 + i}"] = counts.get(category, 0)

    ws["A10"] = "ITC at risk (Rs)"
    _set_money(ws, "B10", summary["itc_at_risk"])

    ws["A12"] = "By supplier"
    ws["A13"] = "GSTIN"
    ws["B13"] = "Supplier"
    ws["C13"] = "Invoices at risk"
    ws["D13"] = "Tax at risk (Rs)"
    for i, (gstin, row) in enumerate(sorted(summary["by_supplier"].items())):
        r = 14 + i
        ws[f"A{r}"] = gstin
        ws[f"B{r}"] = names.get(gstin, "")
        ws[f"C{r}"] = row["invoices"]
        _set_money(ws, f"D{r}", row["tax_at_risk"])

    ws.column_dimensions["A"].width = 20
    ws.column_dimensions["B"].width = 26
    ws.column_dimensions["C"].width = 18
    ws.column_dimensions["D"].width = 16


def _write_exceptions(ws, entries, purchase_rows):
    books = _books_lookup(purchase_rows)
    names = _supplier_names(purchase_rows, [])
    headers = ["Category", "Decision", "Reason", "Invoice no", "Portal invoice no",
               "Supplier GSTIN", "Supplier name", "Tax diff", "Taxable diff"]
    ws.append(headers)
    for entry in entries:
        if entry["decision"] == "ALLOW":
            continue
        book = books.get((entry["supplier_gstin"], entry["invoice_no"]))
        ws.append([
            entry["category"],
            entry["decision"],
            entry["reason"],
            entry["invoice_no"],
            entry.get("portal_invoice_no", ""),
            entry["supplier_gstin"],
            names.get(entry["supplier_gstin"], ""),
            float(entry.get("tax_diff", 0) or 0),
            float(entry.get("taxable_diff", 0) or 0),
        ])
    last_row = ws.max_row
    # the two diff columns keep the money format even when empty
    for r in range(2, last_row + 1):
        for col in ("H", "I"):
            ws[f"{col}{r}"].number_format = MONEY_FORMAT
    if last_row >= 1:
        ws.auto_filter.ref = f"A1:I{last_row}"
    widths = [18, 10, 52, 12, 18, 18, 24, 10, 12]
    for i, width in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(i)].width = width


def _write_followup(ws, entries, purchase_rows):
    books = _books_lookup(purchase_rows)
    names = _supplier_names(purchase_rows, [])
    headers = ["Supplier GSTIN", "Supplier name", "Invoices missing in 2B",
               "ITC at risk (Rs)"]
    ws.append(headers)
    by_supplier = defaultdict(lambda: [0, Decimal("0")])
    for entry in entries:
        if entry["category"] != "MISSING_IN_2B":
            continue
        book = books.get((entry["supplier_gstin"], entry["invoice_no"]))
        row = by_supplier[entry["supplier_gstin"]]
        row[0] += 1
        if book is not None:
            row[1] += _tax(book)
    for gstin, (count, tax) in sorted(by_supplier.items(),
                                      key=lambda item: (-item[1][1], item[0])):
        ws.append([gstin, names.get(gstin, ""), count, None])
        _set_money(ws, f"D{ws.max_row}", tax)
    ws.column_dimensions["A"].width = 18
    ws.column_dimensions["B"].width = 26
    ws.column_dimensions["C"].width = 22
    ws.column_dimensions["D"].width = 16


def export_report(entries, purchase_rows, gstr2b_rows, out_path):
    """Write the Summary, Exceptions and Supplier follow-up sheets."""
    wb = Workbook()
    _write_summary(wb.active, entries, purchase_rows)
    wb.active.title = "Summary"
    _write_exceptions(wb.create_sheet("Exceptions"), entries, purchase_rows)
    _write_followup(wb.create_sheet("Supplier follow-up"), entries, purchase_rows)
    wb.save(out_path)
