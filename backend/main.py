# main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.routers import auth
from backend.database import engine
from backend.models import Base
from backend.routers import appointments
from backend.routers import notifications  # Import the new router


Base.metadata.create_all(bind=engine)

app = FastAPI()

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5500"],  # ONLY allow your frontend origin
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

#app.add_middleware(cookie_backend.middleware) # Added for function correctly

app.include_router(auth.router)
app.include_router(appointments.router)  # Include the new router
app.include_router(notifications.router) # Include the new router