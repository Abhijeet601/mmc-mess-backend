from dataclasses import dataclass

import httpx
from fastapi import HTTPException, status

from .config import HOSTEL_ERP_API_URL, HOSTEL_ERP_TIMEOUT_SECONDS


PAID_STATUSES = {"paid", "success", "successful", "completed", "captured"}


@dataclass(frozen=True)
class VerifiedHostelStudent:
    hostel_student_id: int
    registration_number: str
    admission_number: str
    name: str
    email: str | None
    mobile: str | None
    hostel: str
    room_number: str
    course: str | None
    academic_year: str | None


def integration_enabled() -> bool:
    return bool(HOSTEL_ERP_API_URL)


def _text(value) -> str:
    return str(value or "").strip()


def authenticate_paid_student(identifier: str, password: str) -> VerifiedHostelStudent:
    if not integration_enabled():
        raise RuntimeError("HOSTEL_ERP_API_URL is not configured.")

    try:
        with httpx.Client(timeout=HOSTEL_ERP_TIMEOUT_SECONDS) as client:
            login_response = client.post(
                f"{HOSTEL_ERP_API_URL}/api/login",
                json={"email": identifier, "password": password},
            )
            if login_response.status_code in {400, 401, 403, 404, 422}:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid Hostel ERP login ID or password.",
                )
            login_response.raise_for_status()
            login_data = login_response.json()
            access_token = _text(login_data.get("access_token") or login_data.get("token"))
            if not access_token:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Hostel ERP did not return a login token.",
                )

            dashboard_response = client.get(
                f"{HOSTEL_ERP_API_URL}/api/dashboard",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            dashboard_response.raise_for_status()
            dashboard = dashboard_response.json()
    except HTTPException:
        raise
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Hostel ERP verification is temporarily unavailable. Please try again.",
        ) from exc

    hostel_payment_status = _text(dashboard.get("hostel_payment_status")).lower()
    if hostel_payment_status not in PAID_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Hostel fee payment is not verified. Mess login is unavailable.",
        )

    user = login_data.get("user") or {}
    summary = dashboard.get("summary") or {}
    hostel_student_id = int(login_data.get("student_id") or user.get("id") or 0)
    registration_number = _text(
        user.get("student_code")
        or login_data.get("application_number")
        or dashboard.get("student_code")
    )
    admission_number = _text(
        summary.get("admission_application_id")
        or dashboard.get("application_no")
        or dashboard.get("application_number")
        or registration_number
    )
    hostel = _text(dashboard.get("allocated_hostel") or dashboard.get("preferred_hostel"))
    if not hostel_student_id or not registration_number or not hostel:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Hostel ERP profile is incomplete. Student ID and hostel allocation are required.",
        )

    return VerifiedHostelStudent(
        hostel_student_id=hostel_student_id,
        registration_number=registration_number,
        admission_number=admission_number,
        name=_text(login_data.get("student_name") or user.get("name") or dashboard.get("name")) or "Student",
        email=_text(login_data.get("email") or user.get("email") or dashboard.get("email")) or None,
        mobile=_text(login_data.get("mobile") or user.get("mobile") or dashboard.get("mobile_number")) or None,
        hostel=hostel,
        room_number=_text(dashboard.get("room_number")) or "Not allotted",
        course=_text(user.get("course") or summary.get("course_name")) or None,
        academic_year=_text(user.get("session") or summary.get("session")) or None,
    )
