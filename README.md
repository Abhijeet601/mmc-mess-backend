# Mess Attendance Backend

FastAPI backend for real login IDs and mess fee payments.

## Run

```powershell
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
python -m app.seed_admin --login-id SUPERADMIN001 --password "SuperAdmin@123" --role super-admin --name "Super Admin"
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

## Real IDs

The backend does not seed demo students or payments. Create users and student records with your real admission/registration IDs through API/database import before production use.

Existing local development logins:

| Portal | Login ID | Password |
| --- | --- | --- |
| Super Admin | `SUPERADMIN001` | `SuperAdmin@123` |
| Admin | `ADMIN001` | `Admin@123` |
| Student | `STUDENT001` | `Student@123` |

Change these passwords before deployment.

Use `POST /api/auth/login` with:

```json
{
  "portal": "super-admin",
  "login_id": "SUPERADMIN001",
  "password": "SuperAdmin@123"
}
```

## Hostel ERP student login

When `HOSTEL_ERP_API_URL` is configured, all `student` portal logins are verified by
the Hostel ERP backend. A student is allowed into the mess portal only when:

- the Hostel ERP login ID/password is valid;
- the Hostel ERP account is active;
- `hostel_payment_status` is verified as `paid` (or another successful gateway status);
- a hostel is allotted to the student.

The mess backend creates or refreshes its local student profile after successful
verification. The Hostel ERP password and access token are never stored in the mess
database. Admin and super-admin logins continue to use the local mess `users` table.

Set these variables on the **mess backend service** in Railway:

```env
HOSTEL_ERP_API_URL=https://hostel-erp-backend-production.up.railway.app
HOSTEL_ERP_TIMEOUT_SECONDS=20
FRONTEND_ORIGINS=https://mmc-mess-frontend.vercel.app
```

Keep the mess backend connected to its own MySQL service using its existing
`MYSQLHOST`, `MYSQLPORT`, `MYSQLUSER`, `MYSQLPASSWORD`, and `MYSQLDATABASE`
variables. Do not replace those variables with the Hostel ERP database credentials.

If both backends are later moved into the same Railway project and environment, the
public URL can be replaced by the Hostel ERP service's private Railway URL.

Student login request:

```json
{
  "portal": "student",
  "login_id": "student email, mobile, or Hostel ERP student ID",
  "password": "Hostel ERP password"
}
```
