"""
Integration with Poetic Reflection master database for student eligibility and profile data.
This module handles:
- Reading student records from Poetic Reflection (READ-ONLY)
- Verifying hostel fee payment status
- Syncing student profile data
"""

from fastapi import HTTPException, status
from .db import get_poetic_db, row_to_dict


def check_hostel_fee_payment_status(registration_number: str) -> dict:
    """
    Check if a student has paid their hostel fee from Poetic Reflection.
    
    Args:
        registration_number: Student registration number from Poetic Reflection
        
    Returns:
        dict: {
            'eligible': bool,
            'status': str,  # 'PAID', 'PENDING', 'UNPAID', 'FAILED', 'NOT_FOUND'
            'student_id': int | None,
            'student_name': str | None,
            'hostel': str | None,
            'room_number': str | None,
            'payment_status': str | None
        }
    """
    try:
        with get_poetic_db() as db:
            # Query structure depends on Poetic Reflection schema
            # Adjust table names and columns based on actual database structure
            row = db.execute(
                """
                SELECT 
                    id,
                    name,
                    registration_number,
                    hostel,
                    room_number,
                    hostel_fee_status
                FROM students 
                WHERE registration_number = ? AND active = 1
                LIMIT 1
                """,
                (registration_number,)
            ).fetchone()
            
            if not row:
                return {
                    'eligible': False,
                    'status': 'NOT_FOUND',
                    'student_id': None,
                    'student_name': None,
                    'hostel': None,
                    'room_number': None,
                    'payment_status': None
                }
            
            student = dict(row)
            payment_status = student.get('hostel_fee_status', '').upper()
            
            # Only PAID status allows login
            is_eligible = payment_status == 'PAID'
            
            return {
                'eligible': is_eligible,
                'status': payment_status if payment_status in ['PAID', 'PENDING', 'UNPAID', 'FAILED'] else 'UNKNOWN',
                'student_id': student.get('id'),
                'student_name': student.get('name'),
                'hostel': student.get('hostel'),
                'room_number': student.get('room_number'),
                'payment_status': payment_status
            }
    except Exception as e:
        # Log the error but don't expose database details
        print(f"Error checking Poetic Reflection: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to verify hostel fee status. Please try again later."
        )


def get_student_profile_from_poetic(registration_number: str) -> dict | None:
    """
    Fetch student profile data from Poetic Reflection for profile syncing.
    
    Args:
        registration_number: Student registration number
        
    Returns:
        dict with student profile or None if not found
    """
    try:
        with get_poetic_db() as db:
            row = db.execute(
                """
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
                    photo_url
                FROM students 
                WHERE registration_number = ? AND active = 1
                LIMIT 1
                """,
                (registration_number,)
            ).fetchone()
            
            return dict(row) if row else None
    except Exception as e:
        print(f"Error fetching student profile from Poetic Reflection: {str(e)}")
        return None


def verify_student_in_poetic(registration_number: str) -> bool:
    """
    Verify if a student exists in Poetic Reflection database.
    
    Args:
        registration_number: Student registration number
        
    Returns:
        bool: True if student exists and is active, False otherwise
    """
    try:
        with get_poetic_db() as db:
            row = db.execute(
                "SELECT id FROM students WHERE registration_number = ? AND active = 1 LIMIT 1",
                (registration_number,)
            ).fetchone()
            return row is not None
    except Exception as e:
        print(f"Error verifying student in Poetic Reflection: {str(e)}")
        return False

