# main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import auth
from database import engine
from models import Base
from routers import appointments
from routers import notifications  # Import the new router
from routers import profile, health_data
from routers import auth, appointments, notifications, profile, video, prescriptions
 # Add video

Base.metadata.create_all(bind=engine)

app = FastAPI()

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5500",
                   "https://chroni-care-ez3l.vercel.app"],  # ONLY allow your frontend origin
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

#app.add_middleware(cookie_backend.middleware) # Added for function correctly

app.include_router(auth.router)
app.include_router(appointments.router)  # Include the new router
app.include_router(notifications.router) # Include the new router
app.include_router(profile.router)
app.include_router(video.router)
app.include_router(prescriptions.router) # Include the new video router
app.include_router(health_data.router)
print("--- MAIN.PY - Routers Included ---")