# backend/routers/notifications.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Annotated, List, Optional

from backend.database import get_db
from backend.models import Notification, User # Import User if needed for auth
from backend.routers.auth import get_current_active_user # Use general user auth
from pydantic import BaseModel
from datetime import datetime

router = APIRouter(
    prefix="/notifications",
    tags=["notifications"],
)

db_dependency = Annotated[Session, Depends(get_db)]
current_user_dependency = Annotated[User, Depends(get_current_active_user)]

# --- Pydantic Models for Notifications ---
class NotificationResponse(BaseModel):
    id: int
    message: str
    is_read: bool
    created_at: datetime
    appointment_id: Optional[int] = None # Include if needed

    class Config:
        from_attributes = True

class UnreadCountResponse(BaseModel):
    unread_count: int

# --- Endpoints ---

@router.get("", response_model=List[NotificationResponse])
async def get_my_notifications(
    current_user: current_user_dependency,
    db: db_dependency,
    mark_as_read: bool = False # Optional query param to mark as read on fetch
):
    """Fetches all notifications for the logged-in user, ordered by most recent."""
    print(f"Fetching notifications for user {current_user.id}") # DEBUG
    notifications = db.query(Notification).filter(
        Notification.user_id == current_user.id
    ).order_by(Notification.created_at.desc()).all()

    if mark_as_read and notifications:
         print(f"Marking {len(notifications)} notifications as read for user {current_user.id}") # DEBUG
         try:
              # Mark fetched notifications as read
              unread_ids = [n.id for n in notifications if not n.is_read]
              if unread_ids:
                   db.query(Notification).filter(
                       Notification.id.in_(unread_ids)
                   ).update({"is_read": True}, synchronize_session=False)
                   db.commit()
                   # Update the is_read status in the objects we're returning
                   for n in notifications:
                        if n.id in unread_ids:
                            n.is_read = True
         except Exception as e:
              db.rollback()
              print(f"Error marking notifications as read: {e}") # Log error but proceed

    return notifications

@router.get("/unread-count", response_model=UnreadCountResponse)
async def get_my_unread_notification_count(
    current_user: current_user_dependency,
    db: db_dependency
):
    """Gets the count of unread notifications for the logged-in user."""
    print(f"Fetching unread count for user {current_user.id}") # DEBUG
    count = db.query(Notification).filter(
        Notification.user_id == current_user.id,
        Notification.is_read == False
    ).count()
    print(f"Unread count for user {current_user.id}: {count}") # DEBUG
    return {"unread_count": count}

@router.post("/{notification_id}/mark-read", status_code=status.HTTP_204_NO_CONTENT)
async def mark_notification_as_read(
    notification_id: int,
    current_user: current_user_dependency,
    db: db_dependency
):
    """Marks a specific notification as read."""
    print(f"Marking notification {notification_id} as read for user {current_user.id}") # DEBUG
    notification = db.query(Notification).filter(
        Notification.id == notification_id,
        Notification.user_id == current_user.id # Ensure user owns notification
    ).first()

    if not notification:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found.")

    if not notification.is_read:
        notification.is_read = True
        db.commit()
        print("Marked as read.") # DEBUG
    else:
         print("Already marked as read.") # DEBUG

    return None # No content to return on success