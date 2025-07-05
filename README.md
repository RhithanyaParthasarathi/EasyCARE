# EasyCARE

EasyCARE is a full-featured web application that bridges the gap between patients and their healthcare providers. It offers seamless appointment scheduling, personal health data tracking, user profile management, and in-app notifications—enabling proactive, coordinated long-term care.

# Project Overview

EasyCARE simplifies health care management for both patients and doctors.

Patients: Easily log health metrics, view visual health trends, and book telemedicine appointments, virtually consult doctors

Doctors: View and manage patient appointments, schedules, provide video consultations and monitor submitted health data.

# Features

User Authentication: Secure registration (with role selection) and login for patients and doctors using JWT.

Role-Based Dashboards: Tailored interfaces and functionalities for patients and doctors.

Doctor Tools:

   Scheduling: Create, view, edit, and delete available telemedicine time slots.
   
   Appointment Management: View pending patient appointment requests, with options to accept or reject.
   
   Patient Roster: View a list of patients with confirmed appointments.
   
   Patient Health Overview: Access and view health data charts for their associated patients.
   
   Prescription Management: Create, view, and manage digital prescriptions for patients.
   
   Virtual Consultation: Conduct secure video/audio consultations with patients through an integrated interface.
   
Patient Tools:

   Doctor Discovery & Booking: Browse doctors, view their schedules, and request appointments for available slots.
   
   Appointment Tracking: Receive notifications on appointment status changes (confirmed/rejected).
   
   Health Data Logging: Manually input key health metrics (e.g., Heart Rate, Glucose, SpO2, Temperature, Respiratory Rate). Input is validated, and normal/abnormal status is determined.
   
   Health Data Visualization: View personal historical health data in chart format.
   
   Virtual Consultation: Join scheduled video/audio consultations with doctors.
   
   Prescription Access: View prescriptions issued by their doctors.
   
   Pharmacy Redirect Options: Access options to redirect to online pharmacies.
   
Profile Management: Both user types can manage and update their respective personal and professional (for doctors) profile information. Prompts encourage profile completion.

Notification System: Patients receive in-app notifications for appointment status changes. (Planned: Doctors receive critical health data alerts).

# Tech Stack

Backend: 

Python 3.9+, FastAPI, SQLAlchemy, SQLite (Dev), Pydantic

Authentication: JWT with python-jose, passlib[bcrypt]

Env Management: python-dotenv

Server: Uvicorn

Frontend:

HTML, CSS, JavaScript

Chart.js (for health data visualization)

Font Awesome (icons)

Version Control:

Git & GitHub

# Installation & Setup

Prerequisites:
Python 3.9+ and pip

Git

Modern web browser


Backend Setup:

bash
git clone <repository-url>

cd chronicare

python -m venv venv

source venv/bin/activate  # Or venv\Scripts\activate on Windows

cd backend

pip install -r requirements.txt


Create .env inside backend/:

env

SECRET_KEY="your_strong_secret_key"

DATABASE_URL="sqlite:///../site.db"

Optional:

EMAIL_ADDRESS=""

EMAIL_PASSWORD=""

# Frontend Access
Serve frontend/ using a live server (e.g., VS Code Live Server) on port 5500

Open frontend/login.html

Ensure API_BASE_URL in frontend JS = http://127.0.0.1:8000

# Running the Application
bash

Activate virtual environment and run backend

uvicorn backend.main:app --reload 

Open frontend/login.html in browser via live server

User Roles & Access

Doctor  

   Register via register.html with license info (e.g., 12345)       
   
   Manage appointments and health data of assigned patients

Patient
 
   Register via register.html
        
   Book appointments and log health metrics

# Key Workflows

Doctor sets schedule	Dashboard → "My Schedule" → Add/Save slots

Patient books appointment	Telemedicine → Choose Doctor → Select slot → Confirm

Doctor manages appointments	"My Appointments" → Accept/Decline

Patient views status	Bell icon / Notifications page

Patient and doctor connect through video consultation

Health data	"Health Monitor" → Log / View charts

Update profile	Profile → Edit & Save

# Challenges & Future Enhancements
Challenges

Handling JWT securely

Managing async JS & backend data flow

Schema evolution with SQLite

Planned Features

IoT integration for live health data

Medication & prescription management

Secure messaging between doctors and patients

# Deployment Considerations

Backend: Deploy FastAPI app to a Python-compatible platform ( Render, etc.).

Frontend: Deploy static files to a static host (GitHub Pages, Vercel, etc.).

Database: Use a managed cloud database (e.g., PostgreSQL) for production.

CORS: Configure backend to allow requests from the deployed frontend domain.

Environment Variables: Set all secrets on the backend hosting platform.

API_BASE_URL: Update in frontend JS to point to the live backend.
