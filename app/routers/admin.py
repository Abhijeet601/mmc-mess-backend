from fastapi import APIRouter, Depends, Query

from .. import repository
from ..db import get_db, row_to_dict
from ..schemas import ConfigUpdateRequest, ExtendDueDateRequest, MarkPaidRequest, ReminderRequest, StudentCreateRequest, UserCreateRequest
from ..security import hash_password
from ..security import require_auth, require_roles

router = APIRouter(prefix="/admin", tags=["admin"])


@router.post("/students")
def create_student(payload: StudentCreateRequest, user=Depends(require_auth)):
    require_roles(user, {"admin", "super-admin"})
    with get_db() as db:
        cursor = db.execute(
            """
            INSERT INTO students (
              admission_number, registration_number, name, email, mobile, hostel,
              room_number, course, academic_year, photo_url
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payload.admission_number,
                payload.registration_number,
                payload.name,
                payload.email,
                payload.mobile,
                payload.hostel,
                payload.room_number,
                payload.course,
                payload.academic_year,
                payload.photo_url,
            ),
        )
        student = row_to_dict(db.execute("SELECT * FROM students WHERE id = ?", (cursor.lastrowid,)).fetchone())
    repository.audit(user["user_id"], "student_created", "student", str(student["id"]), payload.registration_number)
    return student


@router.post("/users")
def create_user(payload: UserCreateRequest, user=Depends(require_auth)):
    require_roles(user, {"super-admin"})
    with get_db() as db:
        cursor = db.execute(
            """
            INSERT INTO users (login_id, password_hash, role, name, email, student_id, active)
            VALUES (?, ?, ?, ?, ?, ?, 1)
            """,
            (
                payload.login_id,
                hash_password(payload.password),
                payload.role,
                payload.name,
                payload.email,
                payload.student_id,
            ),
        )
        created = row_to_dict(db.execute("SELECT id, login_id, role, name, email, student_id, active FROM users WHERE id = ?", (cursor.lastrowid,)).fetchone())
    repository.audit(user["user_id"], "user_created", "user", str(created["id"]), payload.role)
    return created


@router.get("/payments")
def payments(
    status: str | None = Query(default=None),
    hostel: str | None = Query(default=None),
    search: str | None = Query(default=None),
    user=Depends(require_auth),
):
    require_roles(user, {"admin", "super-admin"})
    return {"payments": repository.list_admin_payments(status, hostel, search)}


@router.get("/analytics")
def payment_analytics(user=Depends(require_auth)):
    require_roles(user, {"admin", "super-admin"})
    return repository.analytics()


@router.get("/dashboard")
def dashboard(user=Depends(require_auth)):
    require_roles(user, {"admin", "super-admin"})
    return repository.attendance_dashboard()


@router.post("/payments/mark-paid")
def mark_paid(payload: MarkPaidRequest, user=Depends(require_auth)):
    require_roles(user, {"admin", "super-admin"})
    return repository.admin_mark_paid(user["user_id"], payload.invoice_id, payload.payment_mode, payload.transaction_id, payload.amount, payload.payment_date, payload.remarks, payload.receipt_url)


@router.post("/payments/extend-due-date")
def extend_due_date(payload: ExtendDueDateRequest, user=Depends(require_auth)):
    require_roles(user, {"admin", "super-admin"})
    return repository.extend_invoice_due_dates(user["user_id"], payload.invoice_ids, payload.due_date)


@router.post("/reminders")
def send_reminder(payload: ReminderRequest, user=Depends(require_auth)):
    require_roles(user, {"admin", "super-admin"})
    invoice = repository.get_invoice(payload.invoice_id)
    with get_db() as db:
        db.execute(
            "INSERT INTO reminders (invoice_id, student_id, channel, sent_by) VALUES (?, ?, ?, ?)",
            (payload.invoice_id, invoice["student_id"], payload.channel, user["user_id"]),
        )
    repository.audit(user["user_id"], "reminder_sent", "invoice", str(payload.invoice_id), payload.channel)
    return {"status": "Sent"}


@router.get("/config")
def get_config(user=Depends(require_auth)):
    require_roles(user, {"admin", "super-admin"})
    return repository.get_payment_config()


@router.patch("/config")
def update_config(payload: ConfigUpdateRequest, user=Depends(require_auth)):
    require_roles(user, {"super-admin"})
    data = payload.model_dump(exclude_none=True)
    bool_fields = {"razorpay_enabled", "ccavenue_enabled", "demo_gateway_enabled", "cash_enabled", "bank_transfer_enabled"}
    for key in bool_fields.intersection(data):
        data[key] = int(data[key])
    if not data:
        return repository.get_payment_config()
    assignments = ", ".join(f"{key} = ?" for key in data)
    params = list(data.values())
    with get_db() as db:
        db.execute(f"UPDATE payment_config SET {assignments}, updated_at = CURRENT_TIMESTAMP WHERE id = 1", params)
        updated = row_to_dict(db.execute("SELECT * FROM payment_config WHERE id = 1").fetchone())
    repository.audit(user["user_id"], "payment_config_updated", "payment_config", "1", ",".join(data.keys()))
    return updated
