"""Create or refresh the single non-production student used for scanner testing."""

from . import repository
from .db import get_db, init_db
from .security import hash_password


LOGIN_ID = "TESTSTUDENT001"
PASSWORD = "Test@123"
REGISTRATION_NUMBER = "TEST-REG-001"
ADMISSION_NUMBER = "TEST-ADM-001"


def main() -> None:
    init_db()
    with get_db() as db:
        existing = db.execute(
            "SELECT id FROM students WHERE registration_number = ?",
            (REGISTRATION_NUMBER,),
        ).fetchone()
        values = (
            ADMISSION_NUMBER,
            "Test Student",
            "test.student@mess.local",
            "+91 90000 00001",
            "Vaidehi Hostel",
            "T-101",
            "BCA",
            "Computer Applications",
            "1st Year",
            "Semester 1",
            "https://api.dicebear.com/7.x/initials/svg?seed=Test%20Student",
        )
        if existing:
            student_id = existing["id"]
            db.execute(
                """
                UPDATE students SET admission_number=?, name=?, email=?, mobile=?, hostel=?,
                  room_number=?, course=?, department=?, academic_year=?, semester=?, photo_url=?, active=1
                WHERE id=?
                """,
                (*values, student_id),
            )
        else:
            cursor = db.execute(
                """
                INSERT INTO students (
                  admission_number, registration_number, name, email, mobile, hostel,
                  room_number, course, department, academic_year, semester, photo_url, active
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
                """,
                (ADMISSION_NUMBER, REGISTRATION_NUMBER, *values[1:]),
            )
            student_id = cursor.lastrowid

        db.execute(
            """
            INSERT INTO users (login_id, password_hash, role, name, email, student_id, active)
            VALUES (?, ?, 'student', ?, ?, ?, 1)
            ON DUPLICATE KEY UPDATE password_hash=VALUES(password_hash), role='student',
              name=VALUES(name), email=VALUES(email), student_id=VALUES(student_id), active=1
            """,
            (LOGIN_ID, hash_password(PASSWORD), "Test Student", "test.student@mess.local", student_id),
        )

    invoice = repository.ensure_student_invoice(student_id)
    print(f"Ready: {LOGIN_ID}; student_id={student_id}; invoice_id={invoice['id']}")


if __name__ == "__main__":
    main()
