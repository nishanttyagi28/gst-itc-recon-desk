"""One-off generator for the sample dataset. Not part of the deliverable."""
import csv
import os
from decimal import Decimal, ROUND_HALF_UP

# write to <project root>/data regardless of the current working directory
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "data")

suppliers = [
    # (gstin, name, state_code) state 27=MH, 29=KA, 07=DL, 24=GJ, 33=TN, 19=WB
    ("27AAECS1234F1Z5", "Shree Traders", "27"),
    ("27AACCP5678K1Z2", "Prakash Enterprises", "27"),
    ("29AABCU9012L1Z8", "Udaya Electricals", "29"),
    ("07AAFCR3456M1Z4", "Ravi Hardware Pvt Ltd", "07"),
    ("24AAGCN7890P1Z6", "Nand Sons", "24"),
    ("33AAJCT2345Q1Z9", "Tamil Paper Mart", "33"),
    ("19AAKCS6789R1Z3", "Sen Packaging", "19"),
]

own_gstin = "27ABCDA1234B1Z1"  # buyer is in Maharashtra

rows = []
for i in range(1, 61):
    gstin, name, state = suppliers[(i - 1) % len(suppliers)]
    inv = f"INV-{i:03d}"
    # spread across Apr-Jun 2024
    month = 4 + (i - 1) // 20
    day = ((i - 1) % 20) + 1
    date = f"2024-{month:02d}-{day:02d}"
    taxable = Decimal(str(1000 * i + 250))
    inter_state = state != "27"
    rate = Decimal("18") if i % 3 else Decimal("5")
    if inter_state:
        igst = (taxable * rate / 100).quantize(Decimal("0.01"), ROUND_HALF_UP)
        cgst = sgst = Decimal("0.00")
    else:
        cgst = (taxable * rate / 200).quantize(Decimal("0.01"), ROUND_HALF_UP)
        sgst = cgst
        igst = Decimal("0.00")
    rows.append({
        "supplier_gstin": gstin, "supplier_name": name, "invoice_no": inv,
        "invoice_date": date, "taxable_value": f"{taxable:.2f}",
        "cgst": f"{cgst:.2f}", "sgst": f"{sgst:.2f}", "igst": f"{igst:.2f}",
    })

with open(os.path.join(DATA_DIR, "purchase_register.csv"), "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    w.writeheader()
    w.writerows(rows)

# --- build 2B from the register, then inject problems -------------------
portal = [dict(r) for r in rows]
def find(inv):
    return next(r for r in portal if r["invoice_no"] == inv)

# 1. invoice number format differences: portal uses slashes instead of dashes
for inv in ("INV-003", "INV-017", "INV-041"):
    find(inv)["invoice_no"] = inv.replace("-", "/")

# 2. small rounding differences (portal rounds tax slightly differently)
for inv, field, delta in (("INV-008", "sgst", "0.02"), ("INV-018", "igst", "-0.01"),
                          ("INV-051", "cgst", "0.01")):
    r = find(inv)
    r[field] = f"{Decimal(r[field]) + Decimal(delta):.2f}"

# 3. invoices missing in 2B (supplier never filed them)
portal.remove(find("INV-010"))
portal.remove(find("INV-035"))
portal.remove(find("INV-058"))

# 4. invoices only in 2B (supplier uploaded them, books never got them)
extra1 = dict(find("INV-020"))
extra1.update(supplier_gstin="29AABCU9012L1Z8", supplier_name="Udaya Electricals",
              invoice_no="INV-020A", invoice_date="2024-05-21",
              taxable_value="4750.00", cgst="0.00", sgst="0.00", igst="855.00")
extra2 = dict(find("INV-044"))
extra2.update(supplier_gstin="29AABCU9012L1Z8", supplier_name="Udaya Electricals",
              invoice_no="INV-044-B", invoice_date="2024-06-14",
              taxable_value="9800.00", cgst="0.00", sgst="0.00", igst="1764.00")
portal.extend([extra1, extra2])

# 5. wrong GSTIN in 2B (only the GSTIN differs, name and amounts match)
find("INV-015")["supplier_gstin"] = "27AAECS1234F1Z4"  # check digit differs
find("INV-043")["supplier_gstin"] = "27AAECS1234F0Z5"  # entity code differs

# 6. date mismatches (portal shows the date reported at filing, one day later)
find("INV-022")["invoice_date"] = "2024-05-03"   # books say 2024-05-02
find("INV-049")["invoice_date"] = "2024-06-10"   # books say 2024-06-09

# keep 2B in invoice order
portal.sort(key=lambda r: r["invoice_no"])
with open(os.path.join(DATA_DIR, "gstr2b.csv"), "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    w.writeheader()
    w.writerows(portal)

print(f"register rows: {len(rows)}, 2b rows: {len(portal)}")
