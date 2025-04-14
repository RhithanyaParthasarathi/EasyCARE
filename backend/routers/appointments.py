# backend/routers/appointments.py
from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import distinct
from typing import Annotated, List, Optional
from backend.database import get_db
from backend.models import TimeSlot, User, UserRole, Appointment, AppointmentStatus # Ensure correct import
from sqlalchemy import exc, and_,func
from datetime import datetime, date as py_date
from datetime import timezone
# Import the new dependency
from backend.routers.auth import get_current_doctor, get_current_active_user
from backend.models import Notification #import notification model

router = APIRouter(
    prefix="/appointments",
    tags=["appointments"],
)

db_dependency = Annotated[Session, Depends(get_db)]
# Dependency for endpoints managed by the logged-in doctor
current_doctor_dependency = Annotated[User, Depends(get_current_doctor)]

# --- Pydantic Models (NO end_time) ---

# *** ADD THIS NEW MODEL ***

# *** ADD THIS NEW MODEL ***
class DoctorProfileInfo(BaseModel): # Defines profile fields for the doctor list
     specialty: Optional[str] = None
     years_experience: Optional[int] = None
     about_me: Optional[str] = None # Decide if you want full bio in list

     class Config: from_attributes = True
# *** END OF NEW MODEL ***

class Doctor(BaseModel): # For listing doctors
    id: int
    username: str
    #email: str
    #license_number: Optional[str] = None
    profile: Optional[DoctorProfileInfo] = None

    class Config:
        from_attributes = True


class TimeSlotBase(BaseModel): # Base for input/output
    start_time: str # Expect HH:MM (24hr)

    @field_validator("start_time")
    @classmethod
    def validate_time_format(cls, value):
        try:
            # Validate format strictly HH:MM
            datetime.strptime(value, "%H:%M")
            return value
        except ValueError:
            raise ValueError("Time must be in HH:MM (24-hour) format")

class TimeSlotResponse(TimeSlotBase): # For returning saved slots
    id: int
    date: py_date # Return date object

    class Config:
        from_attributes = True

class ScheduleSaveSlot(TimeSlotBase): # For receiving slots to save
    pass # Only needs start_time

class ScheduleSaveRequest(BaseModel): # Request body for saving
    date: str # Expect YYYY-MM-DD string
    slots: List[ScheduleSaveSlot] # List of slots for that date

    @field_validator("date")
    @classmethod
    def validate_and_convert_date(cls, value):
        try:
            # Validate format and convert to date object for use in endpoint
            return datetime.strptime(value, "%Y-%m-%d").date()
        except ValueError:
            raise ValueError("Date must be in YYYY-MM-DD format")

class AppointmentRequest(BaseModel): # For booking request
    doctor_id: int
    date: str  # YYYY-MM-DD
    time: str  # HH:MM (24hr) - patient selects start_time

class PatientInfo(BaseModel): # For embedding patient details
    id: int
    username: str
    # email: EmailStr # Optionally include email if needed

    class Config:
        from_attributes = True

class AppointmentRequestDetails(BaseModel): # Response model for GET /requests
    id: int # Appointment ID
    appointment_date: py_date
    status: AppointmentStatus
    created_at: datetime # When the request was made
    # Include related data
    patient: PatientInfo # Embed patient info
    start_time: str # Get start time from the related timeslot
    doctor: Doctor

    class Config:
        from_attributes = True

# Add near top of appointments.py or in a utils file
def format_time_ampm(time_str_24: str) -> str:
    """Converts HH:MM string to h:mm AM/PM format."""
    if not time_str_24:
        return "N/A"
    try:
        time_obj = datetime.strptime(time_str_24, "%H:%M")
        return time_obj.strftime("%I:%M %p").lstrip('0') # Format and remove leading 0 from hour
    except ValueError:
        print(f"Warning: Could not format time '{time_str_24}' to AM/PM.")
        return time_str_24 # Return original on error

# --- API Endpoints ---

@router.get("/doctors", response_model=List[Doctor]) # Response uses NEW Doctor model
async def get_doctors(db: db_dependency):
    """
    Lists all users with the doctor role, including selected profile info.
    """
    print("Fetching list of doctors with profiles...")
    doctors_query = db.query(User).options(
        joinedload(User.doctor_profile) # Eagerly load DoctorProfile relationship from User model
    ).filter(User.role == UserRole.doctor).order_by(User.username)

    doctors_result = doctors_query.all()
    print(f"Found {len(doctors_result)} doctors.")

    # Manually construct response to ensure correct nesting and field selection
    response_list: List[Doctor] = []
    for doc in doctors_result:
         profile_info_subset = None
         if doc.doctor_profile: # Check if the eager-loaded profile exists
             # Create the DoctorProfileInfo subset from the full profile
             profile_info_subset = DoctorProfileInfo.model_validate(doc.doctor_profile)

         # Create the main Doctor response object including the profile subset
         response_list.append(
             Doctor(
                 id=doc.id,
                 username=doc.username,
                 # email=doc.email, # Uncomment if needed
                 # license_number=doc.license_number, # Uncomment if needed
                 profile=profile_info_subset # Assign the subset object
             )
         )

    return response_list

# --- Schedule Management for Logged-in Doctor ---

@router.get("/schedule", response_model=List[TimeSlotResponse])
async def get_my_schedule_for_date(
    current_doctor: current_doctor_dependency, # Use auth dependency
    db: db_dependency, # <<< CORRECTED
    date: str = Query(..., description="Date in YYYY-MM-DD format") # Date from query param
):
    """Gets the logged-in doctor's schedule for a specific date."""
    try:
        query_date = datetime.strptime(date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid date format. Use YYYY-MM-DD.")

    # Fetch slots for *this* doctor on *this* date
    time_slots = db.query(TimeSlot).filter(
        TimeSlot.doctor_id == current_doctor.id,
        TimeSlot.date == query_date
    ).order_by(TimeSlot.start_time).all()

    return time_slots # Returns empty list if no schedule found

@router.put("/schedule", status_code=status.HTTP_200_OK)
async def save_my_schedule(
    current_doctor: current_doctor_dependency, # Use auth dependency
    schedule_request: ScheduleSaveRequest, # Get date & slots from body
    db: db_dependency 
):
    """
    Saves/updates the logged-in doctor's schedule for the specific date
    provided in the request body. Replaces the entire schedule for that day.
    """
    target_date = schedule_request.date # Already a date object from Pydantic validation

    # Use a transaction
    try:
        # 1. Delete ALL existing slots for this doctor on this specific date
        db.query(TimeSlot).filter(
            TimeSlot.doctor_id == current_doctor.id,
            TimeSlot.date == target_date
        ).delete(synchronize_session=False) # Efficient delete

        # 2. Add the new slots provided in the request
        new_slots_to_add = []
        added_times = set() # To prevent duplicates *within the same request*
        for slot_data in schedule_request.slots:
             if slot_data.start_time not in added_times:
                new_time_slot = TimeSlot(
                    start_time=slot_data.start_time, # Only start_time
                    date=target_date,
                    doctor_id=current_doctor.id
                )
                new_slots_to_add.append(new_time_slot)
                added_times.add(slot_data.start_time)

        if new_slots_to_add:
            db.add_all(new_slots_to_add)

        # 3. Commit changes
        db.commit()

    except Exception as e:
        db.rollback() # Important: undo changes on error
        print(f"Error saving schedule for doctor {current_doctor.id} on {target_date}: {e}") # Log for debugging
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to save schedule due to a server error.")

    return {"message": f"Schedule for {target_date.strftime('%Y-%m-%d')} saved successfully.", "slots_added": len(new_slots_to_add)}

@router.delete("/schedule", status_code=status.HTTP_200_OK)
async def delete_my_schedule_for_date(
    current_doctor: current_doctor_dependency, # Use auth dependency
    db: db_dependency ,
    date: str = Query(..., description="Date in YYYY-MM-DD format") # Date from query param
    
):
    """Deletes the logged-in doctor's schedule for a specific date."""
    try:
        target_date = datetime.strptime(date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid date format. Use YYYY-MM-DD.")

    try:
        # Delete slots for this doctor on this date
        deleted_count = db.query(TimeSlot).filter(
            TimeSlot.doctor_id == current_doctor.id,
            TimeSlot.date == target_date
        ).delete(synchronize_session=False)

        db.commit()

    except Exception as e:
        db.rollback()
        print(f"Error deleting schedule for doctor {current_doctor.id} on {target_date}: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to delete schedule due to a server error.")

    if deleted_count > 0:
        return {"message": f"Schedule for {target_date.strftime('%Y-%m-%d')} deleted successfully."}
    else:
        # It's okay if nothing was there to delete
        return {"message": f"No schedule found for {target_date.strftime('%Y-%m-%d')} to delete."}

# --- Patient Facing Endpoint ---

@router.get("/doctors/{doctor_id}/schedule", response_model=List[TimeSlotResponse])
async def get_doctor_schedule_for_patient(
    doctor_id: int,
    db: db_dependency ,
    date: str = Query(..., description="Date in YYYY-MM-DD format"), # Date from query param
    
):
    """Gets a specific doctor's available schedule for a specific date (for patient viewing)."""
    # Validate doctor exists first
    doctor = db.query(User).filter(User.id == doctor_id, User.role == UserRole.doctor).first()
    if not doctor:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Doctor not found")

    try:
        query_date = datetime.strptime(date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid date format. Use YYYY-MM-DD.")

    # Fetch slots for the specific doctor and date
    # In future, add filter like `.filter(TimeSlot.is_booked == False)` if you add booking status
   # Inside get_doctor_schedule_for_patient function
    time_slots = db.query(TimeSlot).filter(
    TimeSlot.doctor_id == doctor_id,
    TimeSlot.date == query_date,
    TimeSlot.is_booked == False # <<< ADD THIS FILTER
    ).order_by(TimeSlot.start_time).all()

    # Returns an empty list if no slots are scheduled or available (HTTP 200)
    return time_slots

# --- Booking Endpoint (Basic Validation) ---

# --- REPLACED Booking Endpoint ---
@router.post("/book", status_code=status.HTTP_201_CREATED)
async def book_appointment(
    request: AppointmentRequest, # Data sent by frontend (doctor_id, date, time)
    db: db_dependency,
    # Use dependency to get the currently logged-in user making the request
    current_user: Annotated[User, Depends(get_current_active_user)]
):
    """
    Creates an appointment request for the logged-in patient
    and marks the corresponding timeslot as booked.
    """

    # 1. Authorize: Ensure the user is a patient
    if current_user.role != UserRole.patient:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only patients can book appointments."
        )
    current_patient_id = current_user.id # Get ID from the authenticated user object

    # 2. Validate Input Data
    # Validate doctor exists
    doctor = db.query(User).filter(User.id == request.doctor_id, User.role == UserRole.doctor).first()
    if not doctor:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Selected doctor not found.")

    # Validate date and time format
    try:
        appointment_date = datetime.strptime(request.date, "%Y-%m-%d").date()
        appointment_time_str = request.time
        datetime.strptime(appointment_time_str, "%H:%M") # Validate HH:MM format
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid date (YYYY-MM-DD) or time (HH:MM) format provided.")

    # 3. Transaction: Check Slot Availability & Perform Booking
    try:
        # Find the specific timeslot, ensuring it's for the correct doctor/date/time AND is not already booked
        # Note: For high concurrency, adding .with_for_update() might be needed,
        # but requires careful handling depending on DB backend (less critical for SQLite usually)
        available_slot = db.query(TimeSlot).filter(
            TimeSlot.doctor_id == request.doctor_id,
            TimeSlot.date == appointment_date,
            TimeSlot.start_time == appointment_time_str,
            TimeSlot.is_booked == False # *** The crucial availability check ***
        ).first()

        # If no available slot is found
        if not available_slot:
            # Check if the slot exists but is already booked to give a more specific error
            already_booked = db.query(TimeSlot.id).filter(
                TimeSlot.doctor_id == request.doctor_id,
                TimeSlot.date == appointment_date,
                TimeSlot.start_time == appointment_time_str,
                TimeSlot.is_booked == True
            ).scalar() # Use scalar() to efficiently check existence

            if already_booked:
                # 409 Conflict is appropriate for trying to book an already booked slot
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This time slot has already been booked.")
            else:
                # 404 Not Found if the slot never existed or wasn't scheduled by the doctor
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Selected time slot is not available or does not exist for this doctor on this date.")

        # --- Slot is available, proceed with booking ---

        # 4. Mark the TimeSlot as booked
        print(f"Marking TimeSlot {available_slot.id} as booked.") # Log action
        available_slot.is_booked = True
        db.add(available_slot) # Add to session to stage the change

        # 5. Create the new Appointment record
        print(f"Creating Appointment record for patient {current_patient_id}.") # Log action
        new_appointment = Appointment(
            patient_id=current_patient_id, # Use the authenticated patient's ID
            doctor_id=request.doctor_id,
            timeslot_id=available_slot.id, # Link to the specific TimeSlot
            appointment_date=appointment_date, # Store date on appointment too
            status=AppointmentStatus.PENDING # Initial status
            # created_at/updated_at usually handled by DB default/onupdate
        )
        db.add(new_appointment)

        # 6. Commit the transaction (saves both TimeSlot update and Appointment creation)
        db.commit()
        print("Booking transaction committed.") # Log action

        # 7. Refresh objects to get DB-generated values (like ID, default timestamps)
        db.refresh(new_appointment)
        db.refresh(available_slot)

        print(f"Appointment {new_appointment.id} created successfully.") # Log success

        # Return success response
        return {
            "message": "Appointment requested successfully. Waiting for doctor's confirmation.",
            "appointment_id": new_appointment.id # Return the new appointment ID
            }

    except HTTPException as http_exc:
         db.rollback() # Rollback on known HTTP errors raised above
         print(f"HTTP Exception during booking: {http_exc.detail}") # Log action
         raise http_exc # Re-raise the exception

    except exc.IntegrityError as e: # Catch potential unique constraint violations (e.g., on timeslot_id)
        db.rollback()
        print(f"Database Integrity Error during booking: {e}") # Log action
        # This can happen in race conditions if two requests try to book the exact same slot simultaneously
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Booking conflict occurred. The slot may have just been booked. Please try again.")

    except Exception as e:
        db.rollback() # Rollback on any other unexpected error
        print(f"Unexpected error during booking commit: {e}") # Log action
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not process booking request due to an internal server error.")
    

# --- NEW ENDPOINTS FOR DOCTOR TO MANAGE REQUESTS ---

@router.get("/requests", response_model=List[AppointmentRequestDetails])
async def get_my_appointment_requests(
    db: db_dependency,
    current_doctor: current_doctor_dependency, # Ensures only logged-in doctor can access
    status: Optional[str] = Query(None, description="Filter by status (e.g., PENDING, CONFIRMED, REJECTED)") # Optional filter
):
    """Fetches appointment requests for the logged-in doctor."""
    print(f"Fetching appointment requests for doctor {current_doctor.id}, string filter status: '{status}'") # DEBUG

    query = db.query(Appointment).filter(Appointment.doctor_id == current_doctor.id)

    if status:
        try:
            # Attempt to convert the incoming string (e.g., "PENDING") to the Enum member
            status_enum = AppointmentStatus(status.upper()) # Convert to uppercase for robustness
            query = query.filter(Appointment.status == status_enum) # Use the Enum member in the query
            print(f"Applied filter for status: {status_enum}") # DEBUG
        except ValueError:
            # Handle case where the provided status string is not a valid enum member
            print(f"Warning: Invalid status filter value received: '{status}'. Ignoring filter.") # DEBUG WARNING
            # Optionally raise HTTPException 400 Bad Request? Or just ignore the filter? Ignore for now.
            # raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid status value: {status}")
            pass # Ignore invalid status filter

    # Order by creation time or appointment date as preferred
    appointments = query.options(
        joinedload(Appointment.patient), # Load patient data
        joinedload(Appointment.time_slot) # Load time_slot data (for start_time)
        # No need to explicitly load doctor here, as current_doctor already has it,
        # BUT Pydantic needs the data structured correctly for validation.
        # We can pass the current_doctor object or extract relevant fields.
    ).order_by(Appointment.created_at.desc()).all()

    # Prepare response data, including necessary related info
    response_data = []
    for appt in appointments:
        # Check if required relationships were loaded successfully
        if appt.time_slot and appt.patient:
             try: # Add try-except around model validation for robustness
                response_data.append(
                    AppointmentRequestDetails(
                        id=appt.id,
                        appointment_date=appt.appointment_date,
                        status=appt.status,
                        created_at=appt.created_at,
                        patient=PatientInfo.model_validate(appt.patient),
                        start_time=appt.time_slot.start_time,
                        # *** ADD DOCTOR INFO HERE ***
                        # Since current_doctor IS the doctor for these requests,
                        # we can use the Doctor model to validate/structure it.
                        doctor=Doctor.model_validate(current_doctor)
                        # *** END ADDED DOCTOR INFO ***
                    )
                )
             except Exception as e:
                 # Log if Pydantic validation fails for a specific appointment
                 print(f"Warning: Could not validate Appointment {appt.id} for response. Error: {e}")
        else:
             print(f"Warning: Appointment {appt.id} is missing related Patient or TimeSlot data.")


    print(f"Found {len(response_data)} requests matching filter.")
    return response_data


@router.post("/requests/{appointment_id}/confirm", status_code=status.HTTP_200_OK)
async def confirm_appointment_request(
    appointment_id: int,
    db: db_dependency,
    current_doctor: current_doctor_dependency
):
    """Confirms a pending appointment request."""
    print(f"Attempting to confirm appointment {appointment_id} for doctor {current_doctor.id}") # DEBUG

    # Find the appointment, ensure it belongs to this doctor and is pending
    appointment = db.query(Appointment).filter(
        Appointment.id == appointment_id,
        Appointment.doctor_id == current_doctor.id
    ).first()

    if not appointment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Appointment request not found or you are not authorized.")

    if appointment.status != AppointmentStatus.PENDING:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Appointment is already {appointment.status.value}.")

    # Update status to confirmed
    appointment.status = AppointmentStatus.CONFIRMED

    appointment_time_str = appointment.time_slot.start_time if appointment.time_slot else "N/A"
    formatted_time = format_time_ampm(appointment_time_str) # Format the time


    # --- Create Notification ---
     # Use the formatted time in the message
    notification_message = f"Confirmed: Your appointment with Dr. {current_doctor.username} on {appointment.appointment_date} at {formatted_time} is confirmed."
    new_notification = Notification(
        user_id=appointment.patient_id,
        message=notification_message,
        appointment_id=appointment.id
    )
    db.add(new_notification)
    print(f"Created confirmation notification for user {appointment.patient_id}") # DEBUG
    # --- End Create Notification ---


    db.commit()
    db.refresh(appointment)
    print(f"Appointment {appointment_id} confirmed.") # DEBUG

    # +++ TODO: Implement Notification Logic +++
# Example: send_notification(user_id=appointment.patient_id, message=f"Your appointment request for {appointment.appointment_date} with Dr. {current_doctor.username} has been confirmed.")
# +++++++++++++++++++++++++++++++++++++++++++t

    return {"message": "Appointment confirmed successfully.", "appointment_status": appointment.status}


@router.post("/requests/{appointment_id}/reject", status_code=status.HTTP_200_OK)
async def reject_appointment_request(
    appointment_id: int,
    db: db_dependency,
    current_doctor: current_doctor_dependency
):
    """Rejects a pending appointment request and makes the timeslot available again."""
    print(f"Attempting to reject appointment {appointment_id} for doctor {current_doctor.id}") # DEBUG

    # Find the appointment, ensure it belongs to this doctor and is pending
    appointment = db.query(Appointment).filter(
        Appointment.id == appointment_id,
        Appointment.doctor_id == current_doctor.id
    ).first()

    if not appointment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Appointment request not found or you are not authorized.")

    if appointment.status != AppointmentStatus.PENDING:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Appointment is already {appointment.status.value}.")

    try:
        # Find the related timeslot to make it available again
        time_slot = db.query(TimeSlot).filter(TimeSlot.id == appointment.timeslot_id).first()

        if time_slot:
            time_slot.is_booked = False # Make slot available again
            print(f"Timeslot {time_slot.id} marked as available.") # DEBUG
        else:
             # This shouldn't happen if FK constraint is working, but log it
             print(f"Warning: Could not find TimeSlot {appointment.timeslot_id} for rejected appointment {appointment_id}")

        # Update appointment status to rejected
        appointment.status = AppointmentStatus.REJECTED

        # --- Create Notification ---
        notification_message = f"Rejected: Your appointment request for {appointment.appointment_date} with Dr. {current_doctor.username} was rejected."
        # Add reason later if available
        new_notification = Notification(
            user_id=appointment.patient_id,
            message=notification_message,
            appointment_id=appointment.id
        )
        db.add(new_notification)
        print(f"Created rejection notification for user {appointment.patient_id}") # DEBUG
        # --- End Create Notification ---


        db.commit()
        db.refresh(appointment)
        if time_slot: db.refresh(time_slot)
        print(f"Appointment {appointment_id} rejected.") # DEBUG

         # +++ TODO: Implement Notification Logic +++
    # Example: send_notification(user_id=appointment.patient_id, message=f"Your appointment request for {appointment.appointment_date} with Dr. {current_doctor.username} has been rejected.")
    # +++++++++++++++++++++++++++++++++++++++++++

        return {"message": "Appointment rejected successfully.", "appointment_status": appointment.status}

    except Exception as e:
        db.rollback()
        print(f"Error rejecting appointment {appointment_id}: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to reject appointment.")
    
    #test comment 123

    #add new endpoint

@router.get("/upcoming-confirmed", response_model=Optional[AppointmentRequestDetails]) # Return one or none
async def get_my_next_confirmed_appointment(
    db: db_dependency,
    current_user: Annotated[User, Depends(get_current_active_user)]
):
    """
    Fetches the next upcoming confirmed appointment for the logged-in user
    (either as patient or doctor).
    """
    now_date = datetime.utcnow().date() # Use a distinct variable name

    # --- MODIFIED QUERY with JOIN ---
    query = db.query(Appointment).join(Appointment.time_slot).filter( # Join Appointment to TimeSlot
        Appointment.status == AppointmentStatus.CONFIRMED,
        Appointment.appointment_date >= now_date
    )

    # Filter based on user role
    if current_user.role == UserRole.patient:
        query = query.filter(Appointment.patient_id == current_user.id)
    elif current_user.role == UserRole.doctor:
        query = query.filter(Appointment.doctor_id == current_user.id)
    else:
        return None # Should not happen

    # Correct ORDER BY using the joined table
    upcoming_appointment = query.order_by(
        Appointment.appointment_date.asc(),
        TimeSlot.start_time.asc() # <<< CORRECTED: Order by TimeSlot.start_time directly
    ).first()
    # --- END MODIFIED QUERY ---

    if not upcoming_appointment:
        print(f"No upcoming confirmed appointments found for user {current_user.id}")
        return None

    # Prepare response data (should be okay now)
    if upcoming_appointment.time_slot and upcoming_appointment.patient and upcoming_appointment.doctor:
         # ... (rest of response preparation logic - make sure model_validate is correct for Pydantic v2) ...
          response_data = AppointmentRequestDetails(
                id=upcoming_appointment.id,
                appointment_date=upcoming_appointment.appointment_date,
                status=upcoming_appointment.status,
                created_at=upcoming_appointment.created_at,
                patient=PatientInfo.model_validate(upcoming_appointment.patient), # Correct for Pydantic v2+
                doctor=Doctor.model_validate(upcoming_appointment.doctor), # <<< ADD THIS
                start_time=upcoming_appointment.time_slot.start_time
             )
          print(f"Found upcoming appointment {response_data.id} for user {current_user.id}")
          return response_data
    else:
        # This might indicate missing relationship data if the join succeeded but related objects are None
        print(f"Warning: Upcoming appointment {upcoming_appointment.id if upcoming_appointment else 'N/A'} missing expected related data (patient, doctor, or timeslot info).")
        return None
    
@router.get("/my-confirmed-patients", response_model=List[PatientInfo])
async def get_my_confirmed_patient_list(
    db: db_dependency,
    current_doctor: current_doctor_dependency
):
    """
    Fetches a unique list of patients (ID and username) who have CONFIRMED
    appointments (past, present, or future) with the logged-in doctor.
    """
    print(f"Fetching unique confirmed patients (basic info) for doctor {current_doctor.id}")

    # Query distinct patient Users associated with the doctor via CONFIRMED appointments
    # No need to explicitly load patient_profile if only username/id needed
    distinct_patients_query = db.query(User).join(
        Appointment, Appointment.patient_id == User.id
    ).filter(
        Appointment.doctor_id == current_doctor.id,
        Appointment.status == AppointmentStatus.CONFIRMED
    ).distinct(
        User.id
    ).order_by(User.username)

    distinct_patients_result = distinct_patients_query.all()

    # Prepare response using PatientInfo model (id, username only)
    response_list: List[PatientInfo] = []
    for patient in distinct_patients_result:
         response_list.append(
             PatientInfo(
                 id=patient.id,
                 username=patient.username
                 # No full_name here
             )
         )

    print(f"Found {len(response_list)} unique confirmed patients.")
    return response_list