# pfastapiserver/router.py
import psycopg2
from fastapi import APIRouter, HTTPException, status, Request,Header
from pydantic import BaseModel, Field,EmailStr
from typing import Optional
from db import get_db
import os
import datetime
import jwt

# Initialize the router interface with a prefix
router = APIRouter(prefix="/auth", tags=["Authentication"])

# Define the data schema structure your API expects
class SignupRequest(BaseModel):
    phoneNumber: str = Field(..., pattern="^[0-9]{10}$")
    password: str = Field(..., min_length=6)

@router.post("/signup")
async def signup(payload: SignupRequest):
    print("--- Incoming Payload Data ---")
    print(f"Phone Number: {payload.phoneNumber}")
    print("-----------------------------")
    
    with get_db() as conn:
        cursor = conn.cursor()
        try:
            # Check if user already exists
            query = "SELECT slno FROM users WHERE phone_number = %s;"
            cursor.execute(query, (payload.phoneNumber,))
            db_output = cursor.fetchone()
            
            print(f"Database Fetch Result: {db_output}")
            
            # Condition 2: User found -> Send "2"
            if db_output:
                return {"status": "2", "message": "User already exists with this phone number."}
            
            # Condition 1: User not found -> Save to DB and Send "1"
            insert_query = "INSERT INTO users (phone_number, password) VALUES (%s, %s);"
            cursor.execute(insert_query, (payload.phoneNumber, payload.password))
            conn.commit()
            
            return {"status": "1", "message": "Signup successful!"}
            
        except psycopg2.Error as e:
            conn.rollback()
            raise HTTPException(status_code=500, detail=f"Database execution error: {e}")
        finally:
            cursor.close()

# Grabbing your secret key directly from your .env file
JWT_SECRET_KEY = os.getenv("JWT_SECRET", "FALLBACK_SECRET_KEY_IF_ENV_MISSING")
JWT_ALGORITHM = "HS256"

class LoginRequest(BaseModel):
    phoneNumber: str = Field(..., pattern="^[0-9]{10}$")
    password: str = Field(..., min_length=6)

@router.post("/login")
async def login(request: Request, payload: LoginRequest):
    print(f"Incoming Login Attempt for: {payload.phoneNumber}")
    
    with get_db() as conn:
        cursor = conn.cursor()
        try:
            # Fetching password and the brand new name column matching the phone number
            query = "SELECT phone_number, password, name FROM users WHERE phone_number = %s;"
            cursor.execute(query, (payload.phoneNumber,))
            db_output = cursor.fetchone()
            
            # 1. User not found
            if not db_output:
                return {"status": "3", "message": "User not found. Please sign up first."}
            
            db_phone, db_password, db_name = db_output
            
            # 2. Password matches perfectly
            if payload.password == db_password:
                # Generate a secure token packing the sub claim
                token_payload = {
                    "sub": db_phone,
                    "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=24)
                }
                token = jwt.encode(token_payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
                
                return {
                    "status": "1",
                    "message": "Login successful!",
                    "token": token,
                    "user_data": {
                        "phone_number": db_phone,
                        "name": db_name
                    }
                }
            
            # 3. Invalid password
            else:
                return {"status": "2", "message": "Invalid password credentials."}
                
        except psycopg2.Error as e:
            conn.rollback()
            raise HTTPException(status_code=500, detail=f"Database execution error: {e}")
        finally:
            cursor.close()

            # pfastapiserver/router.py

# ... keep your existing imports, tables schemas, and signup/login routes as they are ...

@router.get("/dashboard-data")
async def get_dashboard_data(request: Request):
    print("--- Incoming Dashboard Data Authorization Request ---")
    
    # 1. Grab the Authorization header sent by React Axios
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        print("Missing or malformed Authorization header.")
        return {"status": "1", "message": "Unauthorized token footprint."}
    
    # Extract the clean token string out of 'Bearer <token>'
    token = auth_header.split(" ")[1]
    
    try:
        # 2. Decode and verify the cryptographic signature of the token
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        user_phone = payload.get("sub")
        
        if not user_phone:
            return {"status": "1", "message": "Invalid token payload schema structure."}
            
    except jwt.ExpiredSignatureError:
        print("Token verification failed: Signature has expired.")
        return {"status": "1", "message": "Token has expired."}
    except jwt.InvalidTokenError:
        print("Token verification failed: Invalid token cryptographic hash.")
        return {"status": "1", "message": "Invalid token fingerprint."}

    # 3. Connect to PostgreSQL database to read both profile metrics and student records
    with get_db() as conn:
        cursor = conn.cursor()
        try:
            # Query A: Fetch user's current metrics matching the extracted token phone number
            user_query = "SELECT phone_number, name FROM users WHERE phone_number = %s;"
            cursor.execute(user_query, (user_phone,))
            user_output = cursor.fetchone()
            
            if not user_output:
                return {"status": "1", "message": "User context row resource missing."}
                
            db_phone, db_name = user_output
            
            # Query B: Fetch the first 5 rows from your students data management table
            # (Note: Using LIMIT 5 ensures we only transfer exactly 5 rows)
            try:
                student_query = "SELECT rollno, name, email_id FROM student ORDER BY rollno ;"
                cursor.execute(student_query)
                student_rows = cursor.fetchall()
            except psycopg2.Error:
                # Fallback if your students table doesn't exist yet so your server won't crash
                conn.rollback()
                student_rows = []
                print("Warning: 'student' table does not exist or cannot be accessed yet.")

            # Transform raw database tuples into clean dictionary formats
            formatted_student= []
            for row in student_rows:
                formatted_student.append({
                    "rollno": row[0],
                    "name": row[1],
                    "email_id": row[2]
                })

            # 4. Successful token execution verification payload response match!
            # We pass status 5 to signal to React that data was compiled successfully
            return {
                "status": "5",
                "message": "Token access verified successfully.",
                "user_data": {
                    "phone_number": db_phone,
                    "name": db_name
                },
                "student": formatted_student
            }

        except psycopg2.Error as e:
            conn.rollback()
            raise HTTPException(status_code=500, detail=f"Database execution crash: {e}")
        finally:
            cursor.close()

class UpdateProfileInput(BaseModel):
    username: str
    phoneNumber: str
    password: Optional[str] = None

@router.post("/update-profile")
async def update_profile(request: Request, data: UpdateProfileInput):
    print("--- Incoming Profile Update Request ---")
    
    # 1. Grab and verify the Authorization header
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        print("Missing or malformed Authorization header.")
        return {"status": "0", "message": "Unauthorized token footprint."}
    
    token = auth_header.split(" ")[1]
    
    try:
        # Decode and find the current user's phone number from the token payload
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        current_user_phone = payload.get("sub")
        
        if not current_user_phone:
            return {"status": "0", "message": "Invalid token payload schema structure."}
            
    except jwt.ExpiredSignatureError:
        print("Token verification failed: Signature has expired.")
        return {"status": "1", "message": "Token has expired."}
    except jwt.InvalidTokenError:
        print("Token verification failed: Invalid token cryptographic hash.")
        return {"status": "0", "message": "Invalid token fingerprint."}

    with get_db() as conn:
        cursor = conn.cursor()
        try:
            if data.password and data.password.strip():
                # Update everything including the new password
                update_query = """
                    UPDATE users 
                    SET name = %s, phone_number = %s, password = %s 
                    WHERE phone_number = %s
                    RETURNING phone_number, name;
                """
                query_params = (data.username, data.phoneNumber, data.password, current_user_phone)
            else:
                # Password is empty -> Only update name and phone number
                update_query = """
                    UPDATE users 
                    SET name = %s, phone_number = %s 
                    WHERE phone_number = %s
                    RETURNING phone_number, name;
                """
                query_params = (data.username, data.phoneNumber, current_user_phone)

            # --- FIX: Shifted these left out of the else block so they run for BOTH cases ---
            cursor.execute(update_query, query_params)
            updated_user = cursor.fetchone()
            conn.commit()
            
            if not updated_user:
                return {"status": "0", "message": "User record matching token signature not found."}
                
            db_phone, db_name = updated_user

            # 3. Success Payload Response (Sends status "1" and clean user_data object)
            return {
                "status": "1",
                "message": "Profile updated successfully.",
                "user_data": {
                    "phone_number": db_phone,
                    "name": db_name
                }
            }

        except psycopg2.Error as e:
            conn.rollback()
            print(f"Database update roadblock exception: {e}")
            return {"status": "0", "message": "Internal structural database exception error."}
        finally:
            cursor.close()


# 1. Pydantic Input Schema matching the Formik payload keys
class CreateStudentInput(BaseModel):
    rollno: int
    name: str
    email_id: str
 
@router.post("/create-student")
async def create_student(request: Request, data: CreateStudentInput):
    print("--- Incoming Student Registration Request ---")
    
    # 1. Grab and verify the Authorization header (Matches your pattern)
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        print("Missing or malformed Authorization header.")
        return {"status": "1", "message": "Unauthorized token footprint."}
    
    token = auth_header.split(" ")[1]
    
    try:
        # Decode token to verify validity and expiration dates
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        current_user_phone = payload.get("sub")
        
        if not current_user_phone:
            return {"status": "1", "message": "Invalid token payload schema structure."}
            
    except jwt.ExpiredSignatureError:
        print("Student Creation Blocked: Token has expired.")
        return {"status": "1", "message": "Token has expired."}
    except jwt.InvalidTokenError:
        print("Student Creation Blocked: Invalid token signature.")
        return {"status": "1", "message": "Invalid token fingerprint."}

    # 2. Database Verification & Operations Layer
    with get_db() as conn:
        cursor = conn.cursor()
        try:
            # Check if any duplicate roll number exists in the flat table
            check_query = "SELECT rollno FROM student WHERE rollno = %s;"
            cursor.execute(check_query, (data.rollno,))
            existing_student = cursor.fetchone()

            if existing_student:
                print(f"Conflict found: Roll number {data.rollno} already exists.")
                # Return status "2" if duplicate roll number is caught
                return {
                    "status": "2",
                    "message": "Student roll number already exists."
                }

            # If unique, proceed with standard non-nullable insert sequence
            insert_query = """
                INSERT INTO student (rollno, name, email_id) 
                VALUES (%s, %s, %s) 
                RETURNING rollno, name, email_id;
            """
            cursor.execute(insert_query, (data.rollno, data.name, data.email_id))
            new_student = cursor.fetchone()
            conn.commit()

            print(f"Success: Student record saved -> Roll No: {new_student[0]}")
            # Return status "5" on database creation success
            return {
                "status": "5",
                "message": "Student registered successfully.",
                "student_data": {
                    "rollno": new_student[0],
                    "name": new_student[1],
                    "email_id": new_student[2]
                }
            }

        except psycopg2.Error as e:
            conn.rollback()
            print(f"Database error during student insertion: {e}")
            return {"status": "0", "message": "Internal database exception error."}
        finally:
            cursor.close()

class DeleteStudentInput(BaseModel):
    rollno: int

@router.post("/delete-student")
async def delete_student(
    data: DeleteStudentInput,
    authorization: Optional[str] = Header(None)  # Automatically grabs 'Authorization' from HTTP headers
):
    print("--- Incoming Student Deletion Request ---")
    
    # 1. Verify the Authorization header extraction pattern
    auth_header = authorization
    if not auth_header or not auth_header.startswith("Bearer "):
        print("Missing or malformed Authorization header.")
        return {"status": "1", "message": "Unauthorized token footprint."}
    
    token = auth_header.split(" ")[1]
    
    try:
        # Decode token securely
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        current_user_phone = payload.get("sub")
        
        if not current_user_phone:
            return {"status": "1", "message": "Invalid token payload schema structure."}
            
    except jwt.ExpiredSignatureError:
        print("Student Deletion Blocked: Token has expired.")
        return {"status": "1", "message": "Token has expired."}
    except jwt.InvalidTokenError:
        print("Student Deletion Blocked: Invalid token signature.")
        return {"status": "1", "message": "Invalid token fingerprint."}

    # 2. Database Layer Verification & Execution Operations
    with get_db() as conn:
        cursor = conn.cursor()
        try:
            # Verify if row is present before deletion query block executes
            check_query = "SELECT rollno, name FROM student WHERE rollno = %s;"
            cursor.execute(check_query, (data.rollno,))
            existing_student = cursor.fetchone()

            if not existing_student:
                print(f"Target Missing: Student with roll number {data.rollno} does not exist.")
                return {
                    "status": "2",
                    "message": "Student record not found."
                }

            student_name = existing_student[1]

            # Execute deletion string sequence
            delete_query = "DELETE FROM student WHERE rollno = %s;"
            cursor.execute(delete_query, (data.rollno,))
            conn.commit()

            print(f"Success: Student record wiped -> Roll No: {data.rollno} ({student_name})")
            return {
                "status": "5",
                "message": "Student record deleted successfully from database."
            }

        except psycopg2.Error as e:
            conn.rollback()
            print(f"Database error during student deletion execution: {e}")
            return {"status": "0", "message": "Internal database exception error."}
        finally:
            cursor.close()

class UpdateStudentInput(BaseModel):
    rollno: int
    name: str
    email_id: str

@router.post("/update-student")
async def update_student(request: Request, data: UpdateStudentInput):
    print("--- Incoming Student Record Update Request ---")
    
    # 1. JWT Authentication Guard
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return {"status": "0", "message": "Unauthorized token footprint."}
    
    token = auth_header.split(" ")[1]
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        current_user_phone = payload.get("sub")
        if not current_user_phone:
            return {"status": "0", "message": "Invalid token payload schema structure."}
    except jwt.ExpiredSignatureError:
        return {"status": "1", "message": "Token has expired."}
    except jwt.InvalidTokenError:
        return {"status": "0", "message": "Invalid token fingerprint."}

    # 2. Database Operations
    with get_db() as conn:
        cursor = conn.cursor()
        try:
            # --- DEBUG BLOCK: Let's see what rows are actually visible to this connection ---
            print("\n=== SYSTEM DEBUG: CURRENT ROWS IN DATABASE ===")
            cursor.execute("SELECT rollno, name FROM student;")
            all_rows = cursor.fetchall()
            for r in all_rows:
                print(f"Found Row -> Type of RollNo: {type(r[0])}, Value: {repr(r[0])}, Name: {r[1]}")
            print("==============================================\n")
            
            # Run the parameterized update statement
            update_query = """
                UPDATE student
                SET name = %s, email_id = %s 
                WHERE rollno = %s
                RETURNING rollno, name, email_id;
            """
            
            query_params = (data.name, data.email_id, int(data.rollno))
            
            print(f"Attempting DB Update -> Looking for RollNo: {data.rollno}")
            
            cursor.execute(update_query, query_params)
            updated_student = cursor.fetchone()
            conn.commit()
            
            if not updated_student:
                print(f"Database mismatch: rollno {data.rollno} was not found in the table.")
                return {"status": "0", "message": f"Student record matching Roll Number {data.rollno} not found."}
                
            db_rollno, db_name, db_email = updated_student
            print(f"Database successfully updated row: {db_rollno}")

            return {
                "status": "5",
                "message": "Student record updated successfully.",
                "student_data": {
                    "rollno": db_rollno,
                    "name": db_name,
                    "email_id": db_email
                }
            }

        except psycopg2.Error as e:
            conn.rollback()
            print(f"Database exception caught: {e}")
            return {"status": "0", "message": "Internal structural database exception error."}
        finally:
            cursor.close()