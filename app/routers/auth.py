from fastapi import APIRouter, HTTPException, status

from .. import repository
from ..schemas import LoginRequest, LoginResponse
from ..security import create_token, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest):
    user = repository.get_user_by_login_id(payload.login_id.strip())
    if not user or user["role"] != payload.portal or not verify_password(payload.password, user["password_hash"]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid login ID or password")
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
