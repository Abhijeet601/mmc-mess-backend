import hashlib
import json
import secrets
import logging
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException

from .. import repository
from ..db import get_db, row_to_dict
from ..schemas import MealMenuUpsert, ProfileChangeCreate, ProfileChangeDecision, QRConsumeRequest
from ..security import require_auth, require_roles

router = APIRouter(tags=["student portal"])
logger = logging.getLogger("mess.scanner")
IST = ZoneInfo("Asia/Kolkata")
PROFILE_FIELDS = {"name", "email", "mobile", "hostel", "room_number", "course", "academic_year", "photo_url"}


@router.get("/student/me")
def student_me(user=Depends(require_auth)):
    require_roles(user, {"student"})
    student = repository.get_student(user.get("student_id"))
    if not student:
        raise HTTPException(404, "Student profile not found")
    return student


@router.post("/student/qr")
def issue_qr(user=Depends(require_auth)):
    require_roles(user, {"student"})
    if not user.get("student_id"):
        raise HTTPException(400, "Student account is not linked")
    token = secrets.token_urlsafe(32)
    digest = hashlib.sha256(token.encode()).hexdigest()
    expires = datetime.utcnow() + timedelta(seconds=25)
    with get_db() as db:
        db.execute("DELETE FROM qr_tokens WHERE student_id = ? AND used_at IS NULL", (user["student_id"],))
        db.execute("INSERT INTO qr_tokens (token_hash, student_id, user_id, expires_at) VALUES (?, ?, ?, ?)", (digest, user["student_id"], user["user_id"], expires))
    return {"token": token, "expires_at": expires.isoformat() + "Z", "ttl_seconds": 25}


def _current_meal(now: datetime) -> str | None:
    minute = now.hour * 60 + now.minute
    for name, start, end in (("Breakfast", 7 * 60, 10 * 60), ("Lunch", 12 * 60, 15 * 60), ("Snacks", 16 * 60, 18 * 60), ("Dinner", 19 * 60, 22 * 60)):
        if start <= minute < end:
            return name
    return None


@router.get("/scanner/status")
def scanner_status(user=Depends(require_auth)):
    require_roles(user, {"admin", "super-admin"})
    now = datetime.now(IST)
    return {"meal": _current_meal(now), "server_time": now.isoformat(), "timezone": "Asia/Kolkata"}


@router.post("/scanner/consume")
def consume_qr(payload: QRConsumeRequest, user=Depends(require_auth)):
    require_roles(user, {"admin", "super-admin"})
    digest = hashlib.sha256(payload.token.encode()).hexdigest()
    now_ist = datetime.now(IST)
    meal = payload.meal or _current_meal(now_ist)
    if not meal:
        raise HTTPException(422, "No meal scanning window is currently active")
    try:
        with get_db() as db:
            row = row_to_dict(db.execute("SELECT * FROM qr_tokens WHERE token_hash = ? FOR UPDATE", (digest,)).fetchone())
            if not row:
                raise HTTPException(400, "Invalid Mess QR")
            if row["used_at"] is not None:
                raise HTTPException(409, "QR Already Used – This code cannot be accepted again")
            if row["expires_at"] <= datetime.utcnow():
                raise HTTPException(410, "QR Expired – Ask Student to show the latest live QR")
            student = row_to_dict(db.execute("SELECT * FROM students WHERE id = ? AND active = 1", (row["student_id"],)).fetchone())
            if not student:
                raise HTTPException(403, "Student mess account is inactive")
            existing = db.execute("SELECT id FROM meal_attendance WHERE student_id=? AND meal_date=? AND meal_type=?", (student["id"], now_ist.date(), meal)).fetchone()
            if existing:
                raise HTTPException(409, "Meal Attendance Already Marked")
            cursor = db.execute("INSERT INTO meal_attendance (student_id, meal_date, meal_type, scanned_by, qr_token_id) VALUES (?, ?, ?, ?, ?)", (student["id"], now_ist.date(), meal, user["user_id"], row["id"]))
            db.execute("UPDATE qr_tokens SET used_at = CURRENT_TIMESTAMP WHERE id = ? AND used_at IS NULL", (row["id"],))
        logger.info("attendance_marked attendance_id=%s student_id=%s meal=%s scanner_user=%s", cursor.lastrowid, student["id"], meal, user["user_id"])
        repository.audit(user["user_id"], "meal_attendance_marked", "meal_attendance", str(cursor.lastrowid), {"student_id": student["id"], "meal": meal, "qr_token_id": row["id"]})
        return {"status": "MARKED", "attendance_id": cursor.lastrowid, "student": student, "meal": meal, "scan_date": now_ist.date(), "scan_time": now_ist.strftime("%H:%M:%S"), "scanned_at": now_ist.isoformat()}
    except HTTPException as exc:
        logger.warning("scan_rejected reason=%s scanner_user=%s", exc.detail, user.get("user_id"))
        raise
    except Exception:
        logger.exception("scanner_database_failure scanner_user=%s", user.get("user_id"))
        raise HTTPException(500, "Unable to mark attendance")


@router.get("/student/profile-change-requests")
def my_requests(user=Depends(require_auth)):
    require_roles(user, {"student"})
    with get_db() as db:
        rows = db.execute("SELECT * FROM profile_change_requests WHERE student_id = ? ORDER BY created_at DESC", (user["student_id"],)).fetchall()
    return {"requests": [{**dict(r), "changes": json.loads(r["changes_json"])} for r in rows]}


@router.post("/student/profile-change-requests")
def request_profile_change(payload: ProfileChangeCreate, user=Depends(require_auth)):
    require_roles(user, {"student"})
    changes = {k: v for k, v in payload.changes.items() if k in PROFILE_FIELDS}
    if not changes:
        raise HTTPException(400, "No editable profile fields supplied")
    with get_db() as db:
        pending = db.execute("SELECT id FROM profile_change_requests WHERE student_id = ? AND status = 'Pending Approval'", (user["student_id"],)).fetchone()
        if pending:
            raise HTTPException(409, "A profile change request is already pending")
        cursor = db.execute("INSERT INTO profile_change_requests (student_id, requested_by, changes_json) VALUES (?, ?, ?)", (user["student_id"], user["user_id"], json.dumps(changes)))
    repository.audit(user["user_id"], "profile_change_requested", "profile_change_request", str(cursor.lastrowid), changes)
    return {"id": cursor.lastrowid, "status": "Pending Approval"}


@router.get("/admin/profile-change-requests")
def profile_requests(user=Depends(require_auth)):
    require_roles(user, {"admin", "super-admin"})
    with get_db() as db:
        rows = db.execute("SELECT r.*, s.name, s.registration_number, s.email, s.mobile, s.hostel, s.room_number, s.course, s.academic_year FROM profile_change_requests r JOIN students s ON s.id=r.student_id ORDER BY r.created_at DESC").fetchall()
    return {"requests": [{**dict(r), "changes": json.loads(r["changes_json"])} for r in rows]}


@router.post("/admin/profile-change-requests/{request_id}/decision")
def decide_profile_request(request_id: int, payload: ProfileChangeDecision, user=Depends(require_auth)):
    require_roles(user, {"admin", "super-admin"})
    with get_db() as db:
        req = row_to_dict(db.execute("SELECT * FROM profile_change_requests WHERE id = ? FOR UPDATE", (request_id,)).fetchone())
        if not req or req["status"] != "Pending Approval":
            raise HTTPException(409, "Request is missing or already reviewed")
        changes = json.loads(req["changes_json"])
        if payload.decision == "Approved":
            assignments = ", ".join(f"{key} = ?" for key in changes)
            db.execute(f"UPDATE students SET {assignments} WHERE id = ?", [*changes.values(), req["student_id"]])
        db.execute("UPDATE profile_change_requests SET status=?, reviewed_by=?, admin_note=?, reviewed_at=CURRENT_TIMESTAMP WHERE id=?", (payload.decision, user["user_id"], payload.admin_note, request_id))
    repository.audit(user["user_id"], f"profile_change_{payload.decision.lower()}", "profile_change_request", str(request_id), changes)
    return {"status": payload.decision}


@router.get("/meal-menus")
def menus(user=Depends(require_auth)):
    require_roles(user, {"student", "admin", "super-admin"})
    start = date.today() - timedelta(days=date.today().weekday())
    end = start + timedelta(days=6)
    with get_db() as db:
        rows = db.execute("SELECT * FROM meal_menus WHERE menu_date BETWEEN ? AND ? ORDER BY menu_date", (start, end)).fetchall()
    return {"week_start": start, "menus": [dict(r) for r in rows]}


@router.put("/admin/meal-menus")
def save_menu(payload: MealMenuUpsert, user=Depends(require_auth)):
    require_roles(user, {"admin", "super-admin"})
    with get_db() as db:
        db.execute("INSERT INTO meal_menus (menu_date, breakfast, lunch, snacks, dinner, updated_by) VALUES (?, ?, ?, ?, ?, ?) ON DUPLICATE KEY UPDATE breakfast=VALUES(breakfast), lunch=VALUES(lunch), snacks=VALUES(snacks), dinner=VALUES(dinner), updated_by=VALUES(updated_by)", (payload.menu_date, payload.breakfast, payload.lunch, payload.snacks, payload.dinner, user["user_id"]))
    repository.audit(user["user_id"], "meal_menu_updated", "meal_menu", payload.menu_date, payload.model_dump())
    return {"status": "saved"}
