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


def _latest_application(applications: list[dict]) -> dict:
    return max(
        applications,
        key=lambda item: (_text(item.get("updated_at") or item.get("created_at")), int(item.get("id") or 0)),
        default={},
    )


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

            hostel_student_id = int(login_data.get("student_id") or (login_data.get("user") or {}).get("id") or 0)
            if not hostel_student_id:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Hostel ERP did not return a student ID.",
                )

            headers = {"Authorization": f"Bearer {access_token}"}
            applications_response = client.get(
                f"{HOSTEL_ERP_API_URL}/applications",
                params={"student_id": hostel_student_id},
                headers=headers,
            )
            payments_response = client.get(
                f"{HOSTEL_ERP_API_URL}/payments",
                params={"student_id": hostel_student_id},
                headers=headers,
            )
            hostels_response = client.get(f"{HOSTEL_ERP_API_URL}/hostels", headers=headers)
            applications_response.raise_for_status()
            payments_response.raise_for_status()
            hostels_response.raise_for_status()
            applications = applications_response.json() or []
            payments = payments_response.json() or []
            hostels = hostels_response.json() or []
            application = _latest_application(applications)
            room_number = ""
            room_id = application.get("room_id")
            if room_id:
                try:
                    room_response = client.get(
                        f"{HOSTEL_ERP_API_URL}/rooms/{int(room_id)}/beds",
                        headers=headers,
                    )
                    if room_response.is_success:
                        room_number = _text(room_response.json().get("room_number"))
                except (httpx.HTTPError, ValueError):
                    room_number = ""
    except HTTPException:
        raise
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Hostel ERP verification is temporarily unavailable. Please try again.",
        ) from exc

    hostel_paid = any(
        "hostel" in _text(payment.get("payment_type")).lower()
        and _text(payment.get("status")).lower() in PAID_STATUSES
        for payment in payments
    )
    if not hostel_paid:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Hostel fee payment is not verified. Mess login is unavailable.",
        )

    user = login_data.get("user") or {}
    registration_number = _text(
        user.get("student_code")
        or login_data.get("application_number")
        or application.get("student_code")
    )
    admission_number = _text(
        application.get("admission_id")
        or application.get("application_no")
        or registration_number
    )
    hostel_id = application.get("hostel_id")
    hostel_record = next(
        (item for item in hostels if int(item.get("id") or 0) == int(hostel_id or 0)),
        {},
    )
    hostel = _text(hostel_record.get("name"))
    if not hostel_student_id or not registration_number or not hostel:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Hostel ERP profile is incomplete. Student ID and hostel allocation are required.",
        )

    return VerifiedHostelStudent(
        hostel_student_id=hostel_student_id,
        registration_number=registration_number,
        admission_number=admission_number,
        name=_text(login_data.get("student_name") or user.get("name")) or "Student",
        email=_text(login_data.get("email") or user.get("email")) or None,
        mobile=_text(login_data.get("mobile") or user.get("mobile") or user.get("mobile_number")) or None,
        hostel=hostel,
        room_number=room_number or "Not allotted",
        course=_text(application.get("course") or user.get("course")) or None,
        academic_year=_text(application.get("session") or user.get("session")) or None,
    )
