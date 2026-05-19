import xml.etree.ElementTree as ET
from datetime import datetime
from ..models.sales import Sale, SaleDetail
from ..models.core import Branch

class SRIService:
    """
    Servicio para la integración con el SRI (Ecuador).
    Maneja la generación del XML de la factura.
    """

    @staticmethod
    def generate_access_key(sale: Sale, branch: Branch) -> str:
        """
        Genera la clave de acceso de 49 dígitos.
        Formato: fecha(8) + tipoEmis(2) + ruc(13) + ambiente(1) + serie(6) + secuencial(9) + codNum(8) + tipoEmis(1) + digVer(1)
        """
        fecha = sale.timestamp.strftime("%d%m%Y")
        tipo_comprobante = "01" # 01 para Factura
        ruc = "1790011001001" # TODO: Obtener de configuración de la empresa
        ambiente = str(sale.environment)
        serie = branch.sri_establishment_code + "001" # Establecimiento + Punto Emisión
        secuencial = str(sale.id).zfill(9) # En producción usar un contador real
        codigo_numerico = "12345678" # Aleatorio
        tipo_emision = "1" # Normal
        
        # Concatenación parcial (sin dígito verificador aún)
        clave_parcial = f"{fecha}{tipo_comprobante}{ruc}{ambiente}{serie}{secuencial}{codigo_numerico}{tipo_emision}"
        
        # Algoritmo Módulo 11 para el dígito verificador
        verificador = SRIService._calculate_modulo11(clave_parcial)
        
        return f"{clave_parcial}{verificador}"

    @staticmethod
    def _calculate_modulo11(cadena: str) -> int:
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
        Genera el XML de la factura en formato SRI v1.1.0.
        """
        factura = ET.Element("factura", id="comprobante", version="1.1.0")
        
        # Info Tributaria
        info_tributaria = ET.SubElement(factura, "infoTributaria")
        ET.SubElement(info_tributaria, "ambiente").text = str(sale.environment)
        ET.SubElement(info_tributaria, "tipoEmision").text = "1"
        ET.SubElement(info_tributaria, "razonSocial").text = "COFFEE APP S.A."
        ET.SubElement(info_tributaria, "ruc").text = "1790011001001"
        ET.SubElement(info_tributaria, "claveAcceso").text = sale.access_key
        ET.SubElement(info_tributaria, "codDoc").text = "01"
        ET.SubElement(info_tributaria, "estab").text = branch.sri_establishment_code
        ET.SubElement(info_tributaria, "ptoEmi").text = "001"
        ET.SubElement(info_tributaria, "secuencial").text = str(sale.id).zfill(9)
        ET.SubElement(info_tributaria, "dirMatriz").text = "QUITO - ECUADOR"

        # Info Factura
        info_factura = ET.SubElement(factura, "infoFactura")
        ET.SubElement(info_factura, "fechaEmision").text = sale.timestamp.strftime("%d/%m/%Y")
        ET.SubElement(info_factura, "dirEstablecimiento").text = branch.address or "QUITO"
        ET.SubElement(info_factura, "obligadoContabilidad").text = "SI"
        ET.SubElement(info_factura, "tipoIdentificacionComprador").text = sale.customer_id_type
        ET.SubElement(info_factura, "razonSocialComprador").text = sale.customer_name
        ET.SubElement(info_factura, "identificacionComprador").text = sale.customer_id
        ET.SubElement(info_factura, "totalSinImpuestos").text = f"{sale.subtotal_0 + sale.subtotal_tax:.2f}"
        ET.SubElement(info_factura, "totalDescuento").text = f"{sale.discount:.2f}"

        # Totales con Impuestos
        total_con_impuestos = ET.SubElement(info_factura, "totalConImpuestos")
        total_impuesto = ET.SubElement(total_con_impuestos, "totalImpuesto")
        ET.SubElement(total_impuesto, "codigo").text = "2" # IVA
        ET.SubElement(total_impuesto, "codigoPorcentaje").text = "2" # 12% o 15% según catálogo SRI
        ET.SubElement(total_impuesto, "baseImponible").text = f"{sale.subtotal_tax:.2f}"
        ET.SubElement(total_impuesto, "valor").text = f"{sale.tax_amount:.2f}"

        ET.SubElement(info_factura, "importeTotal").text = f"{sale.total:.2f}"
        ET.SubElement(info_factura, "moneda").text = "DOLAR"

        # Detalles
        detalles = ET.SubElement(factura, "detalles")
        for detail in sale.details:
            detalle = ET.SubElement(detalles, "detalle")
            ET.SubElement(detalle, "codigoPrincipal").text = str(detail.product_id)
            ET.SubElement(detalle, "descripcion").text = "PRODUCTO" # TODO: Traer nombre real
            ET.SubElement(detalle, "cantidad").text = f"{detail.quantity:.2f}"
            ET.SubElement(detalle, "precioUnitario").text = f"{detail.unit_price:.2f}"
            ET.SubElement(detalle, "descuento").text = f"{detail.discount:.2f}"
            ET.SubElement(detalle, "precioTotalSinImpuesto").text = f"{detail.total - detail.tax_percentage:.2f}"
            
            impuestos = ET.SubElement(detalle, "impuestos")
            impuesto = ET.SubElement(impuestos, "impuesto")
            ET.SubElement(impuesto, "codigo").text = "2"
            ET.SubElement(impuesto, "codigoPorcentaje").text = "2"
            ET.SubElement(impuesto, "tarifa").text = str(detail.tax_percentage)
            ET.SubElement(impuesto, "baseImponible").text = f"{detail.total - detail.tax_percentage:.2f}"
            ET.SubElement(impuesto, "valor").text = f"{detail.tax_percentage:.2f}"

        # Pagos
        pagos = ET.SubElement(info_factura, "pagos")
        for p in sale.payments:
            pago = ET.SubElement(pagos, "pago")
            ET.SubElement(pago, "formaPago").text = "01" # Por defecto 01-Efectivo
            ET.SubElement(pago, "total").text = f"{p.amount:.2f}"

        return ET.tostring(factura, encoding="unicode")

    @staticmethod
    def sign_xml(xml_content: str, p12_path: str, password: str) -> str:
        """
        MOCK: Firma el XML usando XAdES-BES.
        En producción requeriría la librería 'pyOpenSSL' o 'xmlsig'.
        """
        # TODO: Implementar firma real XAdES-BES
        return f"<!-- SIGNED XML MOCK -->\n{xml_content}"
