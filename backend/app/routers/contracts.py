from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_
from sqlalchemy.orm import selectinload
from typing import List

from app.database import get_db
from app.models import User, Supplier, Shop, Contract
from app.schemas import ContractResponse, ContractUpdate, ContractWithDetails
from app.auth import get_current_user

router = APIRouter()

@router.get("/", response_model=List[ContractWithDetails])
async def list_contracts(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """List contracts for current user"""
    query = select(Contract).options(
        selectinload(Contract.supplier),
        selectinload(Contract.shop),
        selectinload(Contract.product)
    )
    
    if current_user.role.value == "supplier":
        result = await db.execute(
            select(Supplier).where(Supplier.user_id == current_user.id)
        )
        supplier = result.scalar_one_or_none()
        if supplier:
            query = query.where(Contract.supplier_id == supplier.id)
    elif current_user.role.value == "shop":
        result = await db.execute(
            select(Shop).where(Shop.user_id == current_user.id)
        )
        shop = result.scalar_one_or_none()
        if shop:
            query = query.where(Contract.shop_id == shop.id)
    
    query = query.order_by(Contract.created_at.desc())
    result = await db.execute(query)
    return result.scalars().all()

@router.get("/{contract_id}", response_model=ContractWithDetails)
async def get_contract(
    contract_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get contract details"""
    result = await db.execute(
        select(Contract)
        .options(
            selectinload(Contract.supplier),
            selectinload(Contract.shop),
            selectinload(Contract.product)
        )
        .where(Contract.id == contract_id)
    )
    contract = result.scalar_one_or_none()
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")
    return contract

@router.patch("/{contract_id}", response_model=ContractResponse)
async def update_contract(
    contract_id: int,
    data: ContractUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Update contract"""
    result = await db.execute(
        select(Contract).where(Contract.id == contract_id)
    )
    contract = result.scalar_one_or_none()
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")
    
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(contract, field, value)
    
    await db.commit()
    await db.refresh(contract)
    return contract

@router.delete("/{contract_id}")
async def delete_contract(
    contract_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Delete contract"""
    result = await db.execute(
        select(Contract).where(Contract.id == contract_id)
    )
    contract = result.scalar_one_or_none()
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")
    
    await db.delete(contract)
    await db.commit()
    return {"message": "Contract deleted"}
