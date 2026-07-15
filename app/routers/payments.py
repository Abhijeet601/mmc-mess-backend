from fastapi import APIRouter, Depends, HTTPException, status

from .. import repository
from ..schemas import CheckoutRequest, DemoConfirmRequest
from ..security import require_auth, require_roles

router = APIRouter(prefix="/payments", tags=["payments"])


@router.get("/me")
def my_payments(user=Depends(require_auth)):
    require_roles(user, {"student"})
    student_id = user.get("student_id")
    if not student_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Student ID is not linked to this login")
    student = repository.get_student(student_id)
    if not student:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found")
    repository.ensure_student_invoice(student_id)
    invoices = repository.list_student_invoices(student_id)
    unpaid = [row for row in invoices if row["status"] != "Paid"]
    paid = [row for row in invoices if row["status"] == "Paid"]
    return {
        "student": student,
        "current": invoices[0] if invoices else None,
        "invoices": invoices,
        "summary": {
            "totalPaid": sum(row["amount"] + row["fine"] for row in paid),
            "pendingAmount": sum(row["amount"] for row in unpaid),
            "lateFine": sum(row["fine"] for row in unpaid),
            "totalOutstanding": sum(row["amount"] + row["fine"] for row in unpaid),
            "lastPayment": paid[0] if paid else None,
        },
        "config": repository.get_payment_config(),
    }


@router.post("/checkout")
def checkout(payload: CheckoutRequest, user=Depends(require_auth)):
    require_roles(user, {"student"})
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Student payments are disabled. Contact the mess administrator.")


@router.post("/demo/confirm")
def confirm_demo(payload: DemoConfirmRequest, user=Depends(require_auth)):
    require_roles(user, {"student"})
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Student payments are disabled. Contact the mess administrator.")
