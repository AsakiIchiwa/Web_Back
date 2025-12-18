from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_
from sqlalchemy.orm import selectinload
from typing import List
from io import BytesIO
from datetime import datetime

from app.database import get_db
from app.models import User, Supplier, Shop, Contract
from app.schemas import ContractResponse, ContractUpdate, ContractWithDetails
from app.auth import get_current_user

# PDF imports
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

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

@router.get("/{contract_id}/pdf")
async def generate_contract_pdf(
    contract_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Generate PDF for contract"""
    # Get contract with all relationships
    result = await db.execute(
        select(Contract)
        .options(
            selectinload(Contract.supplier).selectinload(Supplier.user),
            selectinload(Contract.shop).selectinload(Shop.user),
            selectinload(Contract.product)
        )
        .where(Contract.id == contract_id)
    )
    contract = result.scalar_one_or_none()
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")
    
    # Verify access
    if current_user.role.value == "supplier":
        supplier_result = await db.execute(
            select(Supplier).where(Supplier.user_id == current_user.id)
        )
        supplier = supplier_result.scalar_one_or_none()
        if not supplier or contract.supplier_id != supplier.id:
            raise HTTPException(status_code=403, detail="Access denied")
    elif current_user.role.value == "shop":
        shop_result = await db.execute(
            select(Shop).where(Shop.user_id == current_user.id)
        )
        shop = shop_result.scalar_one_or_none()
        if not shop or contract.shop_id != shop.id:
            raise HTTPException(status_code=403, detail="Access denied")
    
    # Generate PDF
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=2*cm,
        leftMargin=2*cm,
        topMargin=2*cm,
        bottomMargin=2*cm
    )
    
    # Styles
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=18,
        alignment=TA_CENTER,
        spaceAfter=30
    )
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=12,
        spaceBefore=15,
        spaceAfter=10
    )
    normal_style = ParagraphStyle(
        'CustomNormal',
        parent=styles['Normal'],
        fontSize=10,
        alignment=TA_JUSTIFY,
        spaceAfter=8
    )
    
    # Content
    elements = []
    
    # Header
    elements.append(Paragraph("CONG HOA XA HOI CHU NGHIA VIET NAM", styles['Heading3']))
    elements.append(Paragraph("Doc lap - Tu do - Hanh phuc", styles['Normal']))
    elements.append(Spacer(1, 20))
    elements.append(Paragraph(f"HOP DONG MUA BAN HANG HOA", title_style))
    elements.append(Paragraph(f"So: {contract.id:04d}/HDMB/{datetime.now().year}", styles['Normal']))
    elements.append(Spacer(1, 20))
    
    # Contract date
    elements.append(Paragraph(
        f"Hom nay, ngay {contract.created_at.strftime('%d')} thang {contract.created_at.strftime('%m')} nam {contract.created_at.strftime('%Y')}, "
        f"tai Van phong Cong ty, chung toi gom:",
        normal_style
    ))
    elements.append(Spacer(1, 10))
    
    # Party A - Supplier
    elements.append(Paragraph("<b>BEN A (Ben ban):</b>", heading_style))
    supplier_info = [
        ["Ten doanh nghiep:", contract.supplier.company_name or "N/A"],
        ["Dia chi:", contract.supplier.address or "N/A"],
        ["Dien thoai:", contract.supplier.phone or "N/A"],
        ["Email:", contract.supplier.user.email if contract.supplier.user else "N/A"],
        ["Dai dien:", contract.supplier.user.full_name if contract.supplier.user else "N/A"],
    ]
    table_a = Table(supplier_info, colWidths=[4*cm, 12*cm])
    table_a.setStyle(TableStyle([
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    elements.append(table_a)
    elements.append(Spacer(1, 10))
    
    # Party B - Shop
    elements.append(Paragraph("<b>BEN B (Ben mua):</b>", heading_style))
    shop_info = [
        ["Ten cua hang:", contract.shop.shop_name or "N/A"],
        ["Dia chi:", contract.shop.address or "N/A"],
        ["Dien thoai:", contract.shop.phone or "N/A"],
        ["Email:", contract.shop.user.email if contract.shop.user else "N/A"],
        ["Dai dien:", contract.shop.user.full_name if contract.shop.user else "N/A"],
    ]
    table_b = Table(shop_info, colWidths=[4*cm, 12*cm])
    table_b.setStyle(TableStyle([
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    elements.append(table_b)
    elements.append(Spacer(1, 15))
    
    # Agreement
    elements.append(Paragraph(
        "Sau khi ban bac, hai ben cung nhat tri ky ket Hop dong mua ban hang hoa voi cac dieu khoan sau:",
        normal_style
    ))
    
    # Article 1 - Products
    elements.append(Paragraph("<b>Dieu 1: San pham, so luong, don gia</b>", heading_style))
    
    # Format price
    total_value = float(contract.agreed_price) * contract.quantity
    price_formatted = f"{float(contract.agreed_price):,.0f} VND"
    total_formatted = f"{total_value:,.0f} VND"
    
    product_data = [
        ["STT", "Ten san pham", "So luong", "Don gia", "Thanh tien"],
        ["1", contract.product.name or "N/A", str(contract.quantity), price_formatted, total_formatted],
        ["", "", "", "<b>Tong cong:</b>", f"<b>{total_formatted}</b>"],
    ]
    product_table = Table(product_data, colWidths=[1*cm, 6*cm, 2.5*cm, 3.5*cm, 3.5*cm])
    product_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -2), 1, colors.black),
        ('BOX', (0, 0), (-1, -1), 1, colors.black),
    ]))
    elements.append(product_table)
    elements.append(Spacer(1, 10))
    
    # Article 2 - Validity
    start_date = contract.start_date.strftime('%d/%m/%Y') if contract.start_date else "Ngay ky"
    end_date = contract.end_date.strftime('%d/%m/%Y') if contract.end_date else "12 thang"
    
    elements.append(Paragraph("<b>Dieu 2: Thoi han hop dong</b>", heading_style))
    elements.append(Paragraph(
        f"Hop dong co hieu luc tu ngay {start_date} den ngay {end_date}.",
        normal_style
    ))
    
    # Article 3 - Payment
    elements.append(Paragraph("<b>Dieu 3: Phuong thuc thanh toan</b>", heading_style))
    elements.append(Paragraph(
        "Ben B thanh toan cho Ben A bang hinh thuc chuyen khoan hoac tien mat. "
        "Thanh toan 100% gia tri don hang khi nhan hang.",
        normal_style
    ))
    
    # Article 4 - Delivery
    elements.append(Paragraph("<b>Dieu 4: Giao nhan hang hoa</b>", heading_style))
    elements.append(Paragraph(
        "Ben A co trach nhiem giao hang dung chat luong, so luong, dia diem da thoa thuan. "
        "Ben B co trach nhiem nhan hang va kiem tra hang hoa tai thoi diem nhan.",
        normal_style
    ))
    
    # Article 5 - General terms
    elements.append(Paragraph("<b>Dieu 5: Dieu khoan chung</b>", heading_style))
    elements.append(Paragraph(
        "Hai ben cam ket thuc hien dung cac dieu khoan cua hop dong. "
        "Moi tranh chap phat sinh se duoc giai quyet thong qua thuong luong. "
        "Truong hop khong thuong luong duoc, se dua ra Toa an co tham quyen giai quyet.",
        normal_style
    ))
    elements.append(Spacer(1, 30))
    
    # Signatures
    sig_data = [
        ["<b>DAI DIEN BEN A</b>", "<b>DAI DIEN BEN B</b>"],
        ["(Ky, ghi ro ho ten)", "(Ky, ghi ro ho ten)"],
        ["", ""],
        ["", ""],
        ["", ""],
        [contract.supplier.user.full_name if contract.supplier.user else "", 
         contract.shop.user.full_name if contract.shop.user else ""],
    ]
    sig_table = Table(sig_data, colWidths=[8*cm, 8*cm])
    sig_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 15),
    ]))
    elements.append(sig_table)
    
    # Build PDF
    doc.build(elements)
    buffer.seek(0)
    
    # Return PDF
    filename = f"hop-dong-{contract.id:04d}.pdf"
    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )
