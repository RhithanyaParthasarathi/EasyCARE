import os
import random
import smtplib
from email.message import EmailMessage
from datetime import datetime, timedelta
import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, field_validator
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
SECRET_KEY = os.environ.get("SECRET_KEY") or "your_secret_key"  # Use an environment variable for security!
ALGORITHM = "HS256"  # HMAC SHA-256

class UserCreate(BaseModel):
    username: str
    password: str
    email: EmailStr
    role: UserRole = UserRole.patient  # Changed to use the Enum
    license_number: Optional[str] = None  # Doctor Specific

    @field_validator("license_number")
    def license_number_must_be_present_for_doctors(cls, value, values):
        if values.get("role") == UserRole.doctor and not value:
            raise ValueError("License number is required for doctors.")
        return value

    @field_validator("role")
    def role_must_be_valid(cls, value):
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
    token_type: str = "bearer"  # Example.  In real usage would be a JWT.

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

def create_jwt_token(user_id: int, role: UserRole):
    payload = {
        'user_id': user_id,
        'role': role,
        'exp': datetime.utcnow() + timedelta(minutes=30)  # Token expires in 30 minutes
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def verify_jwt_token(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(user: UserCreate, db: db_dependency):
    print(f"Registering user: {user}")  # Debugging

    #Check if username already registered
    db_user = db.query(User).filter(User.username == user.username).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Username already registered")

    #Check if email already registered
    db_user = db.query(User).filter(User.email == user.email).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Email already registered")

    if user.role == UserRole.doctor:
        #Check if the email and liscence number already exists.
        existing_doctor = db.query(User).filter(User.license_number == user.license_number, User.email == user.email, User.role == UserRole.doctor).first()
        if existing_doctor:
             raise HTTPException(status_code=400, detail="A doctor with this license number and email already exists.")


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


@router.post("/login", response_model=Token)
async def login(user: UserCreate, db: db_dependency):
    db_user = db.query(User).filter((User.username == user.username) | (User.email == user.username)).first()  # Changed to use user.username for BOTH username and email
    if db_user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password")

    if not check_password_hash(db_user.password, user.password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password")

    if  str(db_user.role) != str(user.role):
         raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid role for this user")

    # Generate JWT token
    access_token = create_jwt_token(user_id=db_user.id, role=db_user.role)
    return Token(access_token=access_token, token_type="bearer")

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