# backend/routers/health_data.py
from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel, Field, field_validator, validator
from sqlalchemy.orm import Session, joinedload
from typing import Annotated, List, Optional, Dict, Any
from sqlalchemy import func, desc
from database import get_db
from models import User, UserRole, HealthDataEntry, Appointment# Import new model
from routers.auth import get_current_active_user, get_current_doctor # Use general user auth
from datetime import datetime, date as py_date, timezone, timedelta

router = APIRouter(
    prefix="/health-data",
    tags=["Health Data"],
)

db_dependency = Annotated[Session, Depends(get_db)]
current_user_dependency = Annotated[User, Depends(get_current_active_user)]
current_doctor_dependency = Annotated[User, Depends(get_current_doctor)]

# --- Pydantic Models for Health Data ---

class HealthDataInput(BaseModel):
    heart_rate: Optional[int] = Field(None, gt=20, lt=300, description="Beats per minute")
    systolic_bp: Optional[int] = Field(None, gt=30, lt=350, description="Systolic blood pressure (mmHg)")
    diastolic_bp: Optional[int] = Field(None, gt=20, lt=250, description="Diastolic blood pressure (mmHg)")
    oxygen_saturation: Optional[float] = Field(None, ge=70, le=100, description="SpO2 percentage (e.g., 98.5)")
    glucose_level: Optional[float] = Field(None, gt=10, lt=1000, description="Blood glucose level (mg/dL)")
    respiratory_rate: Optional[int] = Field(None, gt=5, lt=60, description="Breaths per minute")
    temperature_celsius: Optional[float] = Field(None, gt=30, lt=45, description="Body temperature in Celsius")
    timestamp: Optional[datetime] = Field(None, description="Optional timestamp for backdated entries (ISO format). Defaults to now.")

    @validator('systolic_bp')
    def check_systolic_bp_with_diastolic(cls, systolic, values):
        diastolic = values.get('diastolic_bp')
        if systolic is not None and diastolic is not None and systolic <= diastolic:
            raise ValueError('Systolic BP must be greater than Diastolic BP.')
        return systolic

class HealthDataResponse(HealthDataInput): # Inherits fields from input for response
    id: int
    user_id: int
    timestamp: datetime # Will always be set

    # Status fields determined by backend
    heart_rate_status: Optional[str] = None
    bp_status: Optional[str] = None
    oxygen_status: Optional[str] = None
    glucose_status: Optional[str] = None
    respiratory_rate_status: Optional[str] = None
    temperature_status: Optional[str] = None

    class Config:
        from_attributes = True

class LatestHealthSnapshot(BaseModel):
    heart_rate: Optional[int] = None
    heart_rate_status: Optional[str] = None
    heart_rate_timestamp: Optional[datetime] = None

    systolic_bp: Optional[int] = None
    diastolic_bp: Optional[int] = None
    bp_status: Optional[str] = None
    bp_timestamp: Optional[datetime] = None # Timestamp specific to BP reading

    oxygen_saturation: Optional[float] = None
    oxygen_status: Optional[str] = None
    oxygen_timestamp: Optional[datetime] = None

    glucose_level: Optional[float] = None
    glucose_status: Optional[str] = None
    glucose_timestamp: Optional[datetime] = None

    respiratory_rate: Optional[int] = None
    respiratory_rate_status: Optional[str] = None
    respiratory_rate_timestamp: Optional[datetime] = None

    temperature_celsius: Optional[float] = None
    temperature_status: Optional[str] = None
    temperature_timestamp: Optional[datetime] = None

    # Add other metrics as needed

    class Config:
        from_attributes = True # Not strictly needed if constructing manually

# --- Helper Functions for Status Determination ---
def get_heart_rate_status(hr: Optional[int]) -> Optional[str]:
    if hr is None: return None
    if hr < 50: return "Low (Bradycardia)" # Adjusted lower bound
    if hr > 100: return "High (Tachycardia)"
    return "Normal"

def get_bp_status(systolic: Optional[int], diastolic: Optional[int]) -> Optional[str]:
    if systolic is None or diastolic is None: return None
    if systolic < 90 or diastolic < 60: return "Low"
    if systolic < 120 and diastolic < 80: return "Normal"
    if systolic <= 129 and diastolic < 80: return "Elevated"
    if systolic <= 139 or diastolic <= 89: return "High BP (Stage 1)"
    if systolic >= 140 or diastolic >= 90: return "High BP (Stage 2)"
    if systolic > 180 or diastolic > 120: return "Hypertensive Crisis"
    return "Normal" # Fallback, though conditions should cover all

def get_oxygen_status(spo2: Optional[float]) -> Optional[str]:
    if spo2 is None: return None
    if spo2 < 90: return "Critically Low"
    if spo2 < 95: return "Low"
    return "Normal"

def get_glucose_status(glucose: Optional[float], context: Optional[str] = None) -> Optional[str]: # Context (fasting, post-meal) needed for accuracy
    if glucose is None: return None
    # Simplified - In real app, differentiate fasting/random/post-meal
    if glucose < 70: return "Low (Hypoglycemia)"
    if glucose > 180: return "High (Hyperglycemia)" # Often post-meal threshold
    if glucose > 125: return "Elevated" # Often fasting threshold
    return "Normal"

def get_respiratory_rate_status(rr: Optional[int]) -> Optional[str]:
    if rr is None: return None
    if rr < 12: return "Low (Bradypnea)"
    if rr > 20: return "High (Tachypnea)"
    return "Normal"

def get_temperature_status(temp_c: Optional[float]) -> Optional[str]:
    if temp_c is None: return None
    if temp_c >= 38.0: return "Fever"
    if temp_c >= 37.5: return "Elevated"
    if temp_c < 35.0: return "Low (Hypothermia)"
    return "Normal"

# --- API Endpoints ---

@router.post("", response_model=HealthDataResponse, status_code=status.HTTP_201_CREATED)
async def create_health_data_entry(
    health_data: HealthDataInput,
    current_user: current_user_dependency,
    db: db_dependency
):
    if current_user.role != UserRole.patient:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only patients can log health data.")

    print(f"Received health data from user {current_user.id}: {health_data.model_dump(exclude_none=True)}")

    # Ensure at least one actual metric value is provided (not just timestamp)
    provided_metrics = {k: v for k, v in health_data.model_dump(exclude_none=True).items() if k != 'timestamp'}
    if not provided_metrics:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="At least one health metric value must be provided.")

    # Use provided timestamp or default to now (UTC)
    entry_timestamp = health_data.timestamp if health_data.timestamp else datetime.now(timezone.utc)
    # If naive datetime is provided by chance, make it UTC
    if health_data.timestamp and health_data.timestamp.tzinfo is None:
        entry_timestamp = health_data.timestamp.replace(tzinfo=timezone.utc)


    db_entry = HealthDataEntry(
        user_id=current_user.id,
        timestamp=entry_timestamp,
        heart_rate=health_data.heart_rate,
        systolic_bp=health_data.systolic_bp,
        diastolic_bp=health_data.diastolic_bp,
        oxygen_saturation=health_data.oxygen_saturation,
        glucose_level=health_data.glucose_level,
        respiratory_rate=health_data.respiratory_rate,
        temperature_celsius=health_data.temperature_celsius,

        heart_rate_status=get_heart_rate_status(health_data.heart_rate),
        bp_status=get_bp_status(health_data.systolic_bp, health_data.diastolic_bp),
        oxygen_status=get_oxygen_status(health_data.oxygen_saturation),
        glucose_status=get_glucose_status(health_data.glucose_level),
        respiratory_rate_status=get_respiratory_rate_status(health_data.respiratory_rate),
        temperature_status=get_temperature_status(health_data.temperature_celsius)
    )
    try:
        db.add(db_entry)
        db.commit()
        db.refresh(db_entry)
        print(f"Health data entry {db_entry.id} created for user {current_user.id}")
        return db_entry
    except Exception as e:
        db.rollback()
        print(f"Error creating health data entry: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not save health data.")


@router.get("/me", response_model=List[HealthDataResponse])
async def get_my_health_data(
    current_user: current_user_dependency,
    db: db_dependency,
    limit: Optional[int] = Query(100, ge=1, le=1000),
    start_date: Optional[py_date] = Query(None), # YYYY-MM-DD
    end_date: Optional[py_date] = Query(None)   # YYYY-MM-DD
):
    if current_user.role != UserRole.patient:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access restricted to patients.")

    print(f"Fetching health data for user {current_user.id} with limit {limit}, start: {start_date}, end: {end_date}")
    query = db.query(HealthDataEntry).filter(HealthDataEntry.user_id == current_user.id)

    if start_date:
        # Convert date to datetime at start of day (UTC) for comparison
        start_datetime = datetime.combine(start_date, datetime.min.time(), tzinfo=timezone.utc)
        query = query.filter(HealthDataEntry.timestamp >= start_datetime)
    if end_date:
        # Convert date to datetime at end of day (UTC) for comparison
        end_datetime = datetime.combine(end_date, datetime.max.time(), tzinfo=timezone.utc)
        query = query.filter(HealthDataEntry.timestamp <= end_datetime)

    entries = query.order_by(HealthDataEntry.timestamp.desc()).limit(limit).all()
    print(f"Found {len(entries)} health data entries.")
    return entries

# New Endpoint
@router.get("/me/latest-snapshot", response_model=Optional[LatestHealthSnapshot])
async def get_my_latest_health_snapshot(
    current_user: current_user_dependency,
    db: db_dependency
):
    print(f"Fetching latest health snapshot for user {current_user.id}")
    snapshot = {}
    metrics_and_status = [
        ("heart_rate", "heart_rate_status"),
        ("systolic_bp", "bp_status"), # For BP, we'll fetch systolic_bp and diastolic_bp together
        ("oxygen_saturation", "oxygen_status"),
        ("glucose_level", "glucose_status"),
        ("respiratory_rate", "respiratory_rate_status"),
        ("temperature_celsius", "temperature_status")
    ]

    for metric_field, status_field in metrics_and_status:
        latest_entry = None
        if metric_field == "systolic_bp":  # Special handling for BP
            latest_entry = db.query(
                HealthDataEntry.systolic_bp,
                HealthDataEntry.diastolic_bp,
                HealthDataEntry.bp_status,
                HealthDataEntry.timestamp
            ).filter(
                HealthDataEntry.user_id == current_user.id,
                HealthDataEntry.systolic_bp.isnot(None),
                HealthDataEntry.diastolic_bp.isnot(None)
            ).order_by(desc(HealthDataEntry.timestamp)).first()

            if latest_entry:
                snapshot['systolic_bp'] = latest_entry[0]
                snapshot['diastolic_bp'] = latest_entry[1]
                snapshot['bp_status'] = latest_entry[2]
                snapshot['bp_timestamp'] = latest_entry[3]
        else:
            # For other metrics, get the value, its specific status, and timestamp
            latest_entry = db.query(
                getattr(HealthDataEntry, metric_field), # e.g., HealthDataEntry.heart_rate
                getattr(HealthDataEntry, status_field), # e.g., HealthDataEntry.heart_rate_status
                HealthDataEntry.timestamp
            ).filter(
                HealthDataEntry.user_id == current_user.id,
                getattr(HealthDataEntry, metric_field).isnot(None) # Ensure the metric itself has a value
            ).order_by(desc(HealthDataEntry.timestamp)).first()

            if latest_entry:
                snapshot[metric_field] = getattr(latest_entry, metric_field)
                snapshot[status_field] = getattr(latest_entry, status_field)
                snapshot[metric_field + "_timestamp"] = latest_entry.timestamp # e.g. heart_rate_timestamp

    if not snapshot: # If no data at all was found for any metric
        return None
    return LatestHealthSnapshot(**snapshot) # Create Pydantic model from dict

@router.get("/patient/{patient_id}", response_model=List[HealthDataResponse])
async def get_patient_health_data_for_doctor(
    patient_id: int,
    current_doctor: current_doctor_dependency, # Doctor authentication
    db: db_dependency,
    limit: Optional[int] = Query(200, ge=1, le=1000, description="Number of recent entries to fetch"), # Default limit 200 for charts
    start_date: Optional[py_date] = Query(None),
    end_date: Optional[py_date] = Query(None)
):
    """
    Allows an authenticated doctor to fetch health data entries for a specific patient.
    Includes a basic check to see if the doctor has any appointment record with the patient.
    """
    print(f"Doctor {current_doctor.id} attempting to fetch health data for patient {patient_id}")

    # 1. Verify patient exists and is actually a patient
    patient = db.query(User).filter(User.id == patient_id, User.role == UserRole.patient).first()
    if not patient:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found.")

    # 2. Authorization Check: Does this doctor have any appointment (any status) with this patient?
    # This is a basic check. A more robust system might have explicit doctor-patient linking.
    association_check = db.query(Appointment.id).filter(
        Appointment.doctor_id == current_doctor.id,
        Appointment.patient_id == patient_id
    ).first()

    if not association_check:
        # If no association, doctor cannot view this patient's private health data
        print(f"Authorization failed: Doctor {current_doctor.id} not associated with patient {patient_id}.")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not authorized to view this patient's health data."
        )
    print(f"Doctor {current_doctor.id} is authorized to view patient {patient_id} data.")

    # 3. Fetch health data for the specified patient
    query = db.query(HealthDataEntry).filter(HealthDataEntry.user_id == patient_id)

    if start_date:
        start_datetime = datetime.combine(start_date, datetime.min.time(), tzinfo=timezone.utc)
        query = query.filter(HealthDataEntry.timestamp >= start_datetime)
    if end_date:
        end_datetime = datetime.combine(end_date, datetime.max.time(), tzinfo=timezone.utc)
        query = query.filter(HealthDataEntry.timestamp <= end_datetime)

    entries = query.order_by(HealthDataEntry.timestamp.desc()).limit(limit).all()
    print(f"Found {len(entries)} health data entries for patient {patient_id} for doctor view.")
    return entries
# --- *** END OF NEW ENDPOINT *** ---