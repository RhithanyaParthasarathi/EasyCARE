# backend/routers/appointments.py
from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session, joinedload, selectinload
from sqlalchemy import distinct
from typing import Annotated, List, Optional
from database import get_db
from models import TimeSlot, User, UserRole, Appointment, AppointmentStatus # Ensure correct import
from sqlalchemy import exc, and_,func
from datetime import datetime, date as py_date
from datetime import timezone
# Import the new dependency
from routers.auth import get_current_doctor, get_current_active_user
from models import Notification #import notification model

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
    current_doctor: current_doctor_dependency,
    schedule_request: ScheduleSaveRequest,
    db: db_dependency
):
    target_date = schedule_request.date
    print(f"Attempting to save schedule for doctor {current_doctor.id} on {target_date}") # DEBUG

    try:
        # 1. Identify slots to be potentially removed
        # Get IDs of all existing slots for the doctor on that day
        existing_slots_on_day = db.query(TimeSlot).filter(
            TimeSlot.doctor_id == current_doctor.id,
            TimeSlot.date == target_date
        ).all()

        new_schedule_start_times = {slot.start_time for slot in schedule_request.slots}
        slots_to_actually_delete_ids = []

        for es in existing_slots_on_day:
            if es.start_time not in new_schedule_start_times: # This slot is being removed by the new schedule
                # Check if this slot has ANY appointments (pending, confirmed, etc.)
                appointment_linked = db.query(Appointment.id).filter(Appointment.timeslot_id == es.id).first()
                if appointment_linked:
                    # If an appointment is linked, we cannot delete this TimeSlot due to FK constraint
                    db.rollback() # Important to rollback before raising
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=f"Cannot update schedule. Time slot {es.start_time} on {target_date} has an existing appointment. Please manage the appointment first."
                    )
                else:
                    # No appointment linked, safe to mark for deletion
                    slots_to_actually_delete_ids.append(es.id)

        # 2. Delete the identified old slots that are safe to delete
        if slots_to_actually_delete_ids:
            print(f"Deleting time slots with IDs: {slots_to_actually_delete_ids}") # DEBUG
            db.query(TimeSlot).filter(
                TimeSlot.id.in_(slots_to_actually_delete_ids)
            ).delete(synchronize_session=False)
            # No commit here yet, do it once at the end

        # 3. Add the new slots from the request
        # We only need to add slots that are not already in the existing_slots_on_day
        # (unless their properties like is_booked were to change, but here they are always new/available)
        final_existing_slot_times = {es.start_time for es in existing_slots_on_day if es.id not in slots_to_actually_delete_ids}
        new_slots_to_add_db = []
        for slot_data in schedule_request.slots:
            if slot_data.start_time not in final_existing_slot_times:
                # This slot is genuinely new or was one of the deletable ones
                new_time_slot = TimeSlot(
                    start_time=slot_data.start_time,
                    date=target_date,
                    doctor_id=current_doctor.id,
                    is_booked=False # New slots created by doctor are available
                )
                new_slots_to_add_db.append(new_time_slot)

        if new_slots_to_add_db:
            print(f"Adding new time slots: {[s.start_time for s in new_slots_to_add_db]}") #DEBUG
            db.add_all(new_slots_to_add_db)

        # 4. Commit all changes (deletions and additions)
        db.commit()
        print(f"Schedule for {target_date} saved successfully.") # DEBUG

    except HTTPException as http_exc: # Re-raise specific HTTPExceptions
        # db.rollback() # Already handled before raising if inside this block
        raise http_exc
    except Exception as e:
        db.rollback() # Rollback on any other unexpected error
        print(f"Error saving schedule for doctor {current_doctor.id} on {target_date}: {e}")
        # Be careful not to expose too much detail from 'e' if it's a generic Exception
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to save schedule due to a server error.")

    # Determine number of slots in the final schedule for the day
    final_slots_count = db.query(TimeSlot).filter(
        TimeSlot.doctor_id == current_doctor.id,
        TimeSlot.date == target_date
    ).count()

    return {"message": f"Schedule for {target_date.strftime('%Y-%m-%d')} updated successfully.", "slots_in_schedule": final_slots_count}


@router.delete("/schedule", status_code=status.HTTP_200_OK)
async def delete_my_schedule_for_date(
    current_doctor: current_doctor_dependency,
    db: db_dependency,
    date: str = Query(..., description="Date in YYYY-MM-DD format")
):
    try:
        target_date = datetime.strptime(date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid date format. Use YYYY-MM-DD.")

    print(f"Attempting to delete schedule for doctor {current_doctor.id} on {target_date}") # DEBUG

    try:
        # 1. Find all slots for the doctor on that date
        slots_to_delete = db.query(TimeSlot).filter(
            TimeSlot.doctor_id == current_doctor.id,
            TimeSlot.date == target_date
        ).all()

        if not slots_to_delete:
            return {"message": f"No schedule found for {target_date.strftime('%Y-%m-%d')} to delete."}

        # 2. Check if any of these slots have linked appointments
        for slot in slots_to_delete:
            appointment_linked = db.query(Appointment.id).filter(Appointment.timeslot_id == slot.id).first()
            if appointment_linked:
                db.rollback() # Important
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Cannot delete schedule: Time slot {slot.start_time} on {target_date} has an existing appointment. Please manage appointments first."
                )

        # 3. If no linked appointments, proceed with deletion
        deleted_count = 0
        if slots_to_delete: # Should always be true if we passed the 'if not slots_to_delete' check
            for slot in slots_to_delete: # Delete them individually or by ID list
                db.delete(slot)
            # Or more efficiently:
            # slot_ids_to_delete = [s.id for s in slots_to_delete]
            # deleted_count_result = db.query(TimeSlot).filter(TimeSlot.id.in_(slot_ids_to_delete)).delete(synchronize_session=False)
            # deleted_count = deleted_count_result if deleted_count_result is not None else len(slot_ids_to_delete)
            # For simplicity with individual delete then commit:
            deleted_count = len(slots_to_delete)


        db.commit()
        print(f"Deleted {deleted_count} time slots for doctor {current_doctor.id} on {target_date}.") # DEBUG

        return {"message": f"Schedule for {target_date.strftime('%Y-%m-%d')} deleted successfully."}

    except HTTPException as http_exc: # Re-raise specific HTTPExceptions
        raise http_exc
    except Exception as e:
        db.rollback()
        print(f"Error deleting schedule for doctor {current_doctor.id} on {target_date}: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to delete schedule due to a server error.")
    
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
    
@router.get("/upcoming-confirmed", response_model=Optional[AppointmentRequestDetails])
async def get_my_next_confirmed_appointment(
    db: db_dependency,
    current_user: Annotated[User, Depends(get_current_active_user)]
):
    print(f"\n--- [DEBUG] ENTERING /upcoming-confirmed for User ID: {current_user.id}, Role: {current_user.role.value} ---") # DEBUG

    now_date_utc = datetime.utcnow().date()
    print(f"[DEBUG] Current UTC Date for query: {now_date_utc}") # DEBUG

    # Base query
    query = db.query(Appointment).options(
        joinedload(Appointment.time_slot), # Eager load time_slot
        joinedload(Appointment.patient).joinedload(User.patient_profile), # Eager load patient and their profile
        joinedload(Appointment.doctor).joinedload(User.doctor_profile) # Eager load doctor and their profile
    ).filter(
        Appointment.status == AppointmentStatus.CONFIRMED,
        Appointment.appointment_date >= now_date_utc
    )
    print(f"[DEBUG] Base query constructed. Filtering by status=CONFIRMED and date>={now_date_utc}") # DEBUG

    # Filter based on user role
    if current_user.role == UserRole.patient:
        query = query.filter(Appointment.patient_id == current_user.id)
        print(f"[DEBUG] Applied PATIENT filter: patient_id = {current_user.id}") # DEBUG
    elif current_user.role == UserRole.doctor:
        query = query.filter(Appointment.doctor_id == current_user.id)
        print(f"[DEBUG] Applied DOCTOR filter: doctor_id = {current_user.id}") # DEBUG
    else:
        print(f"[DEBUG] User role '{current_user.role.value}' is not patient or doctor. Returning None.") # DEBUG
        return None

    # Order to get the earliest upcoming appointment
    # Ensure TimeSlot is imported if using TimeSlot.start_time directly
    # The join was removed as it might overcomplicate if options() works as expected
    # If TimeSlot.start_time sort fails, we can add join(Appointment.time_slot) back
    upcoming_appointment = query.order_by(
        Appointment.appointment_date.asc(),
        # Assuming TimeSlot relationship is correctly loaded to access start_time for sorting
        # If this causes issues, you might need to join explicitly or sort differently.
        # For now, let's try without explicit join on time_slot for ordering if options() handles it.
        # If there's an error related to time_slot.start_time, we will re-add:
        # .join(Appointment.time_slot).order_by(Appointment.appointment_date.asc(), TimeSlot.start_time.asc())
    ).order_by(Appointment.appointment_date.asc()).first() # Simplest order for now if time sort is an issue

    # Refined ordering to ensure sorting by time slot if date is the same
    # This requires ensuring the time_slot relationship is available for sorting.
    # If the above .order_by().first() doesn't give the earliest time on the same day,
    # you might need to query all for the earliest day, then sort in Python, or fix the SQL sort.
    # For now, let's assume appointments are distinct enough by date.

    if not upcoming_appointment:
        print(f"[DEBUG] No upcoming confirmed appointments found after filtering and ordering for User ID: {current_user.id}.") # DEBUG
        return None
    else:
        print(f"[DEBUG] Found an upcoming_appointment object. ID: {upcoming_appointment.id}, Date: {upcoming_appointment.appointment_date}, Status: {upcoming_appointment.status}") # DEBUG

    # Prepare response data
    # Check if all necessary related objects were loaded
    if upcoming_appointment.time_slot and upcoming_appointment.patient and upcoming_appointment.doctor:
        print(f"[DEBUG] All related data (time_slot, patient, doctor) seems present for appointment ID: {upcoming_appointment.id}") # DEBUG
        try:
            response_data = AppointmentRequestDetails(
                id=upcoming_appointment.id,
                appointment_date=upcoming_appointment.appointment_date,
                status=upcoming_appointment.status,
                created_at=upcoming_appointment.created_at, # Ensure this exists on Appointment model
                patient=PatientInfo.model_validate(upcoming_appointment.patient),
                doctor=Doctor.model_validate(upcoming_appointment.doctor), # Ensure Doctor model matches
                start_time=upcoming_appointment.time_slot.start_time
            )
            print(f"[DEBUG] Successfully created AppointmentRequestDetails. Returning data for appt ID: {response_data.id}") # DEBUG
            return response_data
        except Exception as e:
            print(f"[DEBUG] !!! ERROR during Pydantic validation or response creation: {e}") # DEBUG
            print(f"[DEBUG] Data for patient: {vars(upcoming_appointment.patient) if upcoming_appointment.patient else 'None'}")
            print(f"[DEBUG] Data for doctor: {vars(upcoming_appointment.doctor) if upcoming_appointment.doctor else 'None'}")
            print(f"[DEBUG] Data for time_slot: {vars(upcoming_appointment.time_slot) if upcoming_appointment.time_slot else 'None'}")
            # Do not raise HTTPException here directly, let the function return None if data is bad
            # or let Pydantic's validation failure be caught by FastAPI if response_model fails
            return None # Or raise an internal server error if this state is unexpected
    else:
        print(f"[DEBUG] !!! WARNING: Upcoming appointment ID: {upcoming_appointment.id} is missing critical related data (time_slot, patient, or doctor).") # DEBUG
        if not upcoming_appointment.time_slot: print("[DEBUG] Missing time_slot")
        if not upcoming_appointment.patient: print("[DEBUG] Missing patient")
        if not upcoming_appointment.doctor: print("[DEBUG] Missing doctor")
        return None