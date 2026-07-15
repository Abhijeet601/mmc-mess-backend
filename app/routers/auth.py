from fastapi import APIRouter, HTTPException, status

from .. import repository
from ..poetic_integration import check_hostel_fee_payment_status
from ..schemas import LoginRequest, LoginResponse
from ..security import create_token, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest):
    """
    Student login with hostel fee verification from Poetic Reflection.
    
    For student portal:
    - Verify credentials in Mess ERP database
    - Check hostel fee payment status in Poetic Reflection database
    - Only allow login if fee status is PAID
    
    For admin/super-admin portal:
    - Standard credentials check only
    """
    user = repository.get_user_by_login_id(payload.login_id.strip())
    if not user or user["role"] != payload.portal or not verify_password(payload.password, user["password_hash"]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid login ID or password")
    
    # For student portal, verify hostel fee payment from Poetic Reflection
    if payload.portal == "student":
        if not user.get("student_id"):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, 
                detail="Student profile not linked properly. Contact administrator."
            )
        
        # Get student registration number from Mess ERP database
        student = repository.get_student(user["student_id"])
        if not student:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, 
                detail="Student profile not found."
            )
        
        registration_number = student.get("registration_number")
        if not registration_number:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, 
                detail="Student registration number not found. Contact administrator."
            )
        
        # Check hostel fee payment status from Poetic Reflection
        fee_status = check_hostel_fee_payment_status(registration_number)
        
        if not fee_status["eligible"]:
            if fee_status["status"] == "NOT_FOUND":
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED, 
                    detail="Student not found in Poetic Reflection system."
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN, 
                    detail=f"Hostel fee not paid. Current status: {fee_status['status']}. Please complete payment to access Mess ERP."
                )
    
    token = create_token({"user_id": user["id"], "role": user["role"], "student_id": user["student_id"]})
    safe_user = {
        "id": user["id"],
        "login_id": user["login_id"],
        "role": user["role"],
        "name": user["name"],
        "email": user["email"],
        "student_id": user["student_id"],
    }
    repository.audit(user["id"], "login", "user", str(user["id"]), user["role"])
    return {"token": token, "role": user["role"], "user": safe_user}

