"""CSV loaders for the purchase register and the GSTR-2B portal file."""
import csv
from datetime import date
from decimal import Decimal, InvalidOperation

MONEY_FIELDS = ("taxable_value", "cgst", "sgst", "igst")
COLUMNS = ("supplier_gstin", "supplier_name", "invoice_no", "invoice_date") + MONEY_FIELDS


class LoadError(ValueError):
    """Raised when a row cannot be parsed."""


def _parse_row(row, line_no):
    missing = [col for col in COLUMNS if not row.get(col)]
    if missing:
        raise LoadError(f"line {line_no}: missing fields: {', '.join(missing)}")

    try:
        invoice_date = date.fromisoformat(row["invoice_date"])
    except ValueError:
        raise LoadError(f"line {line_no}: bad date {row['invoice_date']!r}")

    amounts = {}
    for field in MONEY_FIELDS:
        try:
            amounts[field] = Decimal(row[field])
        except InvalidOperation:
            raise LoadError(f"line {line_no}: bad amount {row[field]!r} in {field}")

    return {
        "supplier_gstin": row["supplier_gstin"].strip(),
        "supplier_name": row["supplier_name"].strip(),
        "invoice_no": row["invoice_no"].strip(),
        "invoice_date": invoice_date,
        **amounts,
    }


def _load(source):
    """source is a path or an open text file (an upload is parsed from memory)."""
    rows = []
    f = source if hasattr(source, "read") else open(source, newline="", encoding="utf-8")
    try:
        for line_no, row in enumerate(csv.DictReader(f), start=2):
            rows.append(_parse_row(row, line_no))
    finally:
        if f is not source:
            f.close()
    return rows


def load_purchase_register(path):
    """Load purchase-book invoices as a list of dicts."""
    return _load(path)


def load_gstr2b(path):
    """Load GSTR-2B portal invoices as a list of dicts."""
    return _load(path)
