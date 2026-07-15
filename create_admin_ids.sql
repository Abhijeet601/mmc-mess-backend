USE mess;

INSERT INTO users (login_id, password_hash, role, name, email, active)
VALUES (
  'SUPERADMIN001',
  'pbkdf2_sha256$0HBG76VjQ3GdTH3dXCJviA==$3sjHuf0MvRPKweDONY6cRugk9PNPrtI8bS9mj4In0Ac=',
  'super-admin',
  'Super Admin',
  'superadmin@mess.local',
  1
)
ON DUPLICATE KEY UPDATE
  password_hash = VALUES(password_hash),
  role = VALUES(role),
  name = VALUES(name),
  email = VALUES(email),
  active = 1;

INSERT INTO users (login_id, password_hash, role, name, email, active)
VALUES (
  'ADMIN001',
  'pbkdf2_sha256$LI6r4/8x+9CY/C3TlIBuzQ==$0Hw3V5GvPrBUPOa6Nm5tqUb6zrbYGqhJKx988efQ96o=',
  'admin',
  'Mess Admin',
  'admin@mess.local',
  1
)
ON DUPLICATE KEY UPDATE
  password_hash = VALUES(password_hash),
  role = VALUES(role),
  name = VALUES(name),
  email = VALUES(email),
  active = 1;
