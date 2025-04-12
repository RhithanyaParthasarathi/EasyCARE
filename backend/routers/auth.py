# auth.py
# --- Add these imports ---
from fastapi import Request, Cookie
from fastapi.security import OAuth2PasswordBearer
# ----
import os
import random
import smtplib
from email.message import EmailMessage
from datetime import datetime, timedelta
from fastapi.security import OAuth2PasswordRequestForm
import jwt
from fastapi import APIRouter, Depends, HTTPException, status, Response, Header
from pydantic import BaseModel, EmailStr, field_validator, ValidationInfo
from sqlalchemy.orm import Session
from typing import Annotated, Optional
from werkzeug.security import generate_password_hash, check_password_hash
from backend.database import get_db
from backend.models import User, UserRole
from dotenv import load_dotenv


load_dotenv()

router = APIRouter(
    prefix="/auth",
    tags=["authentication"],
)

db_dependency = Annotated[Session, Depends(get_db)]
SECRET_KEY = os.environ.get("SECRET_KEY", "default_secret_key_for_dev_only") # Provide a default for safety
ALGORITHM = "HS256"  # HMAC SHA-256
ACCESS_TOKEN_EXPIRE_MINUTES = 30

#Hardcoded liscence
HARDCODED_LICENSE_NUMBER = "12345" # Change this to real valid registration Number

# --- Define OAuth2 scheme (tells FastAPI how to find the token) ---
# The tokenUrl should point to your login endpoint relative to the root
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

class UserCreate(BaseModel):
    username: str
    password: str
    email: EmailStr
    role: UserRole = UserRole.patient  # Changed to use the Enum
    license_number: Optional[str] = None  # Doctor Specific

    @field_validator("license_number")
    def license_number_must_be_present_for_doctors(cls, value: str | None, info: ValidationInfo) -> str | None:
        
        if info.data.get("role") == UserRole.doctor and not value:
            raise ValueError("License number is required for doctors.")
        return value

    @field_validator("role")
    def role_must_be_valid(cls, value: UserRole) -> UserRole:
        if value not in (UserRole.patient, UserRole.doctor):
            raise ValueError("Role must be either 'patient' or 'doctor'.")
        return value

class ForgotPasswordRequest(BaseModel):
    email: EmailStr

class VerifyOTPRequest(BaseModel):
    email: EmailStr
    otp: str

class ResetPasswordRequest(BaseModel):
    email: EmailStr
    otp: str
    new_password: str

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer" # Example.  In real usage would be a JWT.
    username: str
    user_id: int   # <<< ADD THIS LINE
    role: str      # <<< ADD THIS LINE

# Temporary storage for OTPs (Replace with Redis in production)
otp_store = {}

def send_email(to_email: str, subject: str, body: str):
    sender_email = os.environ.get("EMAIL_ADDRESS")
    sender_password = os.environ.get("EMAIL_PASSWORD")

    msg = EmailMessage()
    msg.set_content(body)
    msg['Subject'] = subject
    msg['From'] = sender_email
    msg['To'] = to_email

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(sender_email, sender_password)
            smtp.send_message(msg)
        print("Email sent successfully!")
    except Exception as e:
        print(f"Error sending email: {e}")
        raise HTTPException(status_code=500, detail="Failed to send email")

def create_jwt_token(data: dict):
    payload = data
    payload['exp'] = datetime.utcnow() + timedelta(minutes=30)  # Token expires in 30 minutes
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def verify_jwt_token(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


def validate_license_number(license_number: str) -> bool:
    """
    Validates a doctor's license number (HARDCODED FOR NOW).

    Returns True if the license number matches the hardcoded value, False otherwise.
    """
    return license_number == HARDCODED_LICENSE_NUMBER

def authenticate_user(db: Session, username: str, password: str):
    db_user = db.query(User).filter((User.username == username) | (User.email == username)).first()
    if not db_user:
        return None
    if not check_password_hash(db_user.password, password):
        return None
    return db_user

# --- NEW Dependency for any logged-in user ---
async def get_current_active_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: db_dependency
) -> User:
    """Gets the user associated with the provided JWT token."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = verify_jwt_token(token)
        user_id: int | None = payload.get("user_id")
        if user_id is None:
            print("Token payload missing user_id")
            raise credentials_exception
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has expired")
    except jwt.InvalidTokenError:
        raise credentials_exception
    except Exception as e:
        print(f"Unexpected error verifying token: {e}")
        raise credentials_exception

    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        print(f"User with ID {user_id} from token not found in DB")
        raise credentials_exception
    # Note: We don't check the role here; the endpoint using this dependency will check if needed.
    print(f"get_current_active_user: Found user {user.username} (ID: {user.id}, Role: {user.role})")
    return user
# --- End New Dependency ---

# --- ADD THIS DEPENDENCY FUNCTION ---
# --- REPLACE the old get_current_doctor with this one ---
async def get_current_doctor(
    token: Annotated[str, Depends(oauth2_scheme)], # Extract token from Authorization header
    db: db_dependency
    ) -> User:
    """
    Dependency: Gets the current user from JWT token,
    ensuring they are a doctor.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        # Verify the token (using your existing function is fine)
        payload = verify_jwt_token(token)
        # Extract user identifier (e.g., username or user_id) from payload
        # Ensure your create_jwt_token puts 'user_id' in the payload
        user_id: int | None = payload.get("user_id")
        role: str | None = payload.get("role") # Get role from token

        if user_id is None or role is None:
            print("Token payload missing user_id or role") # Debug
            raise credentials_exception

    except jwt.ExpiredSignatureError:
         raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError as e:
        print(f"Invalid token error: {e}") # Debug
        raise credentials_exception
    except Exception as e: # Catch other potential errors during verification
         print(f"Error verifying token: {e}") # Debug
         raise credentials_exception

    # Fetch user from DB based on ID from token
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        print(f"User with ID {user_id} not found in DB") # Debug
        raise credentials_exception

    # Check if the role from token matches DB and is 'doctor'
    # Compare with the Enum value or its .value attribute
    if role != UserRole.doctor.value or user.role != UserRole.doctor :
         print(f"Role mismatch or not a doctor. Token Role: {role}, DB Role: {user.role}") # Debug
         raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="User is not authorized (Not a doctor)"
        )

    print(f"get_current_doctor successful for user: {user.username}") # Debug
    return user
# --- END OF REPLACEMENT ---
# --- END OF DEPENDENCY FUNCTION ---

@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(user: UserCreate, db: db_dependency):
     # Check if username already registered
    db_user_name = db.query(User).filter(User.username == user.username).first()
    if db_user_name:
        raise HTTPException(status_code=400, detail="Username already registered")

    # Check if email already registered
    db_user_email = db.query(User).filter(User.email == user.email).first()
    if db_user_email:
        raise HTTPException(status_code=400, detail="Email already registered")

    if user.role == UserRole.doctor:
        if not user.license_number:
             raise HTTPException(status_code=400, detail="License number is required for doctors.")
        # Check if the license number already exists for another doctor
        existing_doctor_license = db.query(User).filter(
            User.license_number == user.license_number,
            User.role == UserRole.doctor
            ).first()
        if existing_doctor_license:
            raise HTTPException(status_code=400, detail="This license number is already registered to another doctor.")

        # Validate the license number format/logic (using hardcoded for now)
        if not validate_license_number(user.license_number):
            raise HTTPException(status_code=400, detail="Invalid license number provided.")
    
    hashed_password = generate_password_hash(user.password)

    db_user = User(
        username=user.username,
        password=hashed_password,
        email=user.email,
        role=user.role,
        license_number=user.license_number if user.role == UserRole.doctor else None
    )

    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return {"message": "User created successfully"}

# --- MODIFY THIS LOGIN ENDPOINT ---
@router.post("/login", response_model=Token) # Use your Token model if defined, or adjust response
async def login_for_access_token(response: Response, db: db_dependency, form_data: OAuth2PasswordRequestForm = Depends()):
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_jwt_token(
        # Include essential info in token if needed elsewhere, but primary auth is cookie
        data={"sub": user.username, "role": user.role.value, "user_id": user.id}
    )

    # Set HttpOnly cookie for authentication
    response.set_cookie(
        key="doctor_id_backup", # Rename if you want to avoid potential confusion,          # Cookie name
        value=str(user.id),       # User ID as string
        httponly=True,            # CRUCIAL: Prevent JS access
        samesite="Lax",           # Recommended for security ('Strict' is more secure but can break cross-origin requests)
        secure=False,             # CHANGE TO True if using HTTPS
        path="/",                 # Cookie available site-wide
        max_age=int(access_token_expires.total_seconds()) # Optional: Expire cookie with token
    )

    # Return token AND user info in the body for frontend convenience
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "username": user.username,
        "user_id": user.id, # Send user_id explicitly
        "role": user.role.value # Send role explicitly
        }
# --- END OF MODIFIED LOGIN ---

@router.post("/forgot-password")
async def forgot_password(request: ForgotPasswordRequest, db: db_dependency):
    email = request.email
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User with this email not found")

    otp = str(random.randint(100000, 999999))
    otp_store[email] = {"otp": otp, "user_id": user.id}  # Store in temporary storage

    # Send email
    try:
        send_email(email, "Password Reset OTP", f"Your OTP is: {otp}")
    except HTTPException as e:
        raise e  # Re-raise the exception from send_email
    return {"message": "OTP sent to your email address"}


@router.post("/verify-otp")
async def verify_otp(request: VerifyOTPRequest):
    email = request.email
    otp = request.otp

    if email not in otp_store or otp_store[email]["otp"] != otp:
        raise HTTPException(status_code=400, detail="Invalid OTP")

    # If OTP is valid, you might return a success message and redirect
    # the user to a page where they can enter their new password.
    return {"message": "OTP verified successfully"}


@router.post("/reset-password")
async def reset_password(request: ResetPasswordRequest, db: db_dependency):
    email = request.email
    otp = request.otp
    new_password = request.new_password

    if email not in otp_store or otp_store[email]["otp"] != otp:
        raise HTTPException(status_code=400, detail="Invalid OTP")

    user_id = otp_store[email]["user_id"]
    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    hashed_password = generate_password_hash(new_password)
    user.password = hashed_password
    db.commit()

    del otp_store[email]  # Remove OTP from store

    return {"message": "Password reset successfully"}