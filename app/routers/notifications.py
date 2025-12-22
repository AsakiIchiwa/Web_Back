from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func, and_
from datetime import datetime
from typing import Optional, List
from enum import Enum

from app.database import get_db
from app.models import User, Notification, NotificationType
from app.auth import get_current_user

router = APIRouter()


# ==================== GET NOTIFICATIONS ====================

@router.get("/")
async def get_notifications(
    limit: int = Query(50, ge=1, le=100),
    skip: int = Query(0, ge=0),
    is_read: Optional[bool] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get all notifications for current user"""
    query = select(Notification).where(Notification.user_id == current_user.id)
    
    if is_read is not None:
        query = query.where(Notification.is_read == is_read)
    
    query = query.order_by(Notification.created_at.desc()).offset(skip).limit(limit)
    
    result = await db.execute(query)
    notifications = result.scalars().all()
    
    return [
        {
            "id": n.id,
            "type": n.type.value if isinstance(n.type, Enum) else (n.type or "system"),
            "title": n.title,
            "message": n.message,
            "is_read": n.is_read,
            "created_at": n.created_at.isoformat() if n.created_at else None,
            "link": n.link if hasattr(n, 'link') else None,
            "data": n.data if hasattr(n, 'data') else None
        }
        for n in notifications
    ]


@router.get("/unread-count")
async def get_unread_count(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get unread notifications count"""
    result = await db.execute(
        select(func.count(Notification.id))
        .where(Notification.user_id == current_user.id)
        .where(Notification.is_read == False)
    )
    count = result.scalar() or 0
    return {"count": count}


# ==================== MARK AS READ ====================

@router.patch("/{notification_id}")
async def update_notification(
    notification_id: int,
    data: dict,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Update notification (mark as read)"""
    result = await db.execute(
        select(Notification)
        .where(Notification.id == notification_id)
        .where(Notification.user_id == current_user.id)
    )
    notification = result.scalar_one_or_none()
    
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")
    
    if "is_read" in data:
        notification.is_read = data["is_read"]
    
    await db.commit()
    
    return {"message": "Notification updated", "id": notification_id}


@router.post("/mark-all-read")
async def mark_all_as_read(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Mark all notifications as read"""
    await db.execute(
        update(Notification)
        .where(Notification.user_id == current_user.id)
        .where(Notification.is_read == False)
        .values(is_read=True)
    )
    await db.commit()
    
    return {"message": "All notifications marked as read"}


# ==================== DELETE ====================

@router.delete("/{notification_id}")
async def delete_notification(
    notification_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Delete a notification"""
    result = await db.execute(
        select(Notification)
        .where(Notification.id == notification_id)
        .where(Notification.user_id == current_user.id)
    )
    notification = result.scalar_one_or_none()
    
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")
    
    await db.delete(notification)
    await db.commit()
    
    return {"message": "Notification deleted"}


# ==================== HELPER FUNCTION ====================

async def create_notification(
    db: AsyncSession,
    user_id: int,
    notification_type: str,
    title: str,
    message: str = "",
    link: str = None,
    data: dict = None
):
    """
    Helper function to create a new notification.
    Call this from other routers when events happen.
    
    Example:
        await create_notification(
            db=db,
            user_id=supplier.user_id,
            notification_type="rfq_received",
            title="New RFQ received",
            message="Shop ABC has sent you a new RFQ",
            link="/supplier/rfq"
        )
    """
    try:
        # Convert string to enum if needed
        try:
            ntype = NotificationType(notification_type)
        except (ValueError, KeyError):
            ntype = notification_type  # Use as string if not in enum
        
        notification = Notification(
            user_id=user_id,
            type=ntype,
            title=title,
            message=message,
            is_read=False,
            created_at=datetime.utcnow()
        )
        
        # Add optional fields if model supports them
        if hasattr(notification, 'link') and link:
            notification.link = link
        if hasattr(notification, 'data') and data:
            notification.data = data
        
        db.add(notification)
        await db.commit()
        await db.refresh(notification)
        
        return notification
    except Exception as e:
        print(f"Error creating notification: {e}")
        await db.rollback()
        return None