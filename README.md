# Mess Attendance Backend

FastAPI backend for real login IDs and mess fee payments.

## Run

```powershell
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
python -m app.seed_admin --login-id SUPERADMIN001 --password "ChangeMe@123" --role super-admin --name "Super Admin"
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

## Real IDs

The backend does not seed demo students or payments. Create users and student records with your real admission/registration IDs through API/database import before production use.

Existing local development logins:

| Portal | Login ID | Password |
| --- | --- | --- |
| Super Admin | `SUPERADMIN001` | `ChangeMe@123` |
| Admin | `ADMIN001` | `Admin@123` |
| Student | `STUDENT001` | `Student@123` |

Change these passwords before deployment.

Use `POST /api/auth/login` with:

```json
{
  "portal": "super-admin",
  "login_id": "SUPERADMIN001",
  "password": "ChangeMe@123"
}
```
