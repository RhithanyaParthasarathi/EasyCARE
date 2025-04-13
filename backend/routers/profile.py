# backend/routers/profile.py
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field # Make sure Field is imported
from sqlalchemy.orm import Session, joinedload # Import joinedload for eager loading
from typing import Annotated, Optional, Union # Import Union

from backend.database import get_db
# Import relevant models
from backend.models import User, UserRole, PatientProfile, DoctorProfile
# Import the dependency to get the logged-in user
from backend.routers.auth import get_current_active_user

# --- Pydantic Models for Profile Data ---

# Model for updating Patient specific fields
class PatientProfileUpdate(BaseModel):
    # Include all fields from PatientProfile model that can be updated
    # Use Field for validation constraints
    full_name: Optional[str] = Field(None, min_length=1, description="Patient's full name")
    age: Optional[int] = Field(None, gt=0, description="Patient's age in years (must be > 0)")
    gender: Optional[str] = Field(None, description="Patient's gender (e.g., Male, Female, Other)") # Consider Literal/Enum later
    height_cm: Optional[int] = Field(None, gt=0, description="Patient's height in cm (must be > 0)")
    weight_kg: Optional[float] = Field(None, gt=0, description="Patient's weight in kg (must be > 0)")
    blood_type: Optional[str] = Field(None, description="Patient's blood type (e.g., O+, A-)") # Consider Literal/Enum later

    class Config:
         extra = 'forbid' # Prevent extra fields being sent

# Model for updating Doctor specific fields
class DoctorProfileUpdate(BaseModel):
    # Include all fields from DoctorProfile model that can be updated
    full_name: Optional[str] = Field(None, min_length=1, description="Doctor's full name")
    specialty: Optional[str] = Field(None, description="Doctor's medical specialty")
    hospital_affiliation: Optional[str] = Field(None, description="Hospital or clinic affiliation")
    years_experience: Optional[int] = Field(None, ge=0, description="Years of professional experience (>= 0)")
    qualifications: Optional[str] = Field(None, description="Summary of qualifications (e.g., MBBS, MD)")
    about_me: Optional[str] = Field(None, description="Brief professional bio")

    class Config:
         extra = 'forbid'

# --- Pydantic Models for Profile Response ---
# Separate models for clarity when embedding profile data
class PatientProfileResponse(BaseModel):
    # Include fields from PatientProfile model you want to return
    user_id: int
    full_name: Optional[str] = None
    age: Optional[int] = None
    gender: Optional[str] = None
    height_cm: Optional[int] = None
    weight_kg: Optional[float] = None
    blood_type: Optional[str] = None
    is_complete: bool

    class Config: from_attributes = True

class DoctorProfileResponse(BaseModel):
    # Include fields from DoctorProfile model you want to return
    user_id: int
    full_name: Optional[str] = None
    specialty: Optional[str] = None
    hospital_affiliation: Optional[str] = None
    years_experience: Optional[int] = None
    qualifications: Optional[str] = None
    about_me: Optional[str] = None
    is_complete: bool

    class Config: from_attributes = True

# Unified response model for GET /me
class UserProfileResponse(BaseModel):
    # From User model
    id: int
    username: str
    email: EmailStr
    role: UserRole
    license_number: Optional[str] = None # From User model

    # Embed the specific profile based on role
    profile: Optional[Union[PatientProfileResponse, DoctorProfileResponse]] = None # Use response models
    is_profile_complete: bool = False # Overall completion status

    class Config: from_attributes = True # Still needed for base User fields


# --- Router Setup ---
router = APIRouter(
    prefix="/profile", # Use /profile as the prefix for these endpoints
    tags=["profile"],  # Tag for API documentation
)

db_dependency = Annotated[Session, Depends(get_db)]
current_user_dependency = Annotated[User, Depends(get_current_active_user)] # Use general logged-in user dependency

# --- Endpoints ---

@router.get("/me", response_model=UserProfileResponse)
async def read_users_me(
    current_user: current_user_dependency, # Gets the logged-in user object
    db: db_dependency
    ):
    """
    Get profile details for the currently authenticated user.
    Eagerly loads the appropriate profile based on the user's role.
    """
    print(f"Fetching profile for user: {current_user.username}, Role: {current_user.role.value}") # DEBUG

    profile_data_response = None
    is_complete = False

    # Query the User again but explicitly load the profile relationship
    # This avoids lazy loading issues and ensures profile data is available
    if current_user.role == UserRole.patient:
        user_with_profile = db.query(User).options(
            joinedload(User.patient_profile) # Eagerly load patient profile
        ).filter(User.id == current_user.id).first()
        if user_with_profile and user_with_profile.patient_profile:
            profile_data_response = PatientProfileResponse.model_validate(user_with_profile.patient_profile)
            is_complete = user_with_profile.patient_profile.is_complete
            print("Patient profile data found and loaded.") # DEBUG
    elif current_user.role == UserRole.doctor:
        user_with_profile = db.query(User).options(
            joinedload(User.doctor_profile) # Eagerly load doctor profile
        ).filter(User.id == current_user.id).first()
        if user_with_profile and user_with_profile.doctor_profile:
            profile_data_response = DoctorProfileResponse.model_validate(user_with_profile.doctor_profile)
            is_complete = user_with_profile.doctor_profile.is_complete
            print("Doctor profile data found and loaded.") # DEBUG
    else:
        # Should not happen if role is enforced, but handle case
        user_with_profile = current_user # Use the user object directly if no profile expected

    if not user_with_profile:
        # This means the user from the token wasn't found, auth dependency should have caught this
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    # Construct the final response
    response = UserProfileResponse(
        id=user_with_profile.id,
        username=user_with_profile.username,
        email=user_with_profile.email,
        role=user_with_profile.role,
        license_number=user_with_profile.license_number,
        profile=profile_data_response, # Embed the specific profile model instance
        is_profile_complete=is_complete # Use flag fetched from profile table
    )
    return response


@router.put("/me/patient", response_model=UserProfileResponse)
async def update_patient_profile(
    profile_data: PatientProfileUpdate, # Expect patient data in request body
    db: db_dependency,
    current_user: current_user_dependency # Ensure user is logged in
):
    """Update profile details for the currently authenticated PATIENT."""
    if current_user.role != UserRole.patient:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only patients can update this profile.")

    print(f"Attempting to update patient profile for user {current_user.id}") # DEBUG
    # Get the existing profile or create a new one if it doesn't exist
    profile = db.query(PatientProfile).filter(PatientProfile.user_id == current_user.id).first()
    if not profile:
        profile = PatientProfile(user_id=current_user.id)
        db.add(profile)
        print(f"Creating new PatientProfile for user {current_user.id}") # DEBUG

    # Get fields from request that were actually sent (exclude unset)
    update_data = profile_data.model_dump(exclude_unset=True)
    print(f"Received update data for patient: {update_data}") # DEBUG
    updated = False
    for key, value in update_data.items():
        if hasattr(profile, key) and value is not None: # Check if field exists and value provided
            setattr(profile, key, value)
            updated = True

    if updated:
        # Logic to determine if profile is now complete (customize as needed)
        # Example: Check if certain essential fields are now filled
        is_now_complete = bool(profile.full_name and profile.age and profile.gender) # Basic example
        if is_now_complete and not profile.is_complete:
             profile.is_complete = True
             print(f"Marking patient profile complete for user: {current_user.username}") # DEBUG
        elif not is_now_complete and profile.is_complete:
            # Optional: If user removes required data, mark incomplete again?
            # profile.is_complete = False
             pass


        try:
            db.commit()
            db.refresh(profile) # Get any DB defaults/updates
            print("Patient profile committed successfully.") # DEBUG
        except Exception as e:
            db.rollback()
            print(f"Error committing patient profile update: {e}") # DEBUG
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Database error: {e}")
    else:
         print("No actual data fields were updated.") # DEBUG

    # Return the full updated profile using the GET endpoint logic
    return await read_users_me(current_user, db)


@router.put("/me/doctor", response_model=UserProfileResponse)
async def update_doctor_profile(
    profile_data: DoctorProfileUpdate, # Expect doctor data in request body
    db: db_dependency,
    current_user: current_user_dependency # Ensure user is logged in
):
    """Update profile details for the currently authenticated DOCTOR."""
    if current_user.role != UserRole.doctor:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only doctors can update this profile.")

    print(f"Attempting to update doctor profile for user {current_user.id}") # DEBUG
    # Get or create profile record
    profile = db.query(DoctorProfile).filter(DoctorProfile.user_id == current_user.id).first()
    if not profile:
        profile = DoctorProfile(user_id=current_user.id)
        db.add(profile)
        print(f"Creating new DoctorProfile for user {current_user.id}") # DEBUG

    update_data = profile_data.model_dump(exclude_unset=True)
    print(f"Received update data for doctor: {update_data}") # DEBUG
    updated = False
    for key, value in update_data.items():
        if hasattr(profile, key) and value is not None:
             # Add specific validation here if needed (e.g., for years_experience format)
            setattr(profile, key, value)
            updated = True

    if updated:
        # Logic to determine if doctor profile is now complete
        # Example: Check if key fields like specialty, qualifications, name are filled
        is_now_complete = bool(profile.full_name and profile.specialty and profile.qualifications) # Basic example
        if is_now_complete and not profile.is_complete:
            profile.is_complete = True
            print(f"Marking doctor profile complete for user: {current_user.username}") # DEBUG
        elif not is_now_complete and profile.is_complete:
             # profile.is_complete = False # Optional: Revert if user deletes required info
             pass

        try:
            db.commit()
            db.refresh(profile)
            print("Doctor profile committed successfully.") # DEBUG
        except Exception as e:
            db.rollback()
            print(f"Error committing doctor profile update: {e}") # DEBUG
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Database error: {e}")
    else:
         print("No actual data fields were updated.") # DEBUG

    # Return the full updated profile using the GET endpoint logic
    return await read_users_me(current_user, db)