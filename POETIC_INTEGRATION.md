# Poetic Reflection Integration Guide

This document describes the integration between Mess ERP and Poetic Reflection master student database.

## Overview

**Poetic Reflection** is the master hostel student database containing:
- Student profile data (ID, name, course, hostel, room, etc.)
- Hostel fee payment status

**Mess ERP** contains:
- Student meal QR codes
- Meal attendance records
- Mess fee invoices and payments
- Meal menus
- Scanner activity logs

## Data Flow

### Login Flow (Student)
```
Student Login Form
    ↓
Authenticate against Mess ERP database (credentials)
    ↓
Fetch student registration number from Mess ERP
    ↓
Query Poetic Reflection for hostel fee payment status
    ↓
If PAID → Allow login & create JWT token
If NOT PAID → Deny access (HTTP 403)
If NOT FOUND → Deny access (HTTP 401)
```

### Profile Sync (Optional)
Student profile data can be synced from Poetic Reflection to Mess ERP:
- Name, email, mobile
- Course, semester, department, academic year
- Hostel, room number
- Photo URL

## Environment Variables

Add these to your Railway environment for Poetic Reflection connectivity:

### Connection to Poetic Reflection (Read-Only)
```env
# Host/Port of Poetic Reflection MySQL (via TCP Proxy)
POETIC_HOST=<poetic-mysql-tcp-proxy-host>
POETIC_PORT=<poetic-mysql-tcp-proxy-port>

# Credentials for read-only user on Poetic Reflection
POETIC_MYSQLUSER=<read-only-username>
POETIC_MYSQLPASSWORD=<read-only-password>

# Poetic Reflection database name
POETIC_MYSQLDATABASE=<database-name>
```

### Legacy/Alternative Names (auto-detected)
```env
POETIC_MYSQLHOST=<host>
POETIC_MYSQLPORT=<port>
```

## Setting Up Read-Only Access to Poetic Reflection

### Step 1: Enable TCP Proxy on Poetic Reflection MySQL
In the **Poetic Reflection project**:
1. Open the MySQL service
2. Go to **Networking** tab
3. Enable **TCP Proxy** (should be enabled by default)
4. Note the public host and port (e.g., `poetic-mysql-tcp-proxy.up.railway.app:12345`)

### Step 2: Create Read-Only Database User
Connect to Poetic Reflection MySQL and create a read-only user:

```sql
-- Create read-only user (run this in Poetic Reflection)
CREATE USER 'mess_erp_reader'@'%' IDENTIFIED BY 'your-secure-password';

-- Grant SELECT-only permissions
GRANT SELECT ON poetic_reflection.* TO 'mess_erp_reader'@'%';

-- Verify permissions
SHOW GRANTS FOR 'mess_erp_reader'@'%';

-- Apply changes
FLUSH PRIVILEGES;
```

### Step 3: Configure Mess ERP Variables
In the **Mess ERP project** (zooming-simplicity):
1. Open **mmc-mess-backend** service
2. Go to **Variables** tab
3. Add:
   ```
   POETIC_HOST = poetic-mysql-tcp-proxy.up.railway.app
   POETIC_PORT = 12345
   POETIC_MYSQLUSER = mess_erp_reader
   POETIC_MYSQLPASSWORD = your-secure-password
   POETIC_MYSQLDATABASE = poetic_reflection
   ```

### Step 4: Deploy
Push the code changes and deploy. The backend will now:
- Read student hostel fee status from Poetic Reflection during login
- Block login for students with unpaid hostel fees
- Allow login only for students with PAID status

## Database Schemas

### Poetic Reflection (Expected)
```sql
CREATE TABLE students (
    id INT PRIMARY KEY,
    name VARCHAR(150),
    registration_number VARCHAR(100) UNIQUE,
    admission_number VARCHAR(100),
    email VARCHAR(150),
    mobile VARCHAR(20),
    course VARCHAR(150),
    semester VARCHAR(40),
    department VARCHAR(120),
    academic_year VARCHAR(50),
    hostel VARCHAR(120),
    room_number VARCHAR(40),
    photo_url TEXT,
    hostel_fee_status ENUM('PAID', 'PENDING', 'UNPAID', 'FAILED'),
    active TINYINT DEFAULT 1
);
```

**Note:** Adjust the schema queries in `app/poetic_integration.py` if your Poetic Reflection database structure differs.

### Mess ERP (Existing)
Tables remain unchanged:
- `students` (local copy for Mess ERP specific fields)
- `users` (credentials)
- `invoices` (mess fees)
- `payments` (mess payments)
- `meal_qr_codes`
- `meal_attendance`
- `meal_menus`
- `scanner_logs`

## Query Examples

### Check if student can login (from code)
```python
from app.poetic_integration import check_hostel_fee_payment_status

result = check_hostel_fee_payment_status("REG123456")
# Returns:
# {
#     'eligible': True,           # Only True if PAID
#     'status': 'PAID',           # Current fee status
#     'student_id': 1,
#     'student_name': 'John Doe',
#     'hostel': 'Boys Hostel A',
#     'room_number': '101',
#     'payment_status': 'PAID'
# }
```

## Security Notes

✅ **READ-ONLY**: Only `SELECT` queries are allowed to Poetic Reflection
✅ **No Write Access**: Mess ERP cannot modify Poetic Reflection data
✅ **No Delete Access**: Separate read-only database user with minimal permissions
✅ **Audit Logging**: Login attempts are logged in Mess ERP audit table
✅ **Separate Databases**: Mess data is isolated in its own database

## Error Handling

### Student Login Errors

| Error | HTTP Status | Meaning |
|-------|-------------|---------|
| Invalid login ID or password | 401 | Credentials don't match |
| Student profile not linked | 401 | student_id missing in Mess ERP |
| Student not found in Poetic | 401 | Registration number not in Poetic |
| Hostel fee not paid | 403 | Status is PENDING/UNPAID/FAILED |
| Unable to verify fee status | 503 | Database connection error |

## Troubleshooting

### "Unable to connect to Poetic Reflection"
- Check TCP Proxy is enabled on Poetic MySQL
- Verify host/port environment variables
- Verify read-only user exists and has permissions
- Check firewall allows outbound connection

### "Student not found in Poetic"
- Verify registration_number in Mess ERP matches Poetic Reflection
- Ensure student is marked active in Poetic

### "Access denied for user"
- Verify credentials in environment variables
- Ensure user has SELECT permission on all needed tables
- Check password doesn't contain special characters requiring escaping

## Future Enhancements

1. **Student Profile Sync**: Periodically sync student data from Poetic to Mess ERP
2. **Fee Status Webhook**: Receive fee payment updates from Poetic Reflection
3. **Admin Dashboard**: Show fee collection vs. Mess ERP login access alignment
4. **Caching**: Cache fee status for 5-10 minutes to reduce database queries

