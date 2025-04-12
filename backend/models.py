# backend/models.py
from sqlalchemy import Column, Integer, String, Enum, ForeignKey,Date, Boolean, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
import enum
from datetime import datetime


Base = declarative_base()

class UserRole(str, enum.Enum):
    patient = "patient"
    doctor = "doctor"

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    password = Column(String)
    email = Column(String, unique=True, index=True) # Add unique=True, index=True
    role = Column(Enum(UserRole), default=UserRole.patient, nullable=False) # Add nullable=False
    license_number = Column(String, nullable=True)  # Only for doctors

    # Relationships
    time_slots = relationship("TimeSlot", back_populates="doctor", cascade="all, delete-orphan") # ADD cascade

class TimeSlot(Base):
    __tablename__ = "time_slots"

    id = Column(Integer, primary_key=True, index=True)
    # Store time in 24-hour HH:MM format for consistency and sorting
    start_time = Column(String, nullable=False)
    # end_time column IS NOT DEFINED HERE
    date = Column(Date, nullable=False, index=True) # Use this for scheduling
    # day_of_week = Column(String) # Keep if used elsewhere, but primary logic uses date
    doctor_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    is_booked = Column(Boolean, default=False, nullable=False, index=True) # Add this line

    # Relationship
    doctor = relationship("User", back_populates="time_slots")


# Add near other models in models.py
class AppointmentStatus(str, enum.Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"
    CANCELLED = "cancelled" # Optional: if patient can cancel
    COMPLETED = "completed" # Optional: after the session

class Appointment(Base):
    __tablename__ = "appointments"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    doctor_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    timeslot_id = Column(Integer, ForeignKey("time_slots.id"), unique=True, nullable=False, index=True) # Unique ensures one booking per slot
    appointment_date = Column(Date, nullable=False) # Store the specific date again for querying ease
    # appointment_time = Column(String, nullable=False) # Store start time again, or rely on timeslot link
    status = Column(Enum(AppointmentStatus), default=AppointmentStatus.PENDING, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow) # Use DateTime from sqlalchemy
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships (adjust back_populates based on your User/TimeSlot models)
    patient = relationship("User", foreign_keys=[patient_id]) # Specify foreign_keys if User has multiple relationships
    doctor = relationship("User", foreign_keys=[doctor_id])
    time_slot = relationship("TimeSlot") # One-to-one relationship with TimeSlot via unique=True FK   

# models.py
# Add near other models

class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True) # The user receiving the notification
    message = Column(String, nullable=False)
    is_read = Column(Boolean, default=False, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    # Optional: Link to related entity (e.g., appointment)
    appointment_id = Column(Integer, ForeignKey("appointments.id"), nullable=True)

    # Relationship back to user
    user = relationship("User") # Add back_populates in User if needed: notifications = relationship("Notification", back_populates="user")
    appointment = relationship("Appointment") # Optional relationship 