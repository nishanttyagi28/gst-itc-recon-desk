"""Web app: upload the two CSVs, see results, download the Excel report.

Run locally with: uvicorn recon.app:app --reload
"""
import io
import os
import uuid
from collections import defaultdict

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response

from recon.__main__ import DEFAULT_CONFIG
from recon.io import LoadError, load_gstr2b, load_purchase_register
from recon.matcher import reconcile
from recon.report import export_report, summarize
from recon.rules import decide, load_config

app = FastAPI(title="GST ITC Reconciliation Desk")

# results kept in memory, keyed by session id; enough for a single-desk tool
SESSIONS = {}

XLSX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _read_csv(upload: UploadFile):
    text = upload.file.read().decode("utf-8-sig")
    return io.StringIO(text)


def _exceptions(entries, limit=200):
    rows = [e for e in entries if e["decision"] != "ALLOW"]
    return [
        {
            "category": e["category"],
            "decision": e["decision"],
            "reason": e["reason"],
            "invoice_no": e["invoice_no"],
            "portal_invoice_no": e.get("portal_invoice_no", ""),
            "supplier_gstin": e["supplier_gstin"],
            "tax_diff": str(e.get("tax_diff", "") or ""),
            "taxable_diff": str(e.get("taxable_diff", "") or ""),
        }
        for e in rows[:limit]
    ]


@app.get("/")
def index():
    static = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
    return FileResponse(os.path.join(static, "index.html"))


@app.post("/api/reconcile")
async def reconcile_uploads(books: UploadFile = File(...), gstr2b: UploadFile = File(...)):
    try:
        book_rows = load_purchase_register(_read_csv(books))
        portal_rows = load_gstr2b(_read_csv(gstr2b))
    except LoadError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    results = reconcile(book_rows, portal_rows)
    entries = [{**result, **decide(result, load_config(DEFAULT_CONFIG))}
               for result in results]
    summary = summarize(entries, book_rows)
    summary["itc_at_risk"] = str(summary["itc_at_risk"])
    for row in summary["by_supplier"].values():
        row["tax_at_risk"] = str(row["tax_at_risk"])

    session_id = uuid.uuid4().hex
    SESSIONS[session_id] = (entries, book_rows, portal_rows)
    return {
        "session_id": session_id,
        "summary": summary,
        "exceptions": _exceptions(entries),
    }


@app.get("/api/report/{session_id}")
def download_report(session_id: str):
    if session_id not in SESSIONS:
        raise HTTPException(status_code=404, detail="unknown session")
    entries, book_rows, portal_rows = SESSIONS[session_id]
    buffer = io.BytesIO()
    export_report(entries, book_rows, portal_rows, buffer)
    return Response(
        content=buffer.getvalue(),
        media_type=XLSX_MEDIA_TYPE,
        headers={"Content-Disposition": 'attachment; filename="itc-report.xlsx"'},
    )


@app.get("/healthz")
def healthz():
    return {"status": "ok"}

