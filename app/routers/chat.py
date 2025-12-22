from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, and_, func
from sqlalchemy.orm import selectinload
from typing import List

from app.database import get_db
from app.models import User, Supplier, Shop, ChatRoom, ChatMessage, Notification, NotificationType
from app.schemas import ChatRoomResponse, ChatMessageCreate, ChatMessageResponse
from app.auth import get_current_user
from app.routers.notifications import create_notification

router = APIRouter()

async def get_or_create_chat_room(db: AsyncSession, supplier_id: int, shop_id: int) -> ChatRoom:
    """Get existing chat room or create new one"""
    result = await db.execute(
        select(ChatRoom).where(
            ChatRoom.supplier_id == supplier_id,
            ChatRoom.shop_id == shop_id
        )
    )
    chat_room = result.scalar_one_or_none()
    
    if not chat_room:
        chat_room = ChatRoom(supplier_id=supplier_id, shop_id=shop_id)
        db.add(chat_room)
        await db.flush()
    
    return chat_room

@router.get("/rooms", response_model=List[ChatRoomResponse])
async def get_chat_rooms(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get all chat rooms for current user"""
    query = select(ChatRoom).options(
        selectinload(ChatRoom.supplier).selectinload(Supplier.user),
        selectinload(ChatRoom.shop).selectinload(Shop.user),
        selectinload(ChatRoom.messages).selectinload(ChatMessage.sender)
    )
    
    if current_user.role.value == "supplier":
        supplier_result = await db.execute(
            select(Supplier).where(Supplier.user_id == current_user.id)
        )
        supplier = supplier_result.scalar_one_or_none()
        if supplier:
            query = query.where(ChatRoom.supplier_id == supplier.id)
    elif current_user.role.value == "shop":
        shop_result = await db.execute(
            select(Shop).where(Shop.user_id == current_user.id)
        )
        shop = shop_result.scalar_one_or_none()
        if shop:
            query = query.where(ChatRoom.shop_id == shop.id)
    else:
        return []
    
    query = query.order_by(ChatRoom.updated_at.desc())
    result = await db.execute(query)
    rooms = result.scalars().all()
    
    # Add last message and unread count
    response = []
    for room in rooms:
        room_dict = {
            "id": room.id,
            "supplier_id": room.supplier_id,
            "shop_id": room.shop_id,
            "created_at": room.created_at,
            "updated_at": room.updated_at,
            "supplier": room.supplier,
            "shop": room.shop,
            "messages": [],
            "last_message": room.messages[-1] if room.messages else None,
            "unread_count": sum(1 for m in room.messages if not m.is_read and m.sender_id != current_user.id)
        }
        response.append(room_dict)
    
    return response

@router.get("/rooms/{room_id}", response_model=ChatRoomResponse)
async def get_chat_room(
    room_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get chat room with messages"""
    result = await db.execute(
        select(ChatRoom)
        .options(
            selectinload(ChatRoom.supplier).selectinload(Supplier.user),
            selectinload(ChatRoom.shop).selectinload(Shop.user),
            selectinload(ChatRoom.messages).selectinload(ChatMessage.sender)
        )
        .where(ChatRoom.id == room_id)
    )
    room = result.scalar_one_or_none()
    if not room:
        raise HTTPException(status_code=404, detail="Chat room not found")
    
    # Verify access
    if current_user.role.value == "supplier":
        supplier_result = await db.execute(
            select(Supplier).where(Supplier.user_id == current_user.id)
        )
        supplier = supplier_result.scalar_one_or_none()
        if not supplier or room.supplier_id != supplier.id:
            raise HTTPException(status_code=403, detail="Access denied")
    elif current_user.role.value == "shop":
        shop_result = await db.execute(
            select(Shop).where(Shop.user_id == current_user.id)
        )
        shop = shop_result.scalar_one_or_none()
        if not shop or room.shop_id != shop.id:
            raise HTTPException(status_code=403, detail="Access denied")
    
    # Mark messages as read
    for msg in room.messages:
        if msg.sender_id != current_user.id and not msg.is_read:
            msg.is_read = True
    await db.commit()
    
    return {
        "id": room.id,
        "supplier_id": room.supplier_id,
        "shop_id": room.shop_id,
        "created_at": room.created_at,
        "updated_at": room.updated_at,
        "supplier": room.supplier,
        "shop": room.shop,
        "messages": room.messages,
        "last_message": room.messages[-1] if room.messages else None,
        "unread_count": 0
    }

@router.post("/rooms/with/{partner_user_id}", response_model=ChatRoomResponse)
async def create_or_get_chat_room(
    partner_user_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Create or get chat room with a partner (by user_id)"""
    if current_user.role.value == "supplier":
        # Get current supplier
        supplier_result = await db.execute(
            select(Supplier).where(Supplier.user_id == current_user.id)
        )
        supplier = supplier_result.scalar_one_or_none()
        if not supplier:
            raise HTTPException(status_code=404, detail="Supplier profile not found")
        
        # Get shop by user_id (partner_user_id là user_id của shop)
        shop_result = await db.execute(
            select(Shop).where(Shop.user_id == partner_user_id)
        )
        shop = shop_result.scalar_one_or_none()
        if not shop:
            raise HTTPException(status_code=404, detail="Shop not found")
        
        room = await get_or_create_chat_room(db, supplier.id, shop.id)
        
    elif current_user.role.value == "shop":
        # Get current shop
        shop_result = await db.execute(
            select(Shop).where(Shop.user_id == current_user.id)
        )
        shop = shop_result.scalar_one_or_none()
        if not shop:
            raise HTTPException(status_code=404, detail="Shop profile not found")
        
        # Get supplier by user_id (partner_user_id là user_id của supplier)
        supplier_result = await db.execute(
            select(Supplier).where(Supplier.user_id == partner_user_id)
        )
        supplier = supplier_result.scalar_one_or_none()
        if not supplier:
            raise HTTPException(status_code=404, detail="Supplier not found")
        
        room = await get_or_create_chat_room(db, supplier.id, shop.id)
    else:
        raise HTTPException(status_code=403, detail="Only suppliers and shops can chat")
    
    await db.commit()
    
    # Reload with relationships
    result = await db.execute(
        select(ChatRoom)
        .options(
            selectinload(ChatRoom.supplier).selectinload(Supplier.user),
            selectinload(ChatRoom.shop).selectinload(Shop.user),
            selectinload(ChatRoom.messages)
        )
        .where(ChatRoom.id == room.id)
    )
    room = result.scalar_one()
    
    return {
        "id": room.id,
        "supplier_id": room.supplier_id,
        "shop_id": room.shop_id,
        "created_at": room.created_at,
        "updated_at": room.updated_at,
        "supplier": room.supplier,
        "shop": room.shop,
        "messages": room.messages,
        "last_message": room.messages[-1] if room.messages else None,
        "unread_count": 0
    }

@router.post("/rooms/{room_id}/messages", response_model=ChatMessageResponse)
async def send_message(
    room_id: int,
    data: ChatMessageCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Send a message to chat room"""
    result = await db.execute(
        select(ChatRoom)
        .options(
            selectinload(ChatRoom.supplier).selectinload(Supplier.user),
            selectinload(ChatRoom.shop).selectinload(Shop.user)
        )
        .where(ChatRoom.id == room_id)
    )
    room = result.scalar_one_or_none()
    if not room:
        raise HTTPException(status_code=404, detail="Chat room not found")
    
    # Verify access and get receiver
    receiver_user_id = None
    sender_name = current_user.full_name
    
    if current_user.role.value == "supplier":
        supplier_result = await db.execute(
            select(Supplier).where(Supplier.user_id == current_user.id)
        )
        supplier = supplier_result.scalar_one_or_none()
        if not supplier or room.supplier_id != supplier.id:
            raise HTTPException(status_code=403, detail="Access denied")
        receiver_user_id = room.shop.user_id
        sender_name = supplier.company_name or current_user.full_name
        
    elif current_user.role.value == "shop":
        shop_result = await db.execute(
            select(Shop).where(Shop.user_id == current_user.id)
        )
        shop = shop_result.scalar_one_or_none()
        if not shop or room.shop_id != shop.id:
            raise HTTPException(status_code=403, detail="Access denied")
        receiver_user_id = room.supplier.user_id
        sender_name = shop.shop_name or current_user.full_name
    
    # Create message
    message = ChatMessage(
        chat_room_id=room_id,
        sender_id=current_user.id,
        message=data.message
    )
    db.add(message)
    
    # Update room updated_at
    room.updated_at = func.now()
    
    # Create notification for receiver
    if receiver_user_id:
        await create_notification(
            db=db,
            user_id=receiver_user_id,
            notification_type="new_message",  # <-- SỬA TỪ type= THÀNH notification_type=
            title="Tin nhắn mới",
            message=f"{sender_name}: {data.message[:50]}{'...' if len(data.message) > 50 else ''}",
            link=f"/chat/{room_id}"
        )
    
    await db.commit()
    await db.refresh(message)
    
    # Load sender relationship
    result = await db.execute(
        select(ChatMessage)
        .options(selectinload(ChatMessage.sender))
        .where(ChatMessage.id == message.id)
    )
    message = result.scalar_one()
    
    return message

@router.get("/unread-count")
async def get_total_unread_count(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get total unread message count"""
    query = select(ChatRoom)
    
    if current_user.role.value == "supplier":
        supplier_result = await db.execute(
            select(Supplier).where(Supplier.user_id == current_user.id)
        )
        supplier = supplier_result.scalar_one_or_none()
        if supplier:
            query = query.where(ChatRoom.supplier_id == supplier.id)
    elif current_user.role.value == "shop":
        shop_result = await db.execute(
            select(Shop).where(Shop.user_id == current_user.id)
        )
        shop = shop_result.scalar_one_or_none()
        if shop:
            query = query.where(ChatRoom.shop_id == shop.id)
    
    result = await db.execute(query.options(selectinload(ChatRoom.messages)))
    rooms = result.scalars().all()
    
    total = 0
    for room in rooms:
        total += sum(1 for m in room.messages if not m.is_read and m.sender_id != current_user.id)
    
    return {"count": total}
