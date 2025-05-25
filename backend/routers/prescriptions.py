# backend/routers/prescriptions.py

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, selectinload, joinedload
from typing import Annotated, List, Optional
from pydantic import BaseModel, Field
from datetime import date,datetime # Import date

# Your project imports
from database import get_db
from models import User, UserRole, Prescription, PrescriptionMedication # Import necessary models
from routers.auth import get_current_doctor, get_current_active_user # Use Doctor auth dependency

# --- Pydantic models for this router ---
class MedicationInput(BaseModel):
    # Field names here should match keys expected from frontend JS
    medication_name: str = Field(..., min_length=1)
    dosage: Optional[str] = None
    frequency: Optional[str] = None
    duration: Optional[str] = None
    instructions: Optional[str] = None

class PrescriptionCreate(BaseModel):
    # Field names here should match keys sent in frontend payload
    patient_id: int
    prescription_date: date # Expects YYYY-MM-DD, validated by Pydantic
    patient_age: Optional[int] = None # Optional age
    medications: List[MedicationInput] = Field(..., min_length=1) # List of medications

class PrescriptionBasicResponse(BaseModel): # Simple response
    message: str
    prescription_id: int

# --- NEW Pydantic Models for Response ---

class MedicationResponse(BaseModel): # Details for one medication line item
    id: int
    medication_name: str
    dosage: Optional[str] = None
    frequency: Optional[str] = None
    duration: Optional[str] = None
    instructions: Optional[str] = None

    class Config: from_attributes = True

class PrescriptionResponse(BaseModel): # Details for one full prescription
    id: int
    doctor_id: Optional[int] = None # Might want doctor's name instead?
    doctor_name: Optional[str] = None # Need to fetch this if needed
    prescription_date: date
    created_at: datetime # When it was created
    medications: List[MedicationResponse] = [] # List of medications

    class Config: from_attributes = True

# --- End Pydantic Models ---


# --- Router Setup ---
router = APIRouter(
    prefix="/prescriptions", # Base path for endpoints in this file
    tags=["prescriptions"],  # Tag for API docs
)

db_dependency = Annotated[Session, Depends(get_db)]
# Only doctors can create prescriptions
current_doctor_dependency = Annotated[User, Depends(get_current_doctor)]
# *** ADD Dependency for any logged-in user ***
current_user_dependency = Annotated[User, Depends(get_current_active_user)]
# --- End Router Setup ---


# --- API Endpoint ---
@router.post("", status_code=status.HTTP_201_CREATED, response_model=PrescriptionBasicResponse) # POST /prescriptions
async def create_prescription(
    prescription_data: PrescriptionCreate, # Validate request body using Pydantic model
    db: db_dependency,
    current_doctor: current_doctor_dependency # Ensure only logged-in doctor can use
):
    """
    Creates a new prescription written by the logged-in doctor
    for the specified patient, including associated medications.
    """
    print(f"Received prescription creation request from Dr. {current_doctor.username} (ID: {current_doctor.id}) for patient ID: {prescription_data.patient_id}") # DEBUG

    # Optional: Verify the patient exists and is actually a patient
    patient = db.query(User).filter(User.id == prescription_data.patient_id, User.role == UserRole.patient).first()
    if not patient:
        print(f"Error: Patient with ID {prescription_data.patient_id} not found or is not a patient.") # DEBUG
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Patient with ID {prescription_data.patient_id} not found.")

    # Create the main Prescription database record
    db_prescription = Prescription(
        doctor_id=current_doctor.id, # ID of the doctor writing it
        patient_id=prescription_data.patient_id, # ID from the request body
        prescription_date=prescription_data.prescription_date # Date from the request body
        # created_at is handled by server_default in the model
    )
    db.add(db_prescription) # Add parent object first

    # Ensure parent object gets an ID before adding children if not using cascade correctly
    # Though cascade should handle this if relationship is set up. Flush is safer sometimes.
    try:
        db.flush() # Assigns ID to db_prescription without committing yet
        print(f"Prescription object flushed (ID: {db_prescription.id}). Adding medications...") # DEBUG
    except Exception as e:
         db.rollback()
         print(f"Error during DB flush for prescription: {e}")
         raise HTTPException(status_code=500, detail="Database error during prescription pre-save.")


    # Create associated PrescriptionMedication records
    for med_data in prescription_data.medications:
        db_med = PrescriptionMedication(
            prescription_id=db_prescription.id, # Explicitly link to parent ID
            medication_name=med_data.medication_name,
            dosage=med_data.dosage,
            frequency=med_data.frequency,
            duration=med_data.duration,
            instructions=med_data.instructions
        )
        db.add(db_med) # Add each medication line item

    try:
        db.commit() # Commit parent and all children together
        db.refresh(db_prescription) # Refresh to ensure all fields are up-to-date
        print(f"Prescription {db_prescription.id} and its medications committed successfully.") # DEBUG
        # Return success response
        return PrescriptionBasicResponse(
             message="Prescription created successfully",
             prescription_id=db_prescription.id
        )
    except Exception as e:
        db.rollback() # Rollback transaction on error
        print(f"Error committing prescription: {e}") # Log the specific error
        # Consider more specific error checks (e.g., IntegrityError) if needed
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Database error saving prescription.")
# --- End API Endpoint ---

# --- TODO: Add GET endpoints later for patients/doctors to view prescriptions ---
# e.g., GET /prescriptions/my (for patient)
# e.g., GET /prescriptions/patient/{patient_id} (for doctor)

# --- *** ADD NEW GET Endpoint for Patient *** ---
@router.get("/my", response_model=List[PrescriptionResponse]) # Response is List of the model above
async def get_my_prescriptions(
    db: db_dependency,
    current_user: current_user_dependency
):
    """
    Fetches all prescriptions issued TO the currently logged-in patient,
    including medication details and doctor name. Ordered by most recent.
    """
    if current_user.role != UserRole.patient:
        return []

    print(f"Fetching prescriptions for patient {current_user.id}")

    # Query prescriptions with eager loading
    prescriptions_db = db.query(Prescription).options(
        selectinload(Prescription.medications),
        # Eagerly load Doctor and their profile to get the name efficiently
        joinedload(Prescription.doctor).joinedload(User.doctor_profile)
    ).filter(
        Prescription.patient_id == current_user.id
    ).order_by(
        Prescription.prescription_date.desc(),
        Prescription.created_at.desc()
    ).all()

    print(f"Found {len(prescriptions_db)} prescriptions in DB.")

    # *** MANUALLY CONSTRUCT RESPONSE TO INCLUDE DOCTOR NAME ***
    response_data: List[PrescriptionResponse] = []
    for presc in prescriptions_db:
        # Prepare medication list for this prescription
        med_list = [MedicationResponse.model_validate(med) for med in presc.medications]

        # Get doctor name safely
        doc_name = None
        if presc.doctor: # Check if doctor relationship loaded
            if presc.doctor.doctor_profile and presc.doctor.doctor_profile.full_name:
                doc_name = presc.doctor.doctor_profile.full_name # Prefer full name from profile
            else:
                doc_name = presc.doctor.username # Fallback to username
        else:
             print(f"Warning: Doctor relationship not loaded for Prescription ID {presc.id}")

        # Create the response object for this prescription
        response_data.append(
            PrescriptionResponse( # Use the correct response model
                id=presc.id,
                doctor_id=presc.doctor_id,
                doctor_name=doc_name, # Assign the fetched/derived name
                prescription_date=presc.prescription_date,
                created_at=presc.created_at,
                medications=med_list
            )
        )
    # *** END MANUAL CONSTRUCTION ***

    return response_data # Return the manually constructed list
# --- End GET /my endpoint ---
# --- TODO: Add endpoint for DOCTOR to get prescriptions for a specific patient ---
# e.g., GET /patient/{patient_id}

# --- *** NEW: Endpoint for DOCTOR to get a specific patient's prescriptions *** ---
@router.get("/patient/{patient_id}", response_model=List[PrescriptionResponse])
async def get_prescriptions_for_patient_by_doctor(
    patient_id: int, # Path parameter
    db: db_dependency,
    current_doctor: current_doctor_dependency # Ensures only a logged-in doctor can access
):
    """
    Fetches all prescriptions for a specific patient ID.
    Only accessible by logged-in doctors.
    """
    print(f"Doctor {current_doctor.username} (ID: {current_doctor.id}) requesting prescriptions for patient ID: {patient_id}")

    # Verify the patient exists
    patient = db.query(User).filter(User.id == patient_id, User.role == UserRole.patient).first()
    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Patient with ID {patient_id} not found."
        )

    # Query prescriptions for the specified patient_id
    prescriptions_db = db.query(Prescription).options(
        selectinload(Prescription.medications),
        joinedload(Prescription.doctor).joinedload(User.doctor_profile) # Eager load doctor who prescribed
    ).filter(
        Prescription.patient_id == patient_id
    ).order_by(
        Prescription.prescription_date.desc(),
        Prescription.created_at.desc()
    ).all()

    print(f"Found {len(prescriptions_db)} prescriptions in DB for patient {patient_id}.")

    response_data: List[PrescriptionResponse] = []
    for presc in prescriptions_db:
        med_list = [MedicationResponse.model_validate(med) for med in presc.medications]
        doc_name = None # Name of the doctor who wrote *this specific prescription*
        if presc.doctor:
            if presc.doctor.doctor_profile and presc.doctor.doctor_profile.full_name:
                doc_name = presc.doctor.doctor_profile.full_name
            else:
                doc_name = presc.doctor.username
        else:
            print(f"Warning: Doctor relationship not loaded for Prescription ID {presc.id}")

        response_data.append(
            PrescriptionResponse(
                id=presc.id,
                doctor_id=presc.doctor_id,
                doctor_name=doc_name,
                prescription_date=presc.prescription_date,
                created_at=presc.created_at,
                medications=med_list
            )
        )
    return response_data
# --- End NEW Endpoint ---