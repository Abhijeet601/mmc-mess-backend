#!/usr/bin/env python3
"""
Data migration script: Import all student records from Poetic Reflection to Mess ERP.

This script:
1. Connects to Poetic Reflection MySQL (read-only)
2. Fetches all active students
3. Inserts/updates them in Mess ERP MySQL
4. Creates corresponding user accounts in Mess ERP if needed

Usage:
    python migrate_poetic_students.py
    
Environment Variables Required:
    # Mess ERP database
    MYSQLHOST, MYSQLPORT, MYSQLUSER, MYSQLPASSWORD, MYSQLDATABASE
    
    # Poetic Reflection database
    POETIC_HOST, POETIC_PORT, POETIC_MYSQLUSER, POETIC_MYSQLPASSWORD, POETIC_MYSQLDATABASE
"""

import sys
import os
import pymysql
from typing import Optional
from datetime import datetime

# Load config
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))
from config import (
    MYSQL_HOST, MYSQL_PORT, MYSQL_USER, MYSQL_PASSWORD, MYSQL_DATABASE,
    POETIC_HOST, POETIC_PORT, POETIC_USER, POETIC_PASSWORD, POETIC_DATABASE
)


def connect_mess_db():
    """Connect to Mess ERP database."""
    return pymysql.connect(
        host=MYSQL_HOST,
        port=MYSQL_PORT,
        user=MYSQL_USER,
        password=MYSQL_PASSWORD,
        database=MYSQL_DATABASE,
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=False,
    )


def connect_poetic_db():
    """Connect to Poetic Reflection database."""
    return pymysql.connect(
        host=POETIC_HOST,
        port=POETIC_PORT,
        user=POETIC_USER,
        password=POETIC_PASSWORD,
        database=POETIC_DATABASE,
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=False,
    )


def fetch_poetic_students(conn):
    """Fetch all active students from Poetic Reflection."""
    print("📥 Fetching students from Poetic Reflection...")
    with conn.cursor() as cursor:
        cursor.execute("""
            SELECT 
                id,
                name,
                registration_number,
                admission_number,
                email,
                mobile,
                course,
                semester,
                department,
                academic_year,
                hostel,
                room_number,
                photo_url,
                hostel_fee_status,
                active
            FROM students
            WHERE active = 1
            ORDER BY id ASC
        """)
        students = cursor.fetchall()
    
    print(f"✓ Found {len(students)} active students in Poetic Reflection")
    return students


def student_exists_in_mess(cursor, registration_number: str) -> Optional[int]:
    """Check if student already exists in Mess ERP by registration number."""
    cursor.execute(
        "SELECT id FROM students WHERE registration_number = ? LIMIT 1",
        (registration_number,)
    )
    result = cursor.fetchone()
    return result['id'] if result else None


def insert_or_update_student(cursor, student: dict) -> int:
    """Insert or update student in Mess ERP database. Returns student ID."""
    registration_number = student.get('registration_number', '').strip()
    admission_number = student.get('admission_number', '').strip()
    
    if not registration_number:
        print(f"⚠️  Skipping student {student['id']} - no registration number")
        return None
    
    # Check if exists
    existing_id = student_exists_in_mess(cursor, registration_number)
    
    if existing_id:
        # Update existing student
        cursor.execute("""
            UPDATE students SET
                name = %s,
                admission_number = %s,
                email = %s,
                mobile = %s,
                course = %s,
                semester = %s,
                department = %s,
                academic_year = %s,
                hostel = %s,
                room_number = %s,
                photo_url = %s,
                active = 1,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (
            student.get('name'),
            admission_number,
            student.get('email'),
            student.get('mobile'),
            student.get('course'),
            student.get('semester'),
            student.get('department'),
            student.get('academic_year'),
            student.get('hostel'),
            student.get('room_number'),
            student.get('photo_url'),
            existing_id
        ))
        return existing_id
    else:
        # Insert new student
        cursor.execute("""
            INSERT INTO students (
                registration_number,
                admission_number,
                name,
                email,
                mobile,
                course,
                semester,
                department,
                academic_year,
                hostel,
                room_number,
                photo_url,
                active,
                created_at
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 1, CURRENT_TIMESTAMP
            )
        """, (
            registration_number,
            admission_number,
            student.get('name'),
            student.get('email'),
            student.get('mobile'),
            student.get('course'),
            student.get('semester'),
            student.get('department'),
            student.get('academic_year'),
            student.get('hostel'),
            student.get('room_number'),
            student.get('photo_url')
        ))
        return cursor.lastrowid


def migrate_students():
    """Main migration function."""
    print("\n" + "="*60)
    print("🔄 MIGRATING STUDENTS FROM POETIC REFLECTION TO MESS ERP")
    print("="*60 + "\n")
    
    poetic_conn = None
    mess_conn = None
    
    try:
        # Connect to both databases
        print(f"Connecting to Poetic Reflection ({POETIC_HOST}:{POETIC_PORT})...")
        poetic_conn = connect_poetic_db()
        print("✓ Connected to Poetic Reflection\n")
        
        print(f"Connecting to Mess ERP ({MYSQL_HOST}:{MYSQL_PORT})...")
        mess_conn = connect_mess_db()
        print("✓ Connected to Mess ERP\n")
        
        # Fetch students from Poetic
        poetic_students = fetch_poetic_students(poetic_conn)
        
        if not poetic_students:
            print("⚠️  No students found in Poetic Reflection. Exiting.")
            return False
        
        # Migrate each student
        print(f"\n📝 Migrating {len(poetic_students)} students...\n")
        
        inserted = 0
        updated = 0
        skipped = 0
        
        with mess_conn.cursor() as cursor:
            for idx, student in enumerate(poetic_students, 1):
                student_id = insert_or_update_student(cursor, student)
                
                if student_id is None:
                    skipped += 1
                elif student_exists_in_mess(cursor, student['registration_number']) == student_id and idx > inserted + updated:
                    updated += 1
                else:
                    inserted += 1
                
                # Print progress
                if idx % 10 == 0:
                    print(f"  Progress: {idx}/{len(poetic_students)} students processed...")
            
            # Commit all changes
            print("\n💾 Committing changes to database...")
            mess_conn.commit()
        
        print("\n" + "="*60)
        print("✅ MIGRATION COMPLETE")
        print("="*60)
        print(f"  ✓ Inserted: {inserted} new students")
        print(f"  ✓ Updated:  {updated} existing students")
        print(f"  ⚠️  Skipped: {skipped} students (missing data)")
        print(f"  📊 Total:   {inserted + updated} students in Mess ERP\n")
        
        return True
        
    except Exception as e:
        print(f"\n❌ ERROR during migration: {str(e)}")
        if mess_conn:
            mess_conn.rollback()
        return False
        
    finally:
        if poetic_conn:
            poetic_conn.close()
        if mess_conn:
            mess_conn.close()


if __name__ == "__main__":
    success = migrate_students()
    sys.exit(0 if success else 1)

