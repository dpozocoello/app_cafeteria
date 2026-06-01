import xml.etree.ElementTree as ET
from datetime import datetime
from decimal import Decimal
from ..models.sales import Sale, SaleDetail
from ..models.core import Branch

class SRIService:
    """
    Servicio encargado de la integración con el Servicio de Rentas Internas (SRI) de Ecuador.
    
    Gestiona la lógica técnica requerida para la facturación electrónica:
    1. Generación de claves de acceso estructuradas de 49 dígitos.
    2. Cálculo de dígito verificador usando el algoritmo matemático Módulo 11.
    3. Construcción del comprobante electrónico en formato XML (versión 1.1.0).
    4. Firma digital del comprobante XML usando esquemas XAdES-BES.
    """

    @staticmethod
    def generate_access_key(sale: Sale, branch: Branch) -> str:
        """
        Genera la clave de acceso oficial de 49 dígitos requerida por el SRI para comprobantes electrónicos.
        """
        fecha = sale.timestamp.strftime("%d%m%Y")
        tipo_comprobante = "01" # 01 representa Factura en el catálogo del SRI
        
        # Obtener RUC de la empresa asociada
        ruc = "1790011001001"
        if sale.company:
            ruc = sale.company.ruc
        elif branch.company:
            ruc = branch.company.ruc
            
        ambiente = str(sale.company.environment if sale.company else sale.environment)
        
        # Serie: establecimiento + punto de emisión
        estab = branch.sri_establishment_code
        pto_emi = sale.emission_point.code if sale.emission_point else "001"
        serie = f"{estab}{pto_emi}"
        
        # Secuencial: extraído del número de factura o sale.id
        if sale.invoice_number and "-" in sale.invoice_number:
            secuencial = sale.invoice_number.split("-")[-1]
        else:
            secuencial = str(sale.id).zfill(9)
            
        codigo_numerico = "12345678" # Código numérico fijo/aleatorio
        tipo_emision = "1" # "1" representa Emisión Normal
        
        # Concatenación de los primeros 48 dígitos
        clave_parcial = f"{fecha}{tipo_comprobante}{ruc}{ambiente}{serie}{secuencial}{codigo_numerico}{tipo_emision}"
        
        verificador = SRIService._calculate_modulo11(clave_parcial)
        return f"{clave_parcial}{verificador}"

    @staticmethod
    def _calculate_modulo11(cadena: str) -> int:
        """
        Implementa el algoritmo Módulo 11 (con pivote 2-7) requerido por el SRI de Ecuador.
        """
        pivot = 2
        suma = 0
        for i in range(len(cadena) - 1, -1, -1):
            suma += int(cadena[i]) * pivot
            pivot += 1
            if pivot > 7:
                pivot = 2
        
        residuo = suma % 11
        resultado = 11 - residuo
        
        if resultado == 11:
            return 0
        if resultado == 10:
            return 1
        return resultado

    @staticmethod
    def create_invoice_xml(sale: Sale, branch: Branch) -> str:
        """
        Construye la estructura de datos XML de la factura según la ficha técnica de comprobantes electrónicos v1.1.0 del SRI.
        """
        factura = ET.Element("factura", id="comprobante", version="1.1.0")
        
        # Obtener datos de la empresa y punto de emisión
        company = sale.company if sale.company else (branch.company if branch.company else None)
        ruc = company.ruc if company else "1790011001001"
        razon_social = company.business_name if company else "YUQUI S.A."
        commercial_name = company.commercial_name if company else "YUQUI - Piqueos & Cafeteria"
        address = company.address if company else "Av. de los Shyris y Portugal, Quito"
        obligado_contabilidad = "SI" if (company.obligado_contabilidad if company else True) else "NO"
        environment = str(company.environment if company else sale.environment)
        
        estab = branch.sri_establishment_code
        pto_emi = sale.emission_point.code if sale.emission_point else "001"
        if sale.invoice_number and "-" in sale.invoice_number:
            secuencial = sale.invoice_number.split("-")[-1]
        else:
            secuencial = str(sale.id).zfill(9)
            
        # 1. Bloque de Información Tributaria
        info_tributaria = ET.SubElement(factura, "infoTributaria")
        ET.SubElement(info_tributaria, "ambiente").text = environment
        ET.SubElement(info_tributaria, "tipoEmision").text = "1"
        ET.SubElement(info_tributaria, "razonSocial").text = razon_social
        if commercial_name:
            ET.SubElement(info_tributaria, "nombreComercial").text = commercial_name
        ET.SubElement(info_tributaria, "ruc").text = ruc
        ET.SubElement(info_tributaria, "claveAcceso").text = sale.access_key or ""
        ET.SubElement(info_tributaria, "codDoc").text = "01" # "01" = Factura
        ET.SubElement(info_tributaria, "estab").text = estab
        ET.SubElement(info_tributaria, "ptoEmi").text = pto_emi
        ET.SubElement(info_tributaria, "secuencial").text = secuencial
        ET.SubElement(info_tributaria, "dirMatriz").text = address

        # 2. Bloque de Información Comercial y Datos de la Transacción
        info_factura = ET.SubElement(factura, "infoFactura")
        ET.SubElement(info_factura, "fechaEmision").text = sale.timestamp.strftime("%d/%m/%Y")
        ET.SubElement(info_factura, "dirEstablecimiento").text = branch.address or address
        ET.SubElement(info_factura, "obligadoContabilidad").text = obligado_contabilidad
        ET.SubElement(info_factura, "tipoIdentificacionComprador").text = sale.customer_id_type
        ET.SubElement(info_factura, "razonSocialComprador").text = sale.customer_name
        ET.SubElement(info_factura, "identificacionComprador").text = sale.customer_id
        ET.SubElement(info_factura, "totalSinImpuestos").text = f"{sale.subtotal_0 + sale.subtotal_tax:.2f}"
        ET.SubElement(info_factura, "totalDescuento").text = f"{sale.discount:.2f}"

        # 2.1 Detalle de Impuestos Consolidados
        total_con_impuestos = ET.SubElement(info_factura, "totalConImpuestos")
        total_impuesto = ET.SubElement(total_con_impuestos, "totalImpuesto")
        ET.SubElement(total_impuesto, "codigo").text = "2" # IVA
        
        first_detail = sale.details[0] if sale.details else None
        tax_pct = float(first_detail.tax_percentage) if first_detail else 15.0
        
        codigo_porcentaje = "2"
        if abs(tax_pct - 0.0) < 0.1:
            codigo_porcentaje = "0"
        elif abs(tax_pct - 12.0) < 0.1:
            codigo_porcentaje = "2"
        elif abs(tax_pct - 14.0) < 0.1:
            codigo_porcentaje = "3"
        elif abs(tax_pct - 15.0) < 0.1:
            codigo_porcentaje = "4" # SRI code for 15% is typically 4 in Ecuador
            
        ET.SubElement(total_impuesto, "codigoPorcentaje").text = codigo_porcentaje
        ET.SubElement(total_impuesto, "baseImponible").text = f"{sale.subtotal_tax:.2f}"
        ET.SubElement(total_impuesto, "valor").text = f"{sale.tax_amount:.2f}"

        ET.SubElement(info_factura, "importeTotal").text = f"{sale.total:.2f}"
        ET.SubElement(info_factura, "moneda").text = "DOLAR"

        # 3. Bloque de Detalles
        detalles = ET.SubElement(factura, "detalles")
        for detail in sale.details:
            product_name = "PRODUCTO"
            if hasattr(detail, "product") and detail.product:
                product_name = detail.product.name
                
            detalle = ET.SubElement(detalles, "detalle")
            ET.SubElement(detail, "codigoPrincipal").text = str(detail.product_id)
            ET.SubElement(detail, "descripcion").text = product_name
            ET.SubElement(detail, "cantidad").text = f"{detail.quantity:.2f}"
            ET.SubElement(detail, "precioUnitario").text = f"{detail.unit_price:.2f}"
            ET.SubElement(detail, "descuento").text = f"{detail.discount:.2f}"
            
            subtotal_item = (detail.unit_price * detail.quantity) - detail.discount
            ET.SubElement(detail, "precioTotalSinImpuesto").text = f"{subtotal_item:.2f}"
            
            impuestos = ET.SubElement(detail, "impuestos")
            impuesto = ET.SubElement(impuestos, "impuesto")
            ET.SubElement(impuesto, "codigo").text = "2"
            
            det_tax_pct = float(detail.tax_percentage)
            det_codigo_porcentaje = "2"
            if abs(det_tax_pct - 0.0) < 0.1:
                det_codigo_porcentaje = "0"
            elif abs(det_tax_pct - 12.0) < 0.1:
                det_codigo_porcentaje = "2"
            elif abs(det_tax_pct - 14.0) < 0.1:
                det_codigo_porcentaje = "3"
            elif abs(det_tax_pct - 15.0) < 0.1:
                det_codigo_porcentaje = "4"
                
            ET.SubElement(impuesto, "codigoPorcentaje").text = det_codigo_porcentaje
            ET.SubElement(impuesto, "tarifa").text = f"{det_tax_pct:.2f}"
            ET.SubElement(impuesto, "baseImponible").text = f"{subtotal_item:.2f}"
            
            item_tax_value = subtotal_item * Decimal(det_tax_pct / 100.0)
            ET.SubElement(impuesto, "valor").text = f"{item_tax_value:.2f}"

        # 4. Bloque de Formas de Pago
        pagos = ET.SubElement(info_factura, "pagos")
        for p in sale.payments:
            pago = ET.SubElement(pagos, "pago")
            sri_code = "01"
            if hasattr(p, "payment_method") and p.payment_method and p.payment_method.sri_code:
                sri_code = p.payment_method.sri_code
            ET.SubElement(pago, "formaPago").text = sri_code
            ET.SubElement(pago, "total").text = f"{p.amount:.2f}"

        return ET.tostring(factura, encoding="unicode")

    @staticmethod
    def sign_xml(xml_content: str, p12_path: str, password: str) -> str:
        """
        Simula (Mock) el firmado digital del comprobante XML usando la norma XAdES-BES.
        """
        return f"<!-- SIGNED XML MOCK -->\n{xml_content}"
