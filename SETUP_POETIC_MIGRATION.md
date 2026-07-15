# Poetic Reflection Data Migration Setup

This guide walks you through migrating all student data from Poetic Reflection to Mess ERP.

## Architecture

```
Poetic Reflection Project           zooming-simplicity Project
(Master Data)                       (Mess ERP)
┌──────────────────┐               ┌──────────────────┐
│   MySQL Server   │               │   MySQL Server   │
│  (students data) │               │   (mess data)    │
└────────┬─────────┘               └────────┬─────────┘
         │                                  │
         │ (READ-ONLY via TCP Proxy)        │ (READ/WRITE)
         │                                  │
         └──────────────────┬───────────────┘
                           │
                   mmc-mess-backend
                   (FastAPI App)
                           │
         ┌─────────────────┼─────────────────┐
         │                 │                 │
    During Login:      Student Data:    Mess Operations:
    Check fee status   (synced from     QR codes,
    from Poetic        Poetic)          attendance,
                                        fees, meals
```

## Step 1: Enable TCP Proxy on Poetic Reflection MySQL

In the **Poetic Reflection project**:

1. Go to **MySQL service**
2. Click **Networking** tab
3. Ensure **TCP Proxy** is enabled (toggle ON if needed)
4. **Copy the public host and port** (e.g., `poetic-mysql-tcp-12345.up.railway.app:12345`)

## Step 2: Create Read-Only User in Poetic Reflection

Connect to Poetic Reflection MySQL and run:

```sql
-- Create read-only user
CREATE USER 'mess_erp_reader'@'%' IDENTIFIED BY 'your-secure-password-here';

-- Grant SELECT-only permissions
GRANT SELECT ON poetic_reflection.* TO 'mess_erp_reader'@'%';

-- Apply changes
FLUSH PRIVILEGES;

-- Verify
SHOW GRANTS FOR 'mess_erp_reader'@'%';
```

## Step 3: Add Environment Variables to Mess ERP

In the **mmc-mess-backend service** on Railway, add these variables:

```
POETIC_HOST = <tcp-proxy-host from step 1>
POETIC_PORT = <tcp-proxy-port from step 1>
POETIC_MYSQLUSER = mess_erp_reader
POETIC_MYSQLPASSWORD = <password from step 2>
POETIC_MYSQLDATABASE = poetic_reflection
```

Example:
```
POETIC_HOST = poetic-mysql-tcp-12345.up.railway.app
POETIC_PORT = 12345
POETIC_MYSQLUSER = mess_erp_reader
POETIC_MYSQLPASSWORD = MySecurePassword123!
POETIC_MYSQLDATABASE = poetic_reflection
```

## Step 4: Deploy Backend

Once variables are set, deploy the mmc-mess-backend service to activate the changes.

## Step 5: Run Migration Script

### Option A: Run Locally (Recommended)

Clone the repo and run the migration script locally:

```bash
# Clone repo
git clone https://github.com/Abhijeet601/mmc-mess-backend.git
cd mmc-mess-backend

# Install dependencies
pip install -r requirements.txt

# Set environment variables (Linux/Mac)
export MYSQLHOST=<mess-mysql-host>
export MYSQLPORT=3306
export MYSQLUSER=root
export MYSQLPASSWORD=<mess-mysql-password>
export MYSQLDATABASE=mess

export POETIC_HOST=<poetic-tcp-proxy-host>
export POETIC_PORT=<poetic-tcp-proxy-port>
export POETIC_MYSQLUSER=mess_erp_reader
export POETIC_MYSQLPASSWORD=<poetic-read-only-password>
export POETIC_MYSQLDATABASE=poetic_reflection

# Run migration
python migrate_poetic_students.py
```

Or on Windows:
```powershell
$env:MYSQLHOST = "<mess-mysql-host>"
$env:MYSQLPORT = "3306"
$env:MYSQLUSER = "root"
$env:MYSQLPASSWORD = "<mess-mysql-password>"
$env:MYSQLDATABASE = "mess"

$env:POETIC_HOST = "<poetic-tcp-proxy-host>"
$env:POETIC_PORT = "<poetic-tcp-proxy-port>"
$env:POETIC_MYSQLUSER = "mess_erp_reader"
$env:POETIC_MYSQLPASSWORD = "<poetic-read-only-password>"
$env:POETIC_MYSQLDATABASE = "poetic_reflection"

python migrate_poetic_students.py
```

### Option B: Run in Railway Container (Advanced)

SSH into the mmc-mess-backend container and run:

```bash
cd /app
python migrate_poetic_students.py
```

## How the Migration Works

1. **Connects to Poetic Reflection** using the read-only user
2. **Fetches all active students** with their profile data
3. **Checks if each student exists** in Mess ERP by registration_number
4. **Inserts new students** or **updates existing ones**
5. **Commits all changes** to Mess ERP database

### Data Migrated

From Poetic Reflection → To Mess ERP `students` table:
- `registration_number` (UNIQUE KEY)
- `admission_number`
- `name`
- `email`
- `mobile`
- `course`
- `semester`
- `department`
- `academic_year`
- `hostel`
- `room_number`
- `photo_url`

## What Happens After Migration

✅ **Students table in Mess ERP** is populated with all Poetic Reflection students
✅ **Student login** checks hostel fee status from Poetic Reflection (read-only)
✅ **Meal attendance** is tracked per-student in Mess ERP
✅ **Mess invoices** are generated per-student in Mess ERP
✅ **Poetic Reflection** remains the source of truth for fee status

## Verification

After migration, verify:

```sql
-- In Mess ERP MySQL, check student count
SELECT COUNT(*) as total_students FROM students WHERE active = 1;

-- Check a few records
SELECT id, registration_number, name, hostel, room_number FROM students LIMIT 5;

-- Verify no duplicates
SELECT registration_number, COUNT(*) as count 
FROM students 
GROUP BY registration_number 
HAVING count > 1;
```

## Troubleshooting

### "Connection refused" error
- Verify TCP Proxy is enabled on Poetic Reflection MySQL
- Check POETIC_HOST and POETIC_PORT are correct
- Ensure firewall allows outbound connections

### "Access denied for user" error
- Verify `mess_erp_reader` user exists in Poetic Reflection
- Check password matches POETIC_MYSQLPASSWORD
- Ensure user has SELECT permission: `SHOW GRANTS FOR 'mess_erp_reader'@'%';`

### "Column 'X' doesn't exist" error
- Your Poetic Reflection schema may differ
- Edit `migrate_poetic_students.py` and adjust the SELECT query
- Or edit the INSERT query if Mess ERP schema is different

### "Students table doesn't exist" error
- Run `python app/seed_admin.py` first to create schema
- Or ensure the Mess ERP database is initialized

## Rollback

If something goes wrong:

```sql
-- Delete all migrated students (careful!)
DELETE FROM students WHERE registration_number IS NOT NULL;

-- Or delete specific students
DELETE FROM students WHERE active = 1 LIMIT 100;
```

## Re-running Migration

Safe to run multiple times. The script will:
- Skip existing students (by registration_number)
- Update data if it's been changed in Poetic Reflection
- Add new students if they've been added to Poetic Reflection

## Next: Sync Updates (Optional)

To keep student data in sync with Poetic Reflection updates:

```bash
# Run migration daily via cron
0 2 * * * cd /path/to/repo && python migrate_poetic_students.py
```

Or set up a webhook to trigger migration when Poetic Reflection students change.

