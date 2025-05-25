# backend/routers/video.py

import os
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session, joinedload
from typing import Annotated, Optional
from datetime import datetime, timedelta, timezone # Import needed datetime components

# Twilio specific imports
from twilio.jwt.access_token import AccessToken
from twilio.jwt.access_token.grants import VideoGrant

# Your project imports
from database import get_db
from models import User, UserRole, Appointment, AppointmentStatus, TimeSlot # Import necessary models
from routers.auth import get_current_active_user # Import the user dependency

# --- Pydantic Response Model ---
class VideoTokenResponse(BaseModel):
    token: str
    room_name: str

# --- Router Setup ---
router = APIRouter(
    prefix="/video", # New prefix for video related endpoints
    tags=["video"],  # Tag for API docs
)

db_dependency = Annotated[Session, Depends(get_db)]
current_user_dependency = Annotated[User, Depends(get_current_active_user)]

# --- Helper function (copied from appointments.py or move to a shared utils.py) ---
def format_time_ampm(time_str_24: str) -> str:
    """Converts HH:MM string to h:mm AM/PM format."""
    if not time_str_24: return "N/A"
    try:
        time_obj = datetime.strptime(time_str_24, "%H:%M")
        return time_obj.strftime("%I:%M %p").lstrip('0')
    except ValueError: return time_str_24

# --- Token Generation Endpoint ---
# Note the path now starts relative to the router prefix "/video"
@router.post("/token/appointment/{appointment_id}", response_model=VideoTokenResponse)
async def get_video_join_token_for_appointment( # Renamed slightly for clarity
    appointment_id: int,
    db: db_dependency,
    current_user: current_user_dependency
):
    """
    Generates a Twilio Video Access Token for an authorized user
    to join a specific confirmed appointment's video room,
    validating the appointment time window.
    """
    print(f"Request for video token for appointment {appointment_id} by user {current_user.id}")

    # 1. Fetch Appointment & Authorize
    appointment = db.query(Appointment).options(
        joinedload(Appointment.time_slot) # Load timeslot for time check
    ).filter(Appointment.id == appointment_id).first()

    if not appointment: raise HTTPException(404, "Appointment not found.")
    if not (appointment.patient_id == current_user.id or appointment.doctor_id == current_user.id): raise HTTPException(403, "Not authorized.")
    if appointment.status != AppointmentStatus.CONFIRMED: raise HTTPException(400, f"Appointment status is {appointment.status.value}.")
    if not appointment.time_slot: raise HTTPException(500,"Appointment data incomplete (missing time).")

    # 2. Time Validation (Keep this logic here)
    try:
            # Combine stored date and time string
            appointment_time_naive = datetime.strptime(appointment.time_slot.start_time, "%H:%M").time()
            appointment_dt_naive = datetime.combine(appointment.appointment_date, appointment_time_naive)

            # *** Define the LOCAL timezone the appointment was scheduled in ***
            # Example: IST = UTC+5:30 - ADJUST TO YOUR ACTUAL LOCAL TIMEZONE OFFSET
            local_tz = timezone(timedelta(hours=5, minutes=30))
            # For other timezones:
            # EST (UTC-5): timezone(timedelta(hours=-5))
            # PST (UTC-8): timezone(timedelta(hours=-8))
            # CET (UTC+1): timezone(timedelta(hours=1))
            print(f"Assuming appointment time {appointment.time_slot.start_time} is in timezone: {local_tz}") # DEBUG

            # Make the naive datetime timezone-AWARE using the local timezone
            # Using .replace() is correct for standard library fixed offset timezone objects
            appointment_dt_local = appointment_dt_naive.replace(tzinfo=local_tz)

            # *** Convert the LOCAL start time to UTC ***
            appointment_start_dt_utc = appointment_dt_local.astimezone(timezone.utc)

            # Get current UTC time
            now_utc = datetime.now(timezone.utc)

            # Define the allowed window based on the CORRECT UTC start time
            join_window_start = appointment_start_dt_utc - timedelta(minutes=15) # 15 mins before
            join_window_end = appointment_start_dt_utc + timedelta(minutes=60)  # 60 mins after

            # --- DEBUG LOGS ---
            print(f"Current Time (UTC):                {now_utc}")
            print(f"Appointment Start (Naive Combined):  {appointment_dt_naive}")
            print(f"Appointment Start (Assumed Local):   {appointment_dt_local}")
            print(f"Appointment Start (Converted UTC):   {appointment_start_dt_utc}") # This is the key value
            print(f"Join Window Start (UTC):           {join_window_start}")
            print(f"Join Window End (UTC):             {join_window_end}")
            # --- END DEBUG ---

            # Perform the check using UTC times
            if not (join_window_start <= now_utc <= join_window_end):
                detail = f"It's too early to join. Please try again closer to the appointment time." if now_utc < join_window_start else f"The time window to join this appointment has passed."
                print(f"Time validation failed: {detail}") # DEBUG
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)

            print("Time validation passed.") # DEBUG

    except ValueError as e:
            # Error parsing the date/time string itself
        print(f"Error parsing appointment time/date for validation: {e}") # DEBUG
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not validate appointment time format.")
    except Exception as e: # Catch other potential errors like timezone issues
        print(f"Unexpected error during time validation: {e}") # DEBUG
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error processing appointment time.")
        # --- End Time Validation ---
    # 3. Get Twilio Credentials
    try:
        twilio_account_sid = os.environ['TWILIO_ACCOUNT_SID']
        twilio_api_key_sid = os.environ['TWILIO_API_KEY_SID']
        twilio_api_key_secret = os.environ['TWILIO_API_KEY_SECRET']
    except KeyError as e:
        raise HTTPException(500, f"Server configuration error: Missing Twilio setting ({e})")

    # 4. Define Room Name & User Identity
    room_name = f"chronicare_appt_{appointment.id}"
    #identity = str(current_user.id)
    identity = current_user.username # New way (or use full_name)
    print(f"Generating token - Identity: '{identity}', Room: '{room_name}'")

    # 5. Create Twilio Access Token
    try:
        access_token = AccessToken(twilio_account_sid, twilio_api_key_sid, twilio_api_key_secret, identity=identity)
        video_grant = VideoGrant(room=room_name)
        access_token.add_grant(video_grant)
        jwt_token = access_token.to_jwt()
        print(f"Twilio JWT token generated successfully.")

        # 6. Return Token and Room Name
        return VideoTokenResponse(token=jwt_token, room_name=room_name)

    except Exception as e:
         print(f"!!! SERVER ERROR: Failed to generate Twilio token: {e}")
         raise HTTPException(500, f"Could not generate video access token.")