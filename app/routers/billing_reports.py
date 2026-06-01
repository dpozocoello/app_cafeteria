from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, or_, and_
from datetime import datetime, date
from typing import Optional, List
from decimal import Decimal

from ..database import get_db
from ..models.sales import Sale, SaleDetail, SalePayment, PaymentMethod, CreditNote, TaxParameter
from ..models.core import Branch, EmissionPoint
from ..schemas import CreditNoteResponse, CreditNoteCreate
from ..services.inventory_service import InventoryService
from ..services.sri_service import SRIService

router = APIRouter(prefix="/api/billing-reports", tags=["Facturación y Reportería SRI"])

@router.post("/sales/{sale_id}/annul", response_model=CreditNoteResponse)
def annul_sale(sale_id: int, req: CreditNoteCreate, db: Session = Depends(get_db)):
    """
    Anula una factura y genera su respectiva Nota de Crédito en el sistema,
    reversando el stock correspondiente de manera automatizada.
    """
    sale = db.get(Sale, sale_id)
    if not sale:
        raise HTTPException(status_code=404, detail="Factura no encontrada")
        
    if sale.status == "ANULADA":
        raise HTTPException(status_code=400, detail="Esta factura ya se encuentra anulada")
        
    # Obtener el punto de emisión para la Nota de Crédito
    ep = db.get(EmissionPoint, req.emission_point_id)
    if not ep or ep.branch_id != sale.branch_id:
        raise HTTPException(status_code=400, detail="Punto de emisión no válido para la sucursal de la factura")
        
    branch = db.get(Branch, sale.branch_id)
    if not branch:
        raise HTTPException(status_code=404, detail="Sucursal no encontrada")
        
    # Cambiar estado de la venta
    sale.status = "ANULADA"
    sale.sri_status = "ANULADA"
    
    # Consumir secuencial para la Nota de Crédito
    seq_num = ep.credit_note_sequential
    ep.credit_note_sequential += 1
    
    credit_note_number = f"{branch.sri_establishment_code}-{ep.code}-{str(seq_num).zfill(9)}"
    
    # Generar Clave de Acceso SRI para la Nota de Crédito (Tipo: 04)
    cn_access_key = SRIService.generate_access_key(sale, branch, doc_type="04", sequential=credit_note_number)
    
    credit_note = CreditNote(
        sale_id=sale.id,
        company_id=branch.company_id,
        emission_point_id=ep.id,
        credit_note_number=credit_note_number,
        access_key=cn_access_key,
        reason=req.reason,
        sri_status="AUTORIZADO",  # Simulación directa de autorización exitosa del SRI
        authorization_date=datetime.utcnow()
    )
    
    db.add(credit_note)
    
    # Reversar inventario en Kárdex
    InventoryService.process_sale_inventory_reversal(db, sale)
    
    db.commit()
    db.refresh(credit_note)
    
    return credit_note

@router.get("/reports/sales-by-tax")
def get_sales_by_tax(start_date: str, end_date: str, branch_id: Optional[int] = None, db: Session = Depends(get_db)):
    """
    Consolida las ventas agrupadas por tarifas de IVA dentro de un rango de fechas.
    """
    try:
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.combine(datetime.strptime(end_date, "%Y-%m-%d"), datetime.max.time())
    except ValueError:
        raise HTTPException(status_code=400, detail="Formato de fecha inválido. Use YYYY-MM-DD")
        
    query = db.query(Sale).filter(
        Sale.sale_date >= start_dt,
        Sale.sale_date <= end_dt,
        Sale.status != "ANULADA",
        Sale.invoice_number.like("0%")  # Excluir órdenes no facturadas
    )
    
    if branch_id:
        query = query.filter(Sale.branch_id == branch_id)
        
    sales = query.all()
    
    subtotal_0 = Decimal(0)
    subtotal_tax = Decimal(0)
    tax_amount = Decimal(0)
    total = Decimal(0)
    discount = Decimal(0)
    
    for s in sales:
        subtotal_0 += Decimal(s.subtotal_0 or 0)
        subtotal_tax += Decimal(s.subtotal_tax or 0)
        tax_amount += Decimal(s.tax_amount or 0)
        total += Decimal(s.total or 0)
        discount += Decimal(s.discount or 0)
        
    return {
        "start_date": start_date,
        "end_date": end_date,
        "count": len(sales),
        "subtotal_0": float(subtotal_0),
        "subtotal_tax": float(subtotal_tax),
        "tax_amount": float(tax_amount),
        "discount": float(discount),
        "total": float(total)
    }

@router.get("/reports/withholdings")
def get_withholdings_report(start_date: str, end_date: str, branch_id: Optional[int] = None, db: Session = Depends(get_db)):
    """
    Genera el reporte de retenciones recibidas de clientes.
    """
    try:
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.combine(datetime.strptime(end_date, "%Y-%m-%d"), datetime.max.time())
    except ValueError:
        raise HTTPException(status_code=400, detail="Formato de fecha inválido. Use YYYY-MM-DD")
        
    query = db.query(Sale).filter(
        Sale.sale_date >= start_dt,
        Sale.sale_date <= end_dt,
        Sale.withholding_number.isnot(None),
        Sale.withholding_number != ""
    )
    
    if branch_id:
        query = query.filter(Sale.branch_id == branch_id)
        
    sales = query.order_by(Sale.sale_date.desc()).all()
    
    result = []
    tot_iva = Decimal(0)
    tot_renta = Decimal(0)
    
    for s in sales:
        result.append({
            "sale_id": s.id,
            "invoice_number": s.invoice_number,
            "sale_date": s.sale_date.strftime("%Y-%m-%d %H:%M:%S"),
            "customer_name": s.customer_name,
            "customer_id": s.customer_id,
            "total_invoice": float(s.total),
            "withholding_number": s.withholding_number,
            "withholding_iva": float(s.withholding_iva or 0),
            "withholding_renta": float(s.withholding_renta or 0),
            "withholding_date": s.withholding_date.strftime("%Y-%m-%d") if s.withholding_date else None
        })
        tot_iva += Decimal(s.withholding_iva or 0)
        tot_renta += Decimal(s.withholding_renta or 0)
        
    return {
        "start_date": start_date,
        "end_date": end_date,
        "count": len(sales),
        "total_withholding_iva": float(tot_iva),
        "total_withholding_renta": float(tot_renta),
        "items": result
    }

@router.get("/reports/annulled")
def get_annulled_report(start_date: str, end_date: str, branch_id: Optional[int] = None, db: Session = Depends(get_db)):
    """
    Reporte de facturas anuladas y Notas de Crédito emitidas.
    """
    try:
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.combine(datetime.strptime(end_date, "%Y-%m-%d"), datetime.max.time())
    except ValueError:
        raise HTTPException(status_code=400, detail="Formato de fecha inválido. Use YYYY-MM-DD")
        
    query = db.query(CreditNote).join(Sale).filter(
        CreditNote.created_at >= start_dt,
        CreditNote.created_at <= end_dt
    )
    
    if branch_id:
        query = query.filter(Sale.branch_id == branch_id)
        
    cns = query.order_by(CreditNote.created_at.desc()).all()
    
    result = []
    total_annulled = Decimal(0)
    
    for cn in cns:
        result.append({
            "credit_note_id": cn.id,
            "credit_note_number": cn.credit_note_number,
            "access_key": cn.access_key,
            "reason": cn.reason,
            "created_at": cn.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            "sale_id": cn.sale_id,
            "invoice_number": cn.sale.invoice_number,
            "customer_name": cn.sale.customer_name,
            "total": float(cn.sale.total)
        })
        total_annulled += Decimal(cn.sale.total)
        
    return {
        "start_date": start_date,
        "end_date": end_date,
        "count": len(cns),
        "total_annulled": float(total_annulled),
        "items": result
    }

@router.get("/reports/ats-summary")
def get_ats_summary(start_date: str, end_date: str, branch_id: Optional[int] = None, db: Session = Depends(get_db)):
    """
    Consolida las ventas agrupadas por tipo de identificación del cliente y método de pago (requisitos del ATS del SRI).
    """
    try:
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.combine(datetime.strptime(end_date, "%Y-%m-%d"), datetime.max.time())
    except ValueError:
        raise HTTPException(status_code=400, detail="Formato de fecha inválido. Use YYYY-MM-DD")
        
    # Filtrar ventas base
    base_filter = [
        Sale.sale_date >= start_dt,
        Sale.sale_date <= end_dt,
        Sale.status != "ANULADA",
        Sale.invoice_number.like("0%")
    ]
    if branch_id:
        base_filter.append(Sale.branch_id == branch_id)
        
    # 1. Agrupamiento por tipo de identificación de cliente (customer_id_type)
    # SRI Catalogo: 04=RUC, 05=Cédula, 06=Pasaporte, 07=Consumidor Final
    id_types_map = {
        "04": "RUC",
        "05": "Cédula",
        "06": "Pasaporte",
        "07": "Consumidor Final"
    }
    
    clients_group = db.query(
        Sale.customer_id_type,
        func.count(Sale.id).label("count"),
        func.sum(Sale.subtotal_0).label("subtotal_0"),
        func.sum(Sale.subtotal_tax).label("subtotal_tax"),
        func.sum(Sale.tax_amount).label("tax_amount"),
        func.sum(Sale.total).label("total")
    ).filter(*base_filter).group_by(Sale.customer_id_type).all()
    
    by_client_type = []
    for g in clients_group:
        code = g[0] or "07"
        by_client_type.append({
            "code": code,
            "label": id_types_map.get(code, "Otro"),
            "count": g[1],
            "subtotal_0": float(g[2] or 0),
            "subtotal_tax": float(g[3] or 0),
            "tax_amount": float(g[4] or 0),
            "total": float(g[5] or 0)
        })
        
    # 2. Agrupamiento por método de pago (código SRI)
    payments_group = db.query(
        PaymentMethod.sri_code,
        PaymentMethod.name,
        func.count(SalePayment.id).label("count"),
        func.sum(SalePayment.amount).label("total")
    ).join(SalePayment, SalePayment.payment_method_id == PaymentMethod.id)\
     .join(Sale, Sale.id == SalePayment.sale_id)\
     .filter(*base_filter)\
     .group_by(PaymentMethod.sri_code, PaymentMethod.name).all()
     
    by_payment_method = []
    for g in payments_group:
        by_payment_method.append({
            "sri_code": g[0],
            "name": g[1],
            "count": g[2],
            "total": float(g[3] or 0)
        })
        
    return {
        "start_date": start_date,
        "end_date": end_date,
        "by_client_type": by_client_type,
        "by_payment_method": by_payment_method
    }


@router.get("/sales")
def list_sales_for_reports(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    query: Optional[str] = None,
    db: Session = Depends(get_db)
):
    q = db.query(Sale)
    if start_date:
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        q = q.filter(Sale.sale_date >= start_dt)
    if end_date:
        end_dt = datetime.combine(datetime.strptime(end_date, "%Y-%m-%d"), datetime.max.time())
        q = q.filter(Sale.sale_date <= end_dt)
    if query:
        q = q.filter(or_(
            Sale.invoice_number.like(f"%{query}%"),
            Sale.customer_name.like(f"%{query}%"),
            Sale.customer_id.like(f"%{query}%")
        ))
    sales = q.order_by(Sale.sale_date.desc()).all()
    
    # Obtener notas de crédito para saber cuáles están anuladas y mostrar su CN asociada
    cns = {cn.sale_id: cn.credit_note_number for cn in db.query(CreditNote).all()}
    
    return [{
        "id": s.id,
        "invoice_number": s.invoice_number,
        "customer_name": s.customer_name,
        "customer_id": s.customer_id,
        "total": float(s.total),
        "status": s.status,
        "sri_status": s.sri_status,
        "sale_date": s.sale_date.strftime("%Y-%m-%d %H:%M:%S"),
        "withholding_number": s.withholding_number,
        "withholding_iva": float(s.withholding_iva or 0),
        "withholding_renta": float(s.withholding_renta or 0),
        "credit_note_number": cns.get(s.id)
    } for s in sales]

