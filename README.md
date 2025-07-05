# EasyCARE

EasyCARE is a full-featured web application that bridges the gap between patients and healthcare providers. It offers seamless appointment scheduling, personal health data tracking, user profile management, and in-app notifications—enabling proactive, coordinated long-term care.

---

## Project Overview

EasyCARE simplifies health care management for both patients and doctors.

- **Patients:** Easily log health metrics, view visual health trends, book telemedicine appointments, and virtually consult doctors.
- **Doctors:** View and manage patient appointments and schedules, provide video consultations, and monitor submitted health data.

---

## Features

### User Authentication
- Secure registration (with role selection) and login for patients and doctors using JWT.

### Role-Based Dashboards
- Tailored interfaces and functionalities for patients and doctors.

### Doctor Tools
- **Scheduling:** Create, view, edit, and delete available telemedicine time slots.
- **Appointment Management:** View and manage patient appointment requests.
- **Patient Roster:** View a list of patients with confirmed appointments.
- **Patient Health Overview:** Access and view health data charts for patients.
- **Prescription Management:** Create, view, and manage digital prescriptions.
- **Virtual Consultation:** Conduct secure video/audio consultations.

### Patient Tools
- **Doctor Discovery & Booking:** Browse doctors, view schedules, and request appointments.
- **Appointment Tracking:** Receive notifications on appointment status updates.
- **Health Data Logging:** Input key health metrics (Heart Rate, Glucose, SpO2, Temperature, Respiratory Rate) with input validation and status assessment.
- **Health Data Visualization:** View historical health data in chart format.
- **Virtual Consultation:** Join scheduled video/audio consultations.
- **Prescription Access:** View issued prescriptions.
- **Pharmacy Redirect:** Access options to redirect to online pharmacies.

### Profile Management
- Patients and doctors can manage their profiles with prompts for profile completion.

### Notification System
- Patients receive in-app notifications for appointment status updates.  
*(Planned: Doctors receive critical health data alerts.)*

---

## Tech Stack

### Backend
- Python 3.9+
- FastAPI
- SQLAlchemy
- SQLite (Development)
- Pydantic
- JWT Authentication (python-jose, passlib[bcrypt])
- Uvicorn server

### Frontend
- HTML, CSS, JavaScript
- Chart.js (for health data visualization)
- Font Awesome (icons)

### Version Control
- Git & GitHub

---

## Key Workflows

| Action                      | Navigation                                   |
|-----------------------------|----------------------------------------------|
| Doctor sets schedule        | Dashboard → "My Schedule" → Add/Save slots   |
| Patient books appointment   | Telemedicine → Choose Doctor → Select slot   |
| Doctor manages appointments | "My Appointments" → Accept/Decline           |
| Patient views appointment   | Notifications (Bell icon)                    |
| Video Consultation          | Scheduled session via app interface          |
| Health Data Logging         | "Health Monitor" → Log/View charts           |
| Update Profile              | Profile → Edit & Save                        |

---

## Challenges & Future Enhancements

### Challenges
- Secure JWT handling.
- Managing asynchronous JavaScript with backend data flow.
- Schema evolution and data integrity with SQLite.

### Planned Features
- IoT integration for live health data streaming.
- Enhanced medication & prescription management.
- Secure in-app messaging between doctors and patients.

---

## Deployment Overview

- **Frontend deployed on:** Vercel  
- **Backend deployed on:** Render  
- **Database used:** SQLite for development; PostgreSQL planned for production.  
- **CORS configured** to allow requests from the deployed frontend.  
- **API Base URL configured** for production environment.

---

## Summary

EasyCARE is a role-based telemedicine platform developed to enhance remote patient care and enable doctors to deliver streamlined, personalized services. With features like secure portals, real-time consultations, health tracking, appointment management, and health data visualizations, EasyCARE focuses on making virtual healthcare simple and accessible.

---

