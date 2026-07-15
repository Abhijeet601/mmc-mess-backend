-- MySQL 8+ schema for Mess Attendance / Mess Fee Payment backend.
-- Create a database first, then run this file:
--   CREATE DATABASE mess CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
--   USE mess;
--   SOURCE backend/mysql_schema.sql;

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

CREATE TABLE IF NOT EXISTS students (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  admission_number VARCHAR(100) NOT NULL,
  registration_number VARCHAR(100) NOT NULL,
  name VARCHAR(150) NOT NULL,
  email VARCHAR(150) NULL,
  mobile VARCHAR(30) NULL,
  hostel VARCHAR(120) NOT NULL,
  room_number VARCHAR(40) NOT NULL,
  course VARCHAR(120) NULL,
  department VARCHAR(120) NULL,
  academic_year VARCHAR(40) NULL,
  semester VARCHAR(40) NULL,
  photo_url TEXT NULL,
  active TINYINT(1) NOT NULL DEFAULT 1,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_students_admission_number (admission_number),
  UNIQUE KEY uq_students_registration_number (registration_number),
  KEY idx_students_hostel_room (hostel, room_number),
  KEY idx_students_name (name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS users (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  login_id VARCHAR(100) NOT NULL,
  password_hash VARCHAR(255) NOT NULL,
  role ENUM('super-admin', 'admin', 'student') NOT NULL,
  name VARCHAR(150) NOT NULL,
  email VARCHAR(150) NULL,
  hostel_scope VARCHAR(120) NULL,
  student_id BIGINT UNSIGNED NULL,
  active TINYINT(1) NOT NULL DEFAULT 1,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_users_login_id (login_id),
  KEY idx_users_role (role),
  KEY idx_users_student_id (student_id),
  CONSTRAINT fk_users_student
    FOREIGN KEY (student_id) REFERENCES students(id)
    ON DELETE SET NULL
    ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS payment_config (
  id TINYINT UNSIGNED NOT NULL,
  monthly_fee INT UNSIGNED NOT NULL DEFAULT 3200,
  late_fine INT UNSIGNED NOT NULL DEFAULT 250,
  due_day TINYINT UNSIGNED NOT NULL DEFAULT 10,
  grace_period_days TINYINT UNSIGNED NOT NULL DEFAULT 5,
  receipt_prefix VARCHAR(40) NOT NULL DEFAULT 'MMC-MESS',
  academic_session VARCHAR(40) NOT NULL DEFAULT '2026-27',
  razorpay_enabled TINYINT(1) NOT NULL DEFAULT 1,
  ccavenue_enabled TINYINT(1) NOT NULL DEFAULT 1,
  demo_gateway_enabled TINYINT(1) NOT NULL DEFAULT 1,
  cash_enabled TINYINT(1) NOT NULL DEFAULT 1,
  bank_transfer_enabled TINYINT(1) NOT NULL DEFAULT 1,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  CONSTRAINT chk_payment_config_singleton CHECK (id = 1),
  CONSTRAINT chk_payment_config_due_day CHECK (due_day BETWEEN 1 AND 28)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

INSERT INTO payment_config (id)
VALUES (1)
ON DUPLICATE KEY UPDATE id = id;

CREATE TABLE IF NOT EXISTS invoices (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  student_id BIGINT UNSIGNED NOT NULL,
  month VARCHAR(20) NOT NULL,
  year SMALLINT UNSIGNED NOT NULL,
  amount INT UNSIGNED NOT NULL,
  fine INT UNSIGNED NOT NULL DEFAULT 0,
  due_date DATE NOT NULL,
  status ENUM('Paid', 'Pending', 'Overdue') NOT NULL DEFAULT 'Pending',
  receipt_no VARCHAR(80) NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_invoices_student_month_year (student_id, month, year),
  UNIQUE KEY uq_invoices_receipt_no (receipt_no),
  KEY idx_invoices_status (status),
  KEY idx_invoices_due_date (due_date),
  CONSTRAINT fk_invoices_student
    FOREIGN KEY (student_id) REFERENCES students(id)
    ON DELETE CASCADE
    ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS payments (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  invoice_id BIGINT UNSIGNED NOT NULL,
  student_id BIGINT UNSIGNED NOT NULL,
  amount INT UNSIGNED NOT NULL,
  fine INT UNSIGNED NOT NULL DEFAULT 0,
  payment_mode VARCHAR(40) NOT NULL,
  gateway VARCHAR(40) NOT NULL,
  transaction_id VARCHAR(120) NOT NULL,
  gateway_order_id VARCHAR(120) NOT NULL,
  status ENUM('Created', 'Success', 'Failed', 'PendingApproval') NOT NULL,
  gateway_response TEXT NULL,
  remarks TEXT NULL,
  receipt_url TEXT NULL,
  approved_by BIGINT UNSIGNED NULL,
  payment_date TIMESTAMP NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_payments_transaction_id (transaction_id),
  UNIQUE KEY uq_payments_gateway_order_id (gateway_order_id),
  KEY idx_payments_invoice_id (invoice_id),
  KEY idx_payments_student_id (student_id),
  KEY idx_payments_status (status),
  KEY idx_payments_payment_date (payment_date),
  CONSTRAINT fk_payments_invoice
    FOREIGN KEY (invoice_id) REFERENCES invoices(id)
    ON DELETE CASCADE
    ON UPDATE CASCADE,
  CONSTRAINT fk_payments_student
    FOREIGN KEY (student_id) REFERENCES students(id)
    ON DELETE CASCADE
    ON UPDATE CASCADE,
  CONSTRAINT fk_payments_approved_by
    FOREIGN KEY (approved_by) REFERENCES users(id)
    ON DELETE SET NULL
    ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS reminders (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  invoice_id BIGINT UNSIGNED NOT NULL,
  student_id BIGINT UNSIGNED NOT NULL,
  channel ENUM('Email', 'Dashboard', 'Email + Dashboard', 'SMS') NOT NULL,
  status VARCHAR(40) NOT NULL DEFAULT 'Sent',
  sent_by BIGINT UNSIGNED NULL,
  sent_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_reminders_invoice_id (invoice_id),
  KEY idx_reminders_student_id (student_id),
  KEY idx_reminders_sent_at (sent_at),
  CONSTRAINT fk_reminders_invoice
    FOREIGN KEY (invoice_id) REFERENCES invoices(id)
    ON DELETE CASCADE
    ON UPDATE CASCADE,
  CONSTRAINT fk_reminders_student
    FOREIGN KEY (student_id) REFERENCES students(id)
    ON DELETE CASCADE
    ON UPDATE CASCADE,
  CONSTRAINT fk_reminders_sent_by
    FOREIGN KEY (sent_by) REFERENCES users(id)
    ON DELETE SET NULL
    ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS audit_logs (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  actor_user_id BIGINT UNSIGNED NULL,
  action VARCHAR(120) NOT NULL,
  entity_type VARCHAR(80) NOT NULL,
  entity_id VARCHAR(120) NOT NULL,
  details TEXT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_audit_logs_actor_user_id (actor_user_id),
  KEY idx_audit_logs_entity (entity_type, entity_id),
  KEY idx_audit_logs_created_at (created_at),
  CONSTRAINT fk_audit_logs_actor
    FOREIGN KEY (actor_user_id) REFERENCES users(id)
    ON DELETE SET NULL
    ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS qr_tokens (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  token_hash CHAR(64) NOT NULL,
  student_id BIGINT UNSIGNED NOT NULL,
  user_id BIGINT UNSIGNED NOT NULL,
  expires_at TIMESTAMP NOT NULL,
  used_at TIMESTAMP NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id), UNIQUE KEY uq_qr_token_hash (token_hash),
  KEY idx_qr_student_expiry (student_id, expires_at),
  CONSTRAINT fk_qr_student FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
  CONSTRAINT fk_qr_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS profile_change_requests (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  student_id BIGINT UNSIGNED NOT NULL,
  requested_by BIGINT UNSIGNED NOT NULL,
  changes_json TEXT NOT NULL,
  status ENUM('Pending Approval','Approved','Rejected') NOT NULL DEFAULT 'Pending Approval',
  reviewed_by BIGINT UNSIGNED NULL, admin_note TEXT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, reviewed_at TIMESTAMP NULL,
  PRIMARY KEY (id), KEY idx_profile_status (status, created_at),
  CONSTRAINT fk_profile_student FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
  CONSTRAINT fk_profile_requester FOREIGN KEY (requested_by) REFERENCES users(id) ON DELETE CASCADE,
  CONSTRAINT fk_profile_reviewer FOREIGN KEY (reviewed_by) REFERENCES users(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS meal_menus (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT, menu_date DATE NOT NULL,
  breakfast TEXT NOT NULL, lunch TEXT NOT NULL, snacks TEXT NOT NULL, dinner TEXT NOT NULL,
  updated_by BIGINT UNSIGNED NULL, updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id), UNIQUE KEY uq_meal_menu_date (menu_date),
  CONSTRAINT fk_menu_updater FOREIGN KEY (updated_by) REFERENCES users(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS meal_attendance (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  student_id BIGINT UNSIGNED NOT NULL,
  meal_date DATE NOT NULL,
  meal_type ENUM('Breakfast','Lunch','Snacks','Dinner') NOT NULL,
  scanned_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  scanned_by BIGINT UNSIGNED NOT NULL,
  qr_token_id BIGINT UNSIGNED NOT NULL,
  PRIMARY KEY (id),
  UNIQUE KEY uq_attendance_student_meal (student_id, meal_date, meal_type),
  UNIQUE KEY uq_attendance_qr_token (qr_token_id),
  KEY idx_attendance_date_meal (meal_date, meal_type),
  CONSTRAINT fk_attendance_student FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
  CONSTRAINT fk_attendance_scanner FOREIGN KEY (scanned_by) REFERENCES users(id) ON DELETE RESTRICT,
  CONSTRAINT fk_attendance_token FOREIGN KEY (qr_token_id) REFERENCES qr_tokens(id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


SET FOREIGN_KEY_CHECKS = 1;
