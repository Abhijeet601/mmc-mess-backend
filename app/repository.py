import secrets
import json
from datetime import date, datetime

from fastapi import HTTPException, status

from .db import get_db, row_to_dict


def audit(actor_user_id: int | None, action: str, entity_type: str, entity_id: str, details: str = "") -> None:
    details_payload = details if isinstance(details, (dict, list)) else {"message": details}
    with get_db() as db:
        db.execute(
            "INSERT INTO audit_logs (actor_user_id, action, entity_type, entity_id, details) VALUES (?, ?, ?, ?, ?)",
            (actor_user_id, action, entity_type, entity_id, json.dumps(details_payload)),
        )


def get_user_by_login_id(login_id: str) -> dict | None:
    with get_db() as db:
        row = db.execute("SELECT * FROM users WHERE lower(login_id) = lower(?) AND active = 1", (login_id,)).fetchone()
        return row_to_dict(row)


def get_student(student_id: int) -> dict | None:
    with get_db() as db:
        return row_to_dict(db.execute("SELECT * FROM students WHERE id = ? AND active = 1", (student_id,)).fetchone())


def get_payment_config() -> dict:
    with get_db() as db:
        return row_to_dict(db.execute("SELECT * FROM payment_config WHERE id = 1").fetchone())


def list_student_invoices(student_id: int) -> list[dict]:
    with get_db() as db:
        rows = db.execute(
            """
            SELECT i.*, p.payment_mode, p.gateway, p.transaction_id, p.payment_date, p.receipt_url, p.remarks
            FROM invoices i
            LEFT JOIN payments p ON p.invoice_id = i.id AND p.status = 'Success'
            WHERE i.student_id = ?
            ORDER BY i.year DESC, i.id DESC
            """,
            (student_id,),
        ).fetchall()
        return [dict(row) for row in rows]


def get_invoice(invoice_id: int) -> dict | None:
    with get_db() as db:
        return row_to_dict(db.execute("SELECT * FROM invoices WHERE id = ?", (invoice_id,)).fetchone())


def ensure_student_invoice(student_id: int) -> dict:
    config = get_payment_config()
    today = date.today()
    month = today.strftime("%B")
    due_date = date(today.year, today.month, min(config["due_day"], 28)).isoformat()
    with get_db() as db:
        db.execute(
            """
            INSERT OR IGNORE INTO invoices (student_id, month, year, amount, due_date, status)
            VALUES (?, ?, ?, ?, ?, 'Pending')
            """,
            (student_id, month, today.year, config["monthly_fee"], due_date),
        )
    invoice = next((item for item in list_student_invoices(student_id) if item["month"] == month and item["year"] == today.year), None)
    if not invoice:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Unable to create invoice")
    return invoice


def create_payment_order(student_id: int, invoice_id: int, gateway: str) -> dict:
    invoice = get_invoice(invoice_id)
    if not invoice or invoice["student_id"] != student_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")
    if invoice["status"] == "Paid":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Invoice already paid")
    config = get_payment_config()
    enabled_map = {
        "demo": config["demo_gateway_enabled"],
        "razorpay": config["razorpay_enabled"],
        "ccavenue": config["ccavenue_enabled"],
        "bank_transfer": config["bank_transfer_enabled"],
    }
    if not enabled_map.get(gateway):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Gateway disabled")
    gateway_order_id = f"ORD-{secrets.token_hex(10).upper()}"
    amount = invoice["amount"] + invoice["fine"]
    with get_db() as db:
        db.execute(
            """
            INSERT INTO payments (invoice_id, student_id, amount, fine, payment_mode, gateway, transaction_id, gateway_order_id, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'Created')
            """,
            (invoice_id, student_id, invoice["amount"], invoice["fine"], gateway.title(), gateway, f"PENDING-{secrets.token_hex(8).upper()}", gateway_order_id),
        )
    audit(None, "payment_order_created", "invoice", str(invoice_id), gateway_order_id)
    return {
        "gateway_order_id": gateway_order_id,
        "invoice_id": invoice_id,
        "amount": amount,
        "gateway": gateway,
        "demo_payment_enabled": gateway == "demo",
    }


def _next_receipt_no(prefix: str, invoice_id: int) -> str:
    return f"{prefix}-{datetime.utcnow().strftime('%y%m')}-{invoice_id:06d}"


def confirm_demo_payment(student_id: int, gateway_order_id: str, transaction_id: str | None = None) -> dict:
    with get_db() as db:
        payment = row_to_dict(db.execute(
            "SELECT * FROM payments WHERE gateway_order_id = ? AND student_id = ? AND status = 'Created'",
            (gateway_order_id, student_id),
        ).fetchone())
        if not payment:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment order not found")
        invoice = row_to_dict(db.execute("SELECT * FROM invoices WHERE id = ?", (payment["invoice_id"],)).fetchone())
        config = row_to_dict(db.execute("SELECT * FROM payment_config WHERE id = 1").fetchone())
        txn = transaction_id or f"DEMO-{secrets.token_hex(8).upper()}"
        receipt_no = _next_receipt_no(config["receipt_prefix"], invoice["id"])
        db.execute(
            """
            UPDATE payments
            SET status = 'Success', transaction_id = ?, gateway_response = ?, payment_date = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (txn, json.dumps({"status": "demo_gateway_success"}), payment["id"]),
        )
        db.execute("UPDATE invoices SET status = 'Paid', receipt_no = ? WHERE id = ?", (receipt_no, invoice["id"]))
    audit(None, "payment_success", "invoice", str(payment["invoice_id"]), txn)
    return {"status": "Paid", "receipt_no": receipt_no, "transaction_id": txn}


def admin_mark_paid(actor_user_id: int, invoice_id: int, payment_mode: str, transaction_id: str, amount=None, payment_date=None, remarks=None, receipt_url=None) -> dict:
    invoice = get_invoice(invoice_id)
    if not invoice:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")
    if invoice["status"] == "Paid":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Invoice already paid")
    config = get_payment_config()
    receipt_no = _next_receipt_no(config["receipt_prefix"], invoice_id)
    with get_db() as db:
        db.execute(
            """
            INSERT INTO payments (invoice_id, student_id, amount, fine, payment_mode, gateway, transaction_id, gateway_order_id, status, approved_by, payment_date, gateway_response, remarks, receipt_url)
            VALUES (?, ?, ?, ?, ?, 'offline', ?, ?, 'Success', ?, COALESCE(?, CURRENT_TIMESTAMP), ?, ?, ?)
            """,
            (
                invoice_id,
                invoice["student_id"],
                amount or invoice["amount"],
                invoice["fine"],
                payment_mode,
                transaction_id,
                f"OFFLINE-{secrets.token_hex(8).upper()}",
                actor_user_id,
                payment_date,
                json.dumps({"status": "admin_offline_approved"}),
                remarks,
                receipt_url,
            ),
        )
        db.execute("UPDATE invoices SET status = 'Paid', receipt_no = ? WHERE id = ?", (receipt_no, invoice_id))
    audit(actor_user_id, "offline_payment_approved", "invoice", str(invoice_id), {"transaction_id": transaction_id, "mode": payment_mode, "amount": amount or invoice["amount"], "payment_date": payment_date, "remarks": remarks, "receipt_url": receipt_url})
    return {"status": "Paid", "receipt_no": receipt_no}


def list_admin_payments(status_filter: str | None = None, hostel: str | None = None, search: str | None = None) -> list[dict]:
    clauses = []
    params: list[str] = []
    if status_filter:
        clauses.append("(CASE WHEN i.status != 'Paid' AND i.due_date < CURRENT_DATE THEN 'Overdue' ELSE i.status END) = ?")
        params.append(status_filter)
    if hostel:
        clauses.append("s.hostel = ?")
        params.append(hostel)
    if search:
        clauses.append("(lower(s.name) LIKE ? OR lower(s.registration_number) LIKE ? OR lower(s.admission_number) LIKE ? OR lower(s.room_number) LIKE ? OR lower(s.hostel) LIKE ? OR lower(i.month) LIKE ?)")
        q = f"%{search.lower()}%"
        params.extend([q, q, q, q, q, q])
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    with get_db() as db:
        rows = db.execute(
            f"""
            SELECT i.*, CASE WHEN i.status != 'Paid' AND i.due_date < CURRENT_DATE THEN 'Overdue' ELSE i.status END AS status,
                   DATEDIFF(i.due_date, CURRENT_DATE) AS days_until_due,
                   s.name AS student_name, s.registration_number, s.admission_number, s.hostel, s.room_number,
                   s.course, s.department, s.academic_year, s.semester, s.mobile, s.photo_url,
                   p.amount AS amount_paid, p.payment_date, p.payment_mode, p.transaction_id, p.receipt_url, p.remarks
            FROM invoices i
            JOIN students s ON s.id = i.student_id
            LEFT JOIN payments p ON p.invoice_id = i.id AND p.status = 'Success'
            {where}
            ORDER BY i.year DESC, i.id DESC
            LIMIT 500
            """,
            params,
        ).fetchall()
        return [dict(row) for row in rows]


def extend_invoice_due_dates(actor_user_id: int, invoice_ids: list[int], due_date: str) -> dict:
    try:
        parsed = date.fromisoformat(due_date)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Due date must use YYYY-MM-DD") from exc
    if parsed < date.today():
        raise HTTPException(status_code=422, detail="Extended due date cannot be in the past")
    placeholders = ",".join("?" for _ in invoice_ids)
    with get_db() as db:
        cursor = db.execute(f"UPDATE invoices SET due_date=?, status=CASE WHEN status='Overdue' THEN 'Pending' ELSE status END WHERE id IN ({placeholders}) AND status != 'Paid'", [due_date, *invoice_ids])
        updated = cursor.rowcount
    audit(actor_user_id, "payment_due_date_extended", "invoice", ",".join(map(str, invoice_ids)), {"due_date": due_date, "updated": updated})
    return {"status": "updated", "updated": updated, "due_date": due_date}


def analytics() -> dict:
    rows = list_admin_payments()
    paid = [row for row in rows if row["status"] == "Paid"]
    pending = [row for row in rows if row["status"] == "Pending"]
    overdue = [row for row in rows if row["status"] == "Overdue"]
    return {
        "totalInvoices": len(rows),
        "paidStudents": len(paid),
        "pendingStudents": len(pending),
        "overdueStudents": len(overdue),
        "monthlyCollection": sum(row["amount"] + row["fine"] for row in paid),
        "totalOutstanding": sum(row["amount"] + row["fine"] for row in pending + overdue),
        "collectionPercent": round((len(paid) / len(rows)) * 100) if rows else 0,
    }
