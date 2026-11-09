import io

import pytest
from fastapi.testclient import TestClient
from openpyxl import load_workbook

from recon.app import SESSIONS, app

client = TestClient(app)

CSV_HEADER = ("supplier_gstin,supplier_name,invoice_no,invoice_date,"
              "taxable_value,cgst,sgst,igst\n")


def csv_row(gstin, name, inv, date, taxable, cgst, sgst, igst):
    return f"{gstin},{name},{inv},{date},{taxable},{cgst},{sgst},{igst}\n"


BOOKS_CSV = CSV_HEADER + (
    csv_row("27AAECS1234F1Z5", "Shree Traders", "INV-001", "2024-04-01",
            "1000.00", "90.00", "90.00", "0.00")
    + csv_row("29AABCU9012L1Z8", "Udaya Electricals", "INV-002", "2024-04-02",
              "1000.00", "0.00", "0.00", "180.00")
)

GSTR2B_CSV = CSV_HEADER + (
    csv_row("27AAECS1234F1Z5", "Shree Traders", "INV/001", "2024-04-01",
            "1000.00", "90.00", "90.00", "0.00")
    + csv_row("27AAECS1234F1Z5", "Shree Traders", "INV-009", "2024-04-03",
              "500.00", "45.00", "45.00", "0.00")
)

BAD_CSV = CSV_HEADER + csv_row("27AAECS1234F1Z5", "Shree Traders", "INV-001",
                               "2024-04-01", "abc", "90.00", "90.00", "0.00")


def upload(files=None):
    if files is None:
        files = {"books": ("books.csv", io.BytesIO(BOOKS_CSV.encode()), "text/csv"),
                 "gstr2b": ("gstr2b.csv", io.BytesIO(GSTR2B_CSV.encode()), "text/csv")}
    response = client.post("/api/reconcile", files=files)
    assert response.status_code == 200
    return response.json()


@pytest.fixture(autouse=True)
def clear_sessions():
    SESSIONS.clear()
    yield
    SESSIONS.clear()


def test_index_serves_html():
    response = client.get("/")
    assert response.status_code == 200
    assert "ITC Reconciliation Desk" in response.text
    assert "<form" in response.text


def test_reconcile_returns_summary_and_exceptions():
    data = upload()
    assert data["summary"]["counts"] == {"MATCHED": 1, "MISSING_IN_2B": 1,
                                         "MISSING_IN_BOOKS": 1}
    # Shree tax at risk is 0; Udaya's missing invoice puts 180.00 at risk
    assert data["summary"]["itc_at_risk"] == "180.00"
    categories = [e["category"] for e in data["exceptions"]]
    assert categories == ["MISSING_IN_2B", "MISSING_IN_BOOKS"]
    assert data["session_id"]


def test_reconcile_rejects_bad_csv():
    files = {"books": ("books.csv", io.BytesIO(BAD_CSV.encode()), "text/csv"),
             "gstr2b": ("gstr2b.csv", io.BytesIO(GSTR2B_CSV.encode()), "text/csv")}
    response = client.post("/api/reconcile", files=files)
    assert response.status_code == 400
    assert "bad amount" in response.json()["detail"]


def test_report_download_is_a_workbook():
    session_id = upload()["session_id"]
    response = client.get(f"/api/report/{session_id}")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    assert response.headers["content-disposition"].endswith('"itc-report.xlsx"')
    wb = load_workbook(io.BytesIO(response.content))
    assert wb.sheetnames == ["Summary", "Exceptions", "Supplier follow-up"]


def test_report_download_unknown_session():
    assert client.get("/api/report/nope").status_code == 404
