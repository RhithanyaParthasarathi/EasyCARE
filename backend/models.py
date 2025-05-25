# backend/models.py
from sqlalchemy import (Column, Integer, String, Enum, ForeignKey,Date, Boolean, DateTime, Text,Float,func)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
import enum
from datetime import datetime,timezone


Base = declarative_base()

class UserRole(str, enum.Enum):
    patient = "patient"
    doctor = "doctor"

class Prescription(Base):
    __tablename__ = "prescriptions"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    doctor_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    prescription_date = Column(Date, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    medications = relationship("PrescriptionMedication", back_populates="prescription", cascade="all, delete-orphan")
    # Add back_populates in User if needed
    patient = relationship("User", foreign_keys=[patient_id], back_populates="patient_prescriptions")
    doctor = relationship("User", foreign_keys=[doctor_id], back_populates="doctor_prescriptions")


class PrescriptionMedication(Base):
    __tablename__ = "prescription_medications"

    id = Column(Integer, primary_key=True, index=True)
    prescription_id = Column(Integer, ForeignKey("prescriptions.id", ondelete="CASCADE"), nullable=False, index=True)
    medication_name = Column(String, nullable=False)
    dosage = Column(String, nullable=True)
    frequency = Column(String, nullable=True)
    duration = Column(String, nullable=True)
    instructions = Column(Text, nullable=True)

    prescription = relationship("Prescription", back_populates="medications")

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

     # *** NEW: Add Relationships to Profile Tables (One-to-One) ***
    patient_profile = relationship("PatientProfile", back_populates="user", uselist=False, cascade="all, delete-orphan")
    doctor_profile = relationship("DoctorProfile", back_populates="user", uselist=False, cascade="all, delete-orphan")

    # *** NEW/UPDATED: Add Relationships from Appointments/Notifications ***
    # Appointments booked BY this user (as patient)
    patient_appointments = relationship("Appointment", foreign_keys="[Appointment.patient_id]", back_populates="patient", cascade="all, delete-orphan")
    # Appointments conducted BY this user (as doctor)
    doctor_appointments = relationship("Appointment", foreign_keys="[Appointment.doctor_id]", back_populates="doctor", cascade="all, delete-orphan")
    # Notifications FOR this user
    notifications = relationship("Notification", back_populates="user", cascade="all, delete-orphan")
    doctor_prescriptions = relationship("Prescription", foreign_keys=[Prescription.doctor_id], back_populates="doctor") # Add back_populates here if needed
    patient_prescriptions = relationship("Prescription", foreign_keys=[Prescription.patient_id], back_populates="patient") # Add back_populates here if needed
    health_data_entries = relationship("HealthDataEntry", back_populates="user", cascade="all, delete-orphan", order_by="desc(HealthDataEntry.timestamp)")


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
     # Optional: If TimeSlot needs to know about its one Appointment
    # appointment = relationship("Appointment", back_populates="time_slot", uselist=False)


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
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False) # Use server default, timezone=True recommended

    # Relationships (adjust back_populates based on your User/TimeSlot models)
     # *** UPDATED back_populates names ***
    patient = relationship("User", foreign_keys=[patient_id], back_populates="patient_appointments")
    doctor = relationship("User", foreign_keys=[doctor_id], back_populates="doctor_appointments")
    time_slot = relationship("TimeSlot") # One-to-one relationship with TimeSlot via unique=True FK   

# models.py
# Add near other models

class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True) # The user receiving the notification
    message = Column(String, nullable=False)
    is_read = Column(Boolean, default=False, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False) 
    # Optional: Link to related entity (e.g., appointment)
    appointment_id = Column(Integer, ForeignKey("appointments.id"), nullable=True)

    # Relationship back to user
     # *** UPDATED back_populates name ***
    user = relationship("User", back_populates="notifications")
    appointment = relationship("Appointment") # Optional relationship 

# --- *** NEW Patient Profile Table *** ---
class PatientProfile(Base):
    __tablename__ = "patient_profiles"

    # Use user_id as the primary key AND foreign key for one-to-one
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True) # Add ondelete
    full_name = Column(String, nullable=True)
    age = Column(Integer, nullable=True)
    gender = Column(String, nullable=True)
    height_cm = Column(Integer, nullable=True)
    weight_kg = Column(Float, nullable=True) # Use Float
    blood_type = Column(String, nullable=True)
    is_complete = Column(Boolean, default=False, nullable=False) # Track completion here

    # Relationship back to User
    user = relationship("User", back_populates="patient_profile")
# --- *** END Patient Profile Table *** ---


# --- *** NEW Doctor Profile Table *** ---
class DoctorProfile(Base):
    __tablename__ = "doctor_profiles"

    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True) # Add ondelete
    full_name = Column(String, nullable=True)
    specialty = Column(String, nullable=True, index=True)
    hospital_affiliation = Column(String, nullable=True)
    years_experience = Column(Integer, nullable=True)
    qualifications = Column(Text, nullable=True) # Use Text
    about_me = Column(Text, nullable=True) # Use Text
    is_complete = Column(Boolean, default=False, nullable=False) # Track completion here

    # Relationship back to User
    user = relationship("User", back_populates="doctor_profile")
# --- *** END Doctor Profile Table *** ---

class HealthDataEntry(Base):
    __tablename__ = "health_data_entries"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True) # For DB to handle

    heart_rate = Column(Integer, nullable=True)
    systolic_bp = Column(Integer, nullable=True)
    diastolic_bp = Column(Integer, nullable=True)
    oxygen_saturation = Column(Float, nullable=True)
    glucose_level = Column(Float, nullable=True)
    respiratory_rate = Column(Integer, nullable=True)
    temperature_celsius = Column(Float, nullable=True)

    heart_rate_status = Column(String, nullable=True)
    bp_status = Column(String, nullable=True)
    oxygen_status = Column(String, nullable=True)
    glucose_status = Column(String, nullable=True)
    respiratory_rate_status = Column(String, nullable=True)
    temperature_status = Column(String, nullable=True)

    user = relationship("User", back_populates="health_data_entries")