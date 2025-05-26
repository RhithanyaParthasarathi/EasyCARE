ChroniCARE:

ChroniCARE is a full-featured web application that bridges the gap between patients with chronic conditions and their healthcare providers. It offers seamless appointment scheduling, personal health data tracking, user profile management, and in-app notifications—enabling proactive, coordinated long-term care.

📌 Project Overview
ChroniCARE simplifies chronic care management for both patients and doctors.

Patients: Easily log health metrics, view visual health trends, and book telemedicine appointments.

Doctors: View and manage patient appointments, schedules, and monitor submitted health data.

🛠️ Tech Stack

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

📂 Project Structure

/chronicare-project-root
|-- alembic/
|-- backend/
|   |-- main.py
|   |-- database.py
|   |-- models.py
|   |-- requirements.txt
|   |-- routers/
|   |   |--appointments.py
|   |   |--auth.py
|   |   |--health_data.py
|   |   |--notifications.py 
|   |   |-- ... (other python files)
|   |-- .env
|-- frontend/
|   |-- index.html
|   |-- login.html
|   |-- ... (HTML, CSS, JS files)
|-- .gitignore
|-- site.db
|-- README.md

🚀 Installation & Setup
✅ Prerequisites
Python 3.9+ and pip
Git
Modern web browser

🔧 Backend Setup
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
# Optional:
EMAIL_ADDRESS=""
EMAIL_PASSWORD=""

🌐 Frontend Access
Serve frontend/ using a live server (e.g., VS Code Live Server) on port 5500
Open frontend/login.html
Ensure API_BASE_URL in frontend JS = http://127.0.0.1:8000

▶️ Running the Application
bash
# Activate virtual environment and run backend
uvicorn backend.main:app --reload 
# Open frontend/login.html in browser via live server

👥 User Roles & Access
    🩺 Doctor
       Register via register.html with license info (e.g., 12345)
       Manage appointments and health data of assigned patients

  👤 Patient
      Register via register.html
      Book appointments and log health metrics

🔄 Key Workflows
Task	Flow
Doctor sets schedule	Dashboard → "My Schedule" → Add/Save slots
Patient books appointment	Telemedicine → Choose Doctor → Select slot → Confirm
Doctor manages appointments	"My Appointments" → Accept/Decline
Patient views status	Bell icon / Notifications page
Patient and doctor connect through video consultation
Health data	"Health Monitor" → Log / View charts
Update profile	Profile → Edit & Save

Challenges & Future Enhancements
Challenges
Handling JWT securely
Managing async JS & backend data flow
Schema evolution with SQLite

Planned Features
IoT integration for live health data
Medication & prescription management
Secure messaging between doctors and patients

Deployment Considerations
Backend: Deploy FastAPI app to a Python-compatible platform ( Render, etc.).
Frontend: Deploy static files to a static host (GitHub Pages, Vercel, etc.).
Database: Use a managed cloud database (e.g., PostgreSQL) for production.
CORS: Configure backend to allow requests from the deployed frontend domain.
Environment Variables: Set all secrets on the backend hosting platform.
API_BASE_URL: Update in frontend JS to point to the live backend.
