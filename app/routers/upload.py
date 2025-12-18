from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import os
import uuid
import aiofiles
from pathlib import Path

from app.database import get_db
from app.models import User, Supplier, Product
from app.auth import get_current_user, get_supplier_user

router = APIRouter()

# Create uploads directory
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB

@router.post("/image")
async def upload_image(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Upload an image and return URL"""
    # Validate file extension
    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400, 
            detail=f"File type not allowed. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"
        )
    
    # Read file content
    content = await file.read()
    
    # Validate file size
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File size exceeds 5MB limit")
    
    # Generate unique filename
    filename = f"{uuid.uuid4()}{ext}"
    filepath = UPLOAD_DIR / filename
    
    # Save file
    async with aiofiles.open(filepath, 'wb') as f:
        await f.write(content)
    
    # Return URL (relative path)
    return {
        "filename": filename,
        "url": f"/uploads/{filename}",
        "size": len(content)
    }

@router.post("/product-image/{product_id}")
async def upload_product_image(
    product_id: int,
    file: UploadFile = File(...),
    current_user: User = Depends(get_supplier_user),
    db: AsyncSession = Depends(get_db)
):
    """Upload image for a product and update product.image_url"""
    # Get supplier
    result = await db.execute(
        select(Supplier).where(Supplier.user_id == current_user.id)
    )
    supplier = result.scalar_one_or_none()
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")
    
    # Get product and verify ownership
    result = await db.execute(
        select(Product).where(Product.id == product_id, Product.supplier_id == supplier.id)
    )
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found or not owned by you")
    
    # Validate file extension
    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400, 
            detail=f"File type not allowed. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"
        )
    
    # Read file content
    content = await file.read()
    
    # Validate file size
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File size exceeds 5MB limit")
    
    # Generate unique filename
    filename = f"product_{product_id}_{uuid.uuid4()}{ext}"
    filepath = UPLOAD_DIR / filename
    
    # Delete old image if exists
    if product.image_url and product.image_url.startswith("/uploads/"):
        old_filepath = UPLOAD_DIR / product.image_url.replace("/uploads/", "")
        if old_filepath.exists():
            os.remove(old_filepath)
    
    # Save new file
    async with aiofiles.open(filepath, 'wb') as f:
        await f.write(content)
    
    # Update product image_url
    product.image_url = f"/uploads/{filename}"
    await db.commit()
    await db.refresh(product)
    
    return {
        "filename": filename,
        "url": product.image_url,
        "product_id": product_id,
        "size": len(content)
    }
